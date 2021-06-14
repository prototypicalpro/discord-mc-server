import asyncio
from asyncio.queues import Queue
from asyncio.tasks import Task
from enum import Enum
import logging
from grpc import aio
from google.protobuf.timestamp_pb2 import Timestamp

from .pub_sub_queue import PubSubQueue
from .mc_server import MCProcess
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


class _MCCommand():
    result: asyncio.futures.Future


class _MCCommandGetPlayers(_MCCommand):
    pass


class MCManagementService(mc_management_pb2_grpc.MCManagementServicer):
    def __init__(self, proc: MCProcess):
        super().__init__()
        self.proc = proc
        self._state = MCState.BOOTING
        self._state_condition = asyncio.Condition()
        self._player_count_condition = asyncio.Condition()
        self._log_pub_sub: PubSubQueue[MCProcess.ServerLog] = PubSubQueue()

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
                self._listen_player_count(self._log_pub_sub.subscribe()),
                self._listen_player_death(self._log_pub_sub.subscribe()),
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
            await self._log_pub_sub.publish(line)

    async def _listen_player_death(self, queue: Queue[MCProcess.ServerLog]):
        # this coroutine should be cancelled
        while True:
            line = await queue.get()
            # TODO: determine if player death happens
            queue.task_done()

    async def _listen_player_count(self, queue: Queue[MCProcess.ServerLog]):
        # this coroutine should be cancelled
        while True:
            line = await queue.get()
            # TODO: determine if player join/leave happens
            queue.task_done()
        pass

    async def GetPlayerCount(
        self, request: mc_management_pb2.GetPlayerCountRequest,
        context: aio.ServicerContext) \
            -> mc_management_pb2.GetPlayerCountResponse:
        raise NotImplementedError('Method not implemented!')

    async def SubscribePlayerCount(
            self, request: mc_management_pb2.SubscribeHeartbeatRequest,
            context: aio.ServicerContext):
        raise NotImplementedError('Method not implemented!')

    async def UpdateWhitelist(
        self, request: mc_management_pb2.UpdateWhitelistRequest,
        context: aio.ServicerContext) \
            -> mc_management_pb2.UpdateWhitelistResponse:

        raise NotImplementedError('Method not implemented!')

    async def SubscribePlayerEvent(
            self, request: mc_management_pb2.SubscribePlayerEventRequest,
            context: aio.ServicerContext):
        raise NotImplementedError('Method not implemented!')

    async def GetResourceConsumption(
        self, request: mc_management_pb2.GetResourceConsumptionRequest,
        context: aio.ServicerContext) \
            -> mc_management_pb2.GetResourceConsumptionResponse:
        raise NotImplementedError('Method not implemented!')

    async def SubscribeResourceConsumptionEvent(
            self,
            request: mc_management_pb2.SubscribeResourceConsumptionEventRequest,
            context: aio.ServicerContext):
        raise NotImplementedError('Method not implemented!')

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
