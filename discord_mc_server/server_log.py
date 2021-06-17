from discord_mc_server.gen.proto.mc_management_pb2 import UpdateWhitelistResponse
import logging
import re
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, date, time
from typing import Container, Iterable, Union

MC_LOG_REGEX = re.compile(
    r'^\[(\d\d:\d\d:\d\d)] \[([^/]+)/(\w+)\] \[([^/]+)/(\w*)\]: (.*)$')
MC_MINECRAFT_MODULE = 'minecraft'
MC_SERVERLOG_SUBMODULE = 'DedicatedServer'

log = logging.getLogger('main')


class WhitelistResult(Enum):
    INVAL_NAME = 1
    NONE = 2
    NO_REMOVE = 3
    INVAL_MC_USER = 4
    DUP_ADD = 5
    LIST_OK = 6
    ADD_OK = 7
    REM_OK = 8
    TIMEOUT = 9

    def to_whitelist_result(self):
        return UpdateWhitelistResponse.WhitelistResult.Value(self.name)


@dataclass
class ServerLog:
    time: datetime
    process: str
    level: str
    module: str
    submodule: str
    msg: str
    raw_log: str

    @staticmethod
    def from_log_line(line: str) -> Union['ServerLog', str]:
        assert len(line.splitlines()) <= 1

        parsed = MC_LOG_REGEX.match(line)
        if not parsed:
            log.warning(f'Unparsed: {line}')
            return line
        else:
            hour, min, sec = [int(t) for t in parsed.group(1).split(':')]
            log_time = time(hour=hour, minute=min, second=sec)
            return ServerLog(
                datetime.combine(date.today(), log_time),
                parsed.group(2),
                parsed.group(3),
                parsed.group(4),
                parsed.group(5),
                parsed.group(6),
                line
            )

    def is_player_death(self, all_playernames: Union[Container[str], Iterable[str]]) -> Union[str, None]:
        if self.module == MC_MINECRAFT_MODULE \
                and self.submodule == MC_SERVERLOG_SUBMODULE \
                and self.msg.split(' ')[0] in all_playernames \
                and 'completed the challenge' not in self.msg \
                and 'achievement' not in self.msg \
                and 'made the advancement' not in self.msg \
                and 'has unlocked' not in self.msg \
                and 'joined the game' not in self.msg \
                and 'left the game' not in self.msg:
            return self.msg.split(' ')[0]
        else:
            return None

    def is_player_join(self) -> Union[str, None]:
        if self.module == MC_MINECRAFT_MODULE \
                and self.submodule == MC_SERVERLOG_SUBMODULE \
                and 'joined the game' in self.msg \
                and not self.msg.startswith('<'):
            return self.msg.split(' ')[0]
        else:
            return None

    def is_player_leave(self) -> Union[str, None]:
        if self.module == MC_MINECRAFT_MODULE \
                and self.submodule == MC_SERVERLOG_SUBMODULE \
                and 'left the game' in self.msg \
                and not self.msg.startswith('<'):
            return self.msg.split(' ')[0]
        else:
            return None

    def is_whitelist_response(self, player_name: Union[str, None] = None) -> Union[WhitelistResult, None]:
        whitelist_patterns = {
            WhitelistResult.INVAL_NAME: 'incorrect argument for command',
            WhitelistResult.NONE: 'there are no whitelisted players',
            WhitelistResult.NO_REMOVE: 'player is not whitelisted',
            WhitelistResult.INVAL_MC_USER: 'that player does not exist',
            WhitelistResult.DUP_ADD: 'player is already whitelisted',
            WhitelistResult.LIST_OK: 'whitelisted players:'
        }

        if player_name:
            whitelist_patterns.update({
                WhitelistResult.ADD_OK: f'added {player_name.lower()} to the whitelist',
                WhitelistResult.REM_OK: f'removed {player_name.lower()} from the whitelist',
            })

        if self.module == MC_MINECRAFT_MODULE \
                and self.submodule == MC_SERVERLOG_SUBMODULE \
                and not self.msg.startswith('<'):

            for k, string in whitelist_patterns.items():
                if string in self.msg.lower():
                    return k
        return None
