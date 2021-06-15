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

log = logging.getLogger('server_log')


class WhitelistResult(Enum):
    INVAL_NAME = 0
    NONE = 1
    NO_REMOVE = 2
    INVAL_MC_USER = 3
    LIST_OK = 3
    ADD_OK = 4
    REM_OK = 5
    TIMEOUT = 6


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
            WhitelistResult.INVAL_NAME: 'Incorrect argument for command',
            WhitelistResult.NONE: 'There are no whitelisted players',
            WhitelistResult.NO_REMOVE: 'Player is not whitelisted',
            WhitelistResult.INVAL_MC_USER: 'That player does not exist',
            WhitelistResult.LIST_OK: 'whitelisted players:'
        }

        if player_name:
            whitelist_patterns.update({
                WhitelistResult.ADD_OK: f'Added {player_name} to the whitelist',
                WhitelistResult.REM_OK: f'Removed {player_name} from the whitelist',
            })

        if self.module == MC_MINECRAFT_MODULE \
                and self.submodule == MC_SERVERLOG_SUBMODULE \
                and not self.msg.startswith('<'):

            for k, string in whitelist_patterns.items():
                if string in self.msg:
                    return k
        return None
