import pytest
import signal

from discord_mc_server.mc_server import MCProcess


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
