from datetime import datetime, time, date
from pathlib import Path
import pytest
import signal

from discord_mc_server.mc_server import MCProcess


def test_serverlog_parses_single_line_correctly():
    line = '[11:40:32] [Server thread/INFO] [stormedpanda.simplyjetpacks.SimplyJetpacks/]: Server starting...\n'
    assert MCProcess.ServerLog.from_log_line(line) == MCProcess.ServerLog(
        time=datetime.combine(date.today(), time(
            hour=11, minute=40, second=32)),
        process='Server thread',
        level='INFO',
        module='stormedpanda.simplyjetpacks.SimplyJetpacks',
        submodule='',
        msg='Server starting...',
        raw_log=line)


def test_serverlog_returns_string_when_not_parsing():
    line = 'not valid str'
    assert MCProcess.ServerLog.from_log_line(line) == line


def test_serverlog_parses_typical_logfile():
    with open(Path(__file__).parent.joinpath('assets/sample.log'), mode='r') as f:
        lines = f.readlines()
        for line in lines:
            assert isinstance(
                MCProcess.ServerLog.from_log_line(line), MCProcess.ServerLog)


@pytest.mark.asyncio
async def test_launch_server_creates_running_server_instance():
    proc = await MCProcess.make_mcprocess()
    await proc.wait_bootup()
    await proc.stop()
    assert proc.proc.returncode is not None


@pytest.mark.asyncio
async def test_stop_ok_if_process_already_closed():
    proc = await MCProcess.make_mcprocess()
    await proc.wait_bootup()
    proc.proc.terminate()
    await proc.proc.wait()

    await proc.stop()


@pytest.mark.asyncio
async def test_read_ok_if_pipe_closed():
    proc = await MCProcess.make_mcprocess()
    await proc.wait_bootup()
    proc.proc.send_signal(signal.SIGTERM)
    await proc.proc.wait()

    async for _ in proc.stdout:
        pass
