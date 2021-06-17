#!/usr/bin/env python3

import runpy
import sys
import os

sys.path.append(os.environ["SELF_PATH"])

runpy.run_module("discord_mc_server", run_name="__main__", alter_sys=True)
