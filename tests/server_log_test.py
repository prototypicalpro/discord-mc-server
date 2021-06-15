import pytest
from datetime import date, datetime, time
from pathlib import Path

from discord_mc_server.server_log import ServerLog


def test_parses_single_line_correctly():
    line = '[11:40:32] [Server thread/INFO] [stormedpanda.simplyjetpacks.SimplyJetpacks/]: Server starting...\n'
    assert ServerLog.from_log_line(line) == ServerLog(
        time=datetime.combine(date.today(), time(
            hour=11, minute=40, second=32)),
        process='Server thread',
        level='INFO',
        module='stormedpanda.simplyjetpacks.SimplyJetpacks',
        submodule='',
        msg='Server starting...',
        raw_log=line)


def test_returns_string_when_not_parsing():
    line = 'not valid str'
    assert ServerLog.from_log_line(line) == line


typical_log = None
with open(Path(__file__).parent.joinpath('assets/sample.log'), mode='r') as f:
    typical_log = f.readlines()
assert typical_log


@pytest.mark.parametrize('typical_log', typical_log)
def test_parses_typical_logfile(typical_log):
    assert isinstance(
        ServerLog.from_log_line(typical_log), ServerLog)


def test_is_player_death_detects_death():
    line = '[18:23:40] [Server thread/INFO] [minecraft/DedicatedServer]: BobTheScumbag drowned'
    parsed = ServerLog.from_log_line(line)
    assert parsed.is_player_death(['BobTheScumbag']) == 'BobTheScumbag'


def test_is_player_death_doesnt_detect_death_if_not_online():
    line = '[18:23:40] [Server thread/INFO] [minecraft/DedicatedServer]: BobTheScumbag drowned'
    parsed = ServerLog.from_log_line(line)
    assert not parsed.is_player_death([])


player_log = None
with open(Path(__file__).parent.joinpath('assets/sample_player.log'), mode='r') as f:
    player_log = f.readlines()
assert player_log


@pytest.mark.parametrize('player_log', player_log)
def test_is_player_death_doesnt_non_death(player_log):
    parsed = ServerLog.from_log_line(player_log)
    if isinstance(parsed, ServerLog):
        if 'drowned' not in parsed.msg:
            assert not parsed.is_player_death(['BobTheScumbag'])


def test_is_player_join_detects_join():
    line = '[18:22:04] [Server thread/INFO] [minecraft/DedicatedServer]: BobTheScumbag joined the game'
    parsed = ServerLog.from_log_line(line)
    assert parsed.is_player_join() == 'BobTheScumbag'


def test_is_player_join_ignores_chat():
    line = '[18:23:56] [Server thread/INFO] [minecraft/DedicatedServer]: <BobTheScumbag> I joined the game'
    parsed = ServerLog.from_log_line(line)
    assert not parsed.is_player_join()


def test_is_player_join_ignores_death():
    line = '[18:23:40] [Server thread/INFO] [minecraft/DedicatedServer]: BobTheScumbag drowned'
    parsed = ServerLog.from_log_line(line)
    assert not parsed.is_player_join()


@pytest.mark.parametrize('player_log', player_log)
def test_is_player_join_ignores_all(player_log):
    parsed = ServerLog.from_log_line(player_log)
    if isinstance(parsed, ServerLog):
        if 'joined' not in parsed.msg:
            assert not parsed.is_player_join()


def test_is_player_leave_detects_leave():
    line = '[18:24:14] [Server thread/INFO] [minecraft/DedicatedServer]: BobTheScumbag left the game'
    parsed = ServerLog.from_log_line(line)
    assert parsed.is_player_leave() == 'BobTheScumbag'


def test_is_player_leave_ignores_chat():
    line = '[18:23:56] [Server thread/INFO] [minecraft/DedicatedServer]: <BobTheScumbag> I left the game'
    parsed = ServerLog.from_log_line(line)
    assert not parsed.is_player_leave()


def test_is_player_leave_ignores_death():
    line = '[18:23:40] [Server thread/INFO] [minecraft/DedicatedServer]: BobTheScumbag drowned'
    parsed = ServerLog.from_log_line(line)
    assert not parsed.is_player_leave()


@pytest.mark.parametrize('player_log', player_log)
def test_is_player_leave_ignores_all(player_log):
    parsed = ServerLog.from_log_line(player_log)
    if isinstance(parsed, ServerLog):
        if 'left' not in parsed.msg:
            assert not parsed.is_player_leave()
