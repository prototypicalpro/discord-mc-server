import asyncio
import grpc
from google.protobuf.duration_pb2 import Duration
from .rpc_server import MCManagementService
from .gen.proto import mc_management_pb2_grpc
from .gen.proto.mc_management_pb2 import SubscribeHeartbeatRequest, SubscribeHeartbeatResponse, SubscribePlayerCountRequest, SubscribePlayerEventRequest, UpdateWhitelistRequest
import os
import logging
import signal
import sys
import atexit
from pathlib import Path
from typing import AsyncGenerator, List, Union
from .mc_server import MCProcess

CERT_CA = Path(os.environ['CERT_CA'])
CERT_SERVER = Path(os.environ['CERT_SERVER'])
CERT_SERVER_KEY = Path(os.environ['CERT_SERVER_KEY'])


log = logging.getLogger('main')


def atexit_handler(loop_future: asyncio.futures.Future):
    loop_future.set_exception(SystemExit)


async def main():
    logging.basicConfig(level=logging.INFO)
    log.setLevel(logging.DEBUG)

    cred = grpc.ssl_server_credentials(
        [(CERT_SERVER_KEY.read_bytes(), CERT_SERVER.read_bytes())],
        root_certificates=CERT_CA.read_bytes(),
        require_client_auth=True)

    # redirect sigterm to exit the process
    atexit_future = asyncio.get_running_loop().create_future()
    atexit.register(atexit_handler, atexit_future)
    signal.signal(signal.SIGTERM, lambda num, frame: sys.exit(0))

    log.info('Welcome to minecraft! Booting up...')
    log.info(f'Self PID: {os.getpid()}')

    proc = await MCProcess.make_mcprocess()
    service = MCManagementService(proc)

    server = grpc.aio.server()
    mc_management_pb2_grpc.add_MCManagementServicer_to_server(service, server)
    listen_addr = '[::]:50051'
    server.add_secure_port(listen_addr, cred)
    await server.start()

    try:
        mc_task = asyncio.create_task(service.run_service_until_termination())
        await asyncio.gather(mc_task, server.wait_for_termination(), atexit_future)
    finally:
        log.info('Recieved exit signal, exiting...')
        atexit.unregister(atexit_handler)
        atexit_future.cancel()
        if not mc_task.cancelled():
            mc_task.cancel()
        await server.stop(2)


if __name__ == '__main__':
    asyncio.run(main(), debug=True)
