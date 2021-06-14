import shutil
import re
import os
import logging
import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, date, time
from pathlib import Path
from typing import Union

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

MC_LOG_REGEX = re.compile(
    r'^\[(\d\d:\d\d:\d\d)] \[([^/]+)/(\w+)\] \[([^/]+)/(\w*)\]: (.*)$')


log = logging.getLogger('mc-server')


class MCProcessError(RuntimeError):
    pass


class MCProcess(AsyncIterator):
    @dataclass
    class ServerLog:
        time: datetime
        process: str
        level: str
        module: str
        submodule: str
        msg: str
        raw_log: str

        def from_log_line(line: str) -> Union['MCProcess.ServerLog', str]:
            assert len(line.splitlines()) <= 1

            parsed = MC_LOG_REGEX.match(line)
            if not parsed:
                log.warning(f'Unparsed: {line}')
                return line
            else:
                hour, min, sec = [int(t) for t in parsed.group(1).split(':')]
                log_time = time(hour=hour, minute=min, second=sec)
                return MCProcess.ServerLog(
                    datetime.combine(date.today(), log_time),
                    parsed.group(2),
                    parsed.group(3),
                    parsed.group(4),
                    parsed.group(5),
                    parsed.group(6),
                    line
                )

    def __init__(self, proc: asyncio.subprocess.Process):
        self.proc = proc

    async def next_line(self):
        line = await self.proc.stdout.readline()
        strline = line.decode('utf8').rstrip()
        log.debug(strline)

        return MCProcess.ServerLog.from_log_line(strline)

    async def __anext__(self):
        return await self.next_line()

    def write(self, command: str):
        log.debug(f'"{command.rstrip()}" --> server')
        self.proc.stdin.write(command.encode('utf8'))

    async def wait_bootup(self):
        # wait for bootup to finish
        async for log_msg in self:
            if isinstance(log_msg, MCProcess.ServerLog):
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
