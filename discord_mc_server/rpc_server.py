import asyncio
from asyncio.queues import Queue
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import logging
from grpc import aio, StatusCode
from google.protobuf.timestamp_pb2 import Timestamp
from typing import Set, Tuple

from .pub_sub_queue import PubSubQueue
from .mc_server import MCProcess
from .server_log import ServerLog, WhitelistResult
from .gen.proto import mc_management_pb2_grpc, mc_management_pb2

log = logging.getLogger('rpc')


class MCState(Enum):
    UNKNOWN = 0
    BOOTING = 1
    RUNNING = 2
    SIGNAL_STOP = 3
    FATAL_STOP = 4

    def to_system_status(self):
        return mc_management_pb2.SubscribeHeartbeatResponse.SystemStatus.Value(self.name)


@dataclass
class PlayerEvent():
    timestamp: datetime
    pass


@dataclass
class PlayerDeathEvent(PlayerEvent):
    name: str


@dataclass
class PlayerJoinEvent(PlayerEvent):
    name: str


@dataclass
class PlayerLeaveEvent(PlayerEvent):
    name: str


class MCManagementService(mc_management_pb2_grpc.MCManagementServicer):
    def __init__(self, proc: MCProcess):
        super().__init__()
        self.proc = proc
        self._state = MCState.BOOTING
        self._command_lock = asyncio.Lock()
        self._state_condition = asyncio.Condition()
        self._current_players: Set[str] = set()
        self._current_players_last_updated = datetime.now()
        self._log_pub_sub: PubSubQueue[ServerLog] = PubSubQueue()
        self._player_event_pub_sub: PubSubQueue[PlayerEvent] \
            = PubSubQueue()

    async def run_service_until_termination(self):
        try:
            await self.proc.wait_bootup()

            log.info('Detected system boot complete!')
            await self._post_state(MCState.RUNNING)

            log.info('Waiting for commands...')
            # TODO: replace this with queue-style datastructure that allows
            # coroutines to "catch up" if they miss some logs
            # Just a bunch of async queues?
            await asyncio.gather(
                self._listen_player_event(self._log_pub_sub.subscribe()),
                self._publish_log()
            )

            # this coroutine should be cancelled
            raise RuntimeError('STDOUT pipe closed unexpectedly')

        except asyncio.exceptions.CancelledError:
            log.info('Task cancelled')
            await self._post_state(MCState.SIGNAL_STOP)
        except Exception as err:
            log.fatal(f'Encountered exception "{err}"')
            await self._post_state(MCState.FATAL_STOP)
            raise err
        finally:
            await asyncio.shield(self._cleanup())

    async def _post_state(self, newstate: MCState):
        async with self._state_condition:
            # NOTE: this creates a race condition if the state is set faster than
            # the listener can handle it being set. I really don't think it will
            # be an issue.
            self._state = newstate
            self._state_condition.notify_all()

    async def _cleanup(self):
        log.info('Exiting....')
        self._listeners.remove_all()
        try:
            # Note that typically the server will stop due to SIGTERM on it's own
            await asyncio.wait_for(self.proc.stop(), timeout=10)
        except TimeoutError:
            log.error('Server took too long to shutdown, killing...')
            self.proc.proc.kill()
        log.info('Exit complete')

    async def _publish_log(self):
        async for line in self.proc:
            if isinstance(line, ServerLog):
                await self._log_pub_sub.publish(line)

    async def _listen_player_event(self, queue: Queue[ServerLog]):
        # this coroutine should be cancelled
        while True:
            line = await queue.get()
            queue.task_done()

            player_name = line.is_player_death(self._current_players)
            join_name = line.is_player_join()
            leave_name = line.is_player_leave()
            if player_name:
                await self._player_event_pub_sub.publish(PlayerDeathEvent(line.time, player_name))

            elif join_name:
                if join_name in self._current_players:
                    log.warning(
                        f'Player {join_name} joined but already exists? Log str {line.raw_log}')
                else:
                    self._current_players.add(join_name)
                    self._current_players_last_updated = datetime.now()

                await self._player_event_pub_sub.publish(PlayerJoinEvent(line.time, join_name))

            elif leave_name:
                if leave_name not in self._current_players:
                    log.warning(
                        f'Player {leave_name} left but was not tracked? Log str {line.raw_log}')
                else:
                    self._current_players.remove(leave_name)
                    self._current_players_last_updated = datetime.now()

                await self._player_event_pub_sub.publish(PlayerLeaveEvent(line.time, leave_name))

    async def _listen_whitelist_response(self, queue: Queue[ServerLog]) -> Tuple[WhitelistResult, ServerLog]:
        while True:
            line = await queue.get()

            res = line.is_whitelist_response()
            if res:
                return (res, line)

    async def SubscribePlayerCount(
            self, request: mc_management_pb2.SubscribeHeartbeatRequest,
            context: aio.ServicerContext):

        player_event_sub = self._player_event_pub_sub.subscribe()

        while True:
            cur_player_count = mc_management_pb2.PlayerCount(
                timestamp=Timestamp.FromDatetime(
                    self._current_players_last_updated),
                player_count=len(self._current_players),
                player_names=list(self._current_players))
            yield mc_management_pb2.SubscribePlayerCountResponse(response=cur_player_count)

            while True:
                event = await player_event_sub.get()
                if isinstance(event, PlayerJoinEvent, PlayerLeaveEvent):
                    break

    async def UpdateWhitelist(
        self, request: mc_management_pb2.UpdateWhitelistRequest,
        context: aio.ServicerContext) \
            -> mc_management_pb2.UpdateWhitelistResponse:

        if not request.player_name:
            context.set_code(StatusCode.OUT_OF_RANGE)
            context.set_code('invalid player name!')
            return mc_management_pb2.UpdateWhitelistResponse()

        command = None
        expected_result = None
        if request.action == mc_management_pb2.UpdateWhitelistRequest.UpdateWhitelistAction.ADD:
            command = '/whitelist add'
            expected_result = WhitelistResult.ADD_OK
        elif request.action == mc_management_pb2.UpdateWhitelistRequest.UpdateWhitelistAction.REMOVE:
            command = '/whitelist remove'
            expected_result = WhitelistResult.REM_OK
        else:
            context.set_code(StatusCode.OUT_OF_RANGE)
            context.set_code('invalid whitelist action!')
            return mc_management_pb2.UpdateWhitelistResponse()

        async with self._command_lock:
            queue = self._log_pub_sub.subscribe()

            self.proc.write(f'{command} {request.player_name}\n')

            try:
                res, log = await asyncio.wait_for(self._listen_whitelist_response(queue), 1)
            except asyncio.TimeoutError:
                res = WhitelistResult.TIMEOUT
                log = ''

            if res != expected_result and res != WhitelistResult.TIMEOUT:
                context.set_code(StatusCode.INTERNAL)
                context.set_code(
                    f'Could not update whitelist! Got response {log}')
                return mc_management_pb2.UpdateWhitelistResponse()

            self.proc.write('/whitelist list\n')

            try:
                list_res, list_log = await asyncio.wait_for(self._listen_whitelist_response(queue), 1)
            except asyncio.TimeoutError:
                list_log = ''
                list_res = WhitelistResult.TIMEOUT

            if list_res != WhitelistResult.LIST_OK:
                context.set_code(StatusCode.INTERNAL)
                context.set_code(
                    f'Could not retrieve whitelist! Got response {list_log}')
                return mc_management_pb2.UpdateWhitelistResponse()

            whitelist = list_log.msg.split(': ')[1].split(', ')
            return mc_management_pb2.UpdateWhitelistResponse(
                timestamp=Timestamp.FromDatetime(log.time), response=log.msg, whitelist=whitelist)

    async def SubscribePlayerEvent(
            self, request: mc_management_pb2.SubscribePlayerEventRequest,
            context: aio.ServicerContext):

        player_event_sub = self._player_event_pub_sub.subscribe()

        while True:
            event = None
            while True:
                event = await player_event_sub.get()
                if isinstance(event, PlayerDeathEvent):
                    break

            death_event = mc_management_pb2.PlayerDeathEvent(
                player_name=event.name)

            yield mc_management_pb2.SubscribePlayerEventResponse(
                timestamp=Timestamp.FromDatetime(event.timestamp), death_event=death_event)

    async def SubscribeHeartbeat(
            self, request: mc_management_pb2.SubscribeHeartbeatRequest,
            context: aio.ServicerContext):

        time = request. heartbeat_duration_sec_atleast.seconds + \
            request.heartbeat_duration_sec_atleast.nanos / 1e-9
        if time == 0:
            time = None

        send_state = self._state

        while True:
            now = Timestamp()
            now.GetCurrentTime()

            yield mc_management_pb2.SubscribeHeartbeatResponse(
                timestamp=now, status=send_state.to_system_status())

            if send_state == MCState.SIGNAL_STOP \
                    or send_state == MCState.FATAL_STOP:
                return

            async with self._state_condition:
                if send_state == self._state:
                    try:
                        await asyncio.wait_for(
                            self._state_condition.wait(), timeout=time)
                    except asyncio.TimeoutError:
                        pass
                    except asyncio.CancelledError:
                        pass

                send_state = self._state
