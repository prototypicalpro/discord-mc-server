import asyncio
import os
import logging
import signal
import sys
import atexit
from typing import AsyncGenerator, List, Union

from .mc_server import MCProcess

log = logging.getLogger('main')


async def mc_main_loop(proc: MCProcess):
    await proc.wait_bootup()

    log.info('Engine detected server is ready!')

    proc.write('/list\n')

    async for log_msg in proc.stdout:
        # process events and such!
        pass

    log.fatal('STDOUT pipe closed unexpectedly!')
    raise RuntimeError('STDOUT pipe closed unexpectedly')


def atexit_handler(loop_future: asyncio.futures.Future):
    loop_future.set_exception(SystemExit)


async def main():
    logging.basicConfig(level=logging.INFO)
    log.setLevel(logging.DEBUG)

    log.info('Welcome to minecraft! Booting up...')
    log.info(f'Self PID: {os.getpid()}')

    proc = await MCProcess.make_mcprocess()
    atexit_future = asyncio.get_running_loop().create_future()
    atexit.register(atexit_handler, atexit_future)
    signal.signal(signal.SIGTERM, lambda num, frame: sys.exit(0))

    try:
        mc_task = asyncio.create_task(mc_main_loop(proc))
        await asyncio.gather(mc_task, atexit_future)
    finally:
        log.info('Recieved exit signal, exiting...')
        mc_task.cancel()
        atexit_future.cancel()
        try:
            # Note that typically the server will stop due to SIGTERM on it's own
            await asyncio.wait_for(proc.stop(), timeout=10)
        except TimeoutError:
            log.error('Server took too long to shutdown, killing...')
            proc.proc.kill()
        atexit.unregister(atexit_handler)


if __name__ == '__main__':
    asyncio.run(main(), debug=True)
