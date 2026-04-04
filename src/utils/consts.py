import os
import ctypes as ct
import typing as ty

TAB_SZ = 2
VER = "0.1"

RUN_PTH = os.path.dirname(os.path.dirname(__file__))
BIN_PTH = os.path.join(RUN_PTH, "bin")
CFG_FL = os.path.join(RUN_PTH, "cfg.py")
BUILTIN_PTH = os.path.join(RUN_PTH, "intrpr", "builtin_cmds")
HIST_FL = os.path.join(RUN_PTH, "quark_hist.txt")
RL_INIT_FL = os.path.join(RUN_PTH, "rl_init.rc")

SP_CHRS = ("|", ">", "?", ";")

# Colour codes
# TODO: Make some way to identify if the terminal support ANSI
ANSI = True
ANSI_BOLD = "\033[1m" if ANSI else ""
ANSI_BLINK = "\033[5m" if ANSI else ""
ANSI_BLUE = "\033[94m" if ANSI else ""
ANSI_CLS = "\033[H\033[J" if ANSI else ""
ANSI_CYAN = "\033[96m" if ANSI else ""
ANSI_GREEN = "\033[92m" if ANSI else ""
ANSI_HEADER = "\033[95m" if ANSI else ""
ANSI_RED = "\033[91m" if ANSI else ""
ANSI_RESET = "\033[0m" if ANSI else ""
ANSI_UNDERLINE = "\033[4m" if ANSI else ""
ANSI_YELLOW = "\033[93m" if ANSI else ""
ANSI_BOLD_RED = ANSI_BOLD + ANSI_RED
ANSI_BOLD_YELLOW = ANSI_BOLD + ANSI_YELLOW


class Defaults:
    PROMPT = "!u@!h !p !$ "
    PTH = (BIN_PTH,)

