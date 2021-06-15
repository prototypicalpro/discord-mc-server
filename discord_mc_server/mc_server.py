import shutil
import os
import logging
import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

from .server_log import ServerLog

assert shutil.which('java')
JAVA_PATH = Path(shutil.which('java'))
JAVA_TUNE_ARGS = (
    '-XX:+UseG1GC',
    '-XX:+UnlockExperimentalVMOptions',
    '-Xmx6144M',
    '-Xms4096M',
    '-jar'
)
SERVER_DIR = Path(f'{os.getcwd()}/server')
# SERVER_JAR = SERVER_DIR.joinpath('forge-1.16.5-36.1.16.jar')
SERVER_JAR = SERVER_DIR.joinpath('forge-1.16.5-36.1.16.jar')
SERVER_ARGS = ('nogui')


log = logging.getLogger('mc-server')


class MCProcessError(RuntimeError):
    pass


class MCProcess(AsyncIterator):
    def __init__(self, proc: asyncio.subprocess.Process):
        self.proc = proc

    async def next_line(self):
        line = await self.proc.stdout.readline()
        strline = line.decode('utf8').rstrip()
        log.debug(strline)

        return ServerLog.from_log_line(strline)

    async def __anext__(self):
        return await self.next_line()

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

    async def stop(self):
        if self.proc.returncode is not None:
            return

        self.write('/stop\n')

        async for _ in self.stdout:
            pass

        await self.proc.wait()

    @staticmethod
    async def make_mcprocess() -> 'MCProcess':
        process = await asyncio.create_subprocess_exec(
            JAVA_PATH, *JAVA_TUNE_ARGS,
            SERVER_JAR, *SERVER_ARGS,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            cwd=SERVER_DIR)
        log.info(f'Server PID: {process.pid}')
        return MCProcess(process)
