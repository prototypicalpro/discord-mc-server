# import asyncio
# import signal
# import mmap
# import pytest
# import sys
# from discord_mc_server.mc_server import SERVER_DIR

# TODO: proc.stdout.readline never returns?
# @pytest.mark.asyncio
# async def test_server_launches_ok_and_kills_sigterm(capsys):
#     proc = await asyncio.create_subprocess_exec(
#         sys.executable, '-m', 'discord_mc_server',
#         stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE)

#     while True:
#         line = await proc.stdout.readline()
#         line_str = line.decode('utf8').rstrip()
#         print(line_str)

#         assert 'fatal' not in line_str.lower()
#         if 'Engine detected server is ready!' in line_str:
#             break

#     proc.send_signal(signal.SIGTERM)

#     print('Waiting...')
#     await proc.wait()

#     with open(SERVER_DIR.joinpath('logs/latest.log'), mode='r') as f:
#         with mmap.mmap(f.fileno(), length=0, access=mmap.ACCESS_READ) as map:
#             ret = map.find(
#                 '[net.minecraft.server.MinecraftServer/]: Stopping server')
#             assert ret != -1
