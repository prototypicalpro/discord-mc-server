import shutil
import os
import logging
import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

from .server_log import ServerLog

assert shutil.which('java')
JAVA_PATH = Path(shutil.which('java'))
JAVA_TUNE_ARGS = os.environ.get('JAVA_TUNE_ARGS', '').split(' ')
SERVER_DIR = Path(os.environ.get('SERVER_DIR', os.getcwd()))
# SERVER_JAR = SERVER_DIR.joinpath('forge-1.16.5-36.1.16.jar')
SERVER_JAR = SERVER_DIR.joinpath(os.environ.get(
    'SERVER_JAR', 'forge-1.16.5-36.1.16.jar'))
SERVER_ARGS = os.environ.get('SERVER_ARGS', '').split(' ')


log = logging.getLogger('main')


class MCProcessError(RuntimeError):
    pass


class MCProcess(AsyncIterator):
    def __init__(self, proc: asyncio.subprocess.Process):
        self.proc = proc

    async def next_line(self):
        if self.proc.stdout.at_eof():
            return None

        line = await self.proc.stdout.readline()
        strline = line.decode('utf8').rstrip()
        log.debug(strline)

        return ServerLog.from_log_line(strline)

    async def __anext__(self):
        line = await self.next_line()
        if line is None:
            raise StopAsyncIteration()
        return line

    def write(self, command: str):
        log.debug(f'"{command.rstrip()}" --> server')
        self.proc.stdin.write(command.encode('utf8'))

    async def wait_bootup(self):
        # wait for bootup to finish
        async for log_msg in self:
            if isinstance(log_msg, ServerLog):
                if log_msg.module == 'minecraft':
                    if log_msg.level == 'FATAL':
                        raise MCProcessError(
                            f'server raised a fatal error {log_msg.raw_log}')

                    if log_msg.level == 'INFO' and 'done' in log_msg.msg.lower():
                        return

        raise RuntimeError('stdout pipe closed unexpectedly!')

    async def stop(self):
        if self.proc.returncode is not None:
            return

        self.write('/stop\n')

        await self.proc.wait()

    @staticmethod
    async def make_mcprocess() -> 'MCProcess':
        process = await asyncio.create_subprocess_exec(
            JAVA_PATH, *JAVA_TUNE_ARGS,
            '-jar', SERVER_JAR, *SERVER_ARGS,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            cwd=SERVER_DIR)
        log.info(f'Server PID: {process.pid}')
        return MCProcess(process)
