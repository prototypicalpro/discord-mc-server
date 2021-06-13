import asyncio
from asyncio.futures import Future
from asyncio.streams import StreamReader
from asyncio.subprocess import Process
import os
import logging
import shutil
import subprocess
import re
import datetime
import signal
import sys
import atexit
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncGenerator, List, Union

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


log = logging.getLogger('discord-mc-server')


class MCProcess:
    @dataclass
    class ServerLog:
        time: datetime.datetime
        process: str
        level: str
        module: str
        submodule: str
        msg: str
        raw_log: str

    def __init__(self, proc: Process):
        self.proc = proc
        self.stdout = self._parse_log_gen(proc.stdout)

    def write(self, command: str):
        log.debug(f'"{command.rstrip()}" --> server')
        self.proc.stdin.write(command.encode('utf8'))

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
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, cwd=SERVER_DIR)
        log.debug(f'Server PID: {process.pid}')
        return MCProcess(process)

    @staticmethod
    async def _parse_log_gen(stream: StreamReader):
        while not stream.at_eof():
            line = await stream.readline()
            strline = line.decode('utf8').rstrip()
            log.debug(strline)

            yield MCProcess._parse_server_log(strline)

    @staticmethod
    def _parse_server_log(line: str) -> Union['MCProcess.ServerLog', str]:
        assert len(line.splitlines()) <= 1

        parsed = MC_LOG_REGEX.match(line)
        if not parsed:
            return line
        else:
            hour, min, sec = [int(time) for time in parsed.group(1).split(':')]
            time = datetime.time(hour=hour, minute=min, second=sec)
            return MCProcess.ServerLog(
                datetime.datetime.combine(datetime.date.today(), time),
                parsed.group(2),
                parsed.group(3),
                parsed.group(4),
                parsed.group(5),
                parsed.group(6),
                line
            )


class MCError(Exception):
    pass


async def mc_main_loop(proc: MCProcess):
    # wait for bootup to finish
    async for log_msg in proc.stdout:
        if isinstance(log_msg, MCProcess.ServerLog):
            if log_msg.module == 'minecraft':
                if log_msg.level == 'FATAL':
                    log.fatal('Server crashed?')
                    raise Exception('server raised a fatal error')

                if log_msg.level == 'INFO' and 'done' in log_msg.msg.lower():
                    log.info('Server done!')
                    break
        else:
            log.warning(f'Unparsed: "{log_msg}"')

    async for log_msg in proc.stdout:
        # process events and such!
        pass

    log.fatal('STDOUT pipe closed unexpectedly!')
    raise MCError('STDOUT pipe closed unexpectedly')


def atexit_handler(loop_future: Future):
    loop_future.set_exception(SystemExit)


async def main():
    logging.basicConfig(level=logging.INFO)
    log.setLevel(logging.DEBUG)

    log.info('Welcome to minecraft! Booting up...')
    log.debug(f'Self PID: {os.getpid()}')

    proc = await MCProcess.make_mcprocess()
    atexit_future = asyncio.get_running_loop().create_future()
    atexit.register(atexit_handler, atexit_future)
    signal.signal(signal.SIGTERM, lambda num, frame: sys.exit(0))

    try:
        mc_task = asyncio.create_task(mc_main_loop(proc))
        await asyncio.gather(mc_task, atexit_future)
    finally:
        mc_task.cancel()
        try:
            # Note that typically the server will stop due to SIGTERM on it's own
            await asyncio.wait_for(proc.stop(), timeout=10)
        except TimeoutError:
            log.error('Server took too long to shutdown, killing...')
            proc.proc.kill()
        atexit.unregister(atexit_handler)


if __name__ == '__main__':
    asyncio.run(main(), debug=True)
