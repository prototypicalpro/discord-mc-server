import asyncio

from google.protobuf.duration_pb2 import Duration
from .rpc_server import MCManagementService
from .gen.proto.mc_management_pb2 import SubscribeHeartbeatRequest
import os
import logging
import signal
import sys
import atexit
from typing import AsyncGenerator, List, Union

from .mc_server import MCProcess

log = logging.getLogger('main')


def atexit_handler(loop_future: asyncio.futures.Future):
    loop_future.set_exception(SystemExit)


async def check_heartbeat(service: MCManagementService):
    request = SubscribeHeartbeatRequest(
        heartbeat_duration_sec_atleast=Duration(seconds=0, nanos=0))
    async for beat in service.SubscribeHeartbeat(request, None):
        print(beat)


async def main():
    logging.basicConfig(level=logging.INFO)
    log.setLevel(logging.DEBUG)

    # redirect sigterm to exit the process
    atexit_future = asyncio.get_running_loop().create_future()
    atexit.register(atexit_handler, atexit_future)
    signal.signal(signal.SIGTERM, lambda num, frame: sys.exit(0))

    log.info('Welcome to minecraft! Booting up...')
    log.info(f'Self PID: {os.getpid()}')

    proc = await MCProcess.make_mcprocess()
    service = MCManagementService(proc)

    asyncio.create_task(check_heartbeat(service))

    try:
        mc_task = asyncio.create_task(service.run_service_until_termination())
        await asyncio.gather(mc_task, atexit_future)
    finally:
        log.info('Recieved exit signal, exiting...')
        atexit.unregister(atexit_handler)
        atexit_future.cancel()


if __name__ == '__main__':
    asyncio.run(main(), debug=True)
