import logging as lg
import os
import re
import signal as sig
import sys
import termios
import traceback as tb
import tty
import typing as ty

import intrpr.eng as ieng
import intrpr.cfg_mgr as cmgr
import utils.consts as uconst
import utils.err_codes as uerr
import utils.gen as ugen
import utils.loggers as ulog

get_pos_regex = re.compile(r"^\x1b\[(\d*);(\d*)R")
str_join = "".join
HELP_TXT = f"""USAGE
  {sys.argv[0]} [flag ...]
ARGUMENTS
  none
OPTIONS
  --debug-time-unit
              Set unit for debugging time output.
              Valid: 'ns', 'us', 'ms', 's'
FLAGS
  -d, --debug
              Show debug messages
  -e, --load-external
              Load all external commands on startup
  -h, --help  Display help text
  -i, --info  Show info messages
  -pe, --preserve-ANSI-stderr
              Preserve ANSI codes in STDERR redirects
  -po, --preserve-ANSI-stdout
              Preserve ANSI codes in STDOUT redirects
  -W, --no-warning
              Suppress warnings
""".expandtabs(2)


class MainProgParsed(ty.NamedTuple):
    pre_ld_ext_cmds: bool
    stdout_ansi: bool
    stderr_ansi: bool
    log_lvl: int
    debug_time_expo: int


def getch() -> str:
    fd = sys.stdin.fileno()
    old_setts = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_setts)
    return ch


# Source - https://stackoverflow.com/a/46675451
# Posted by netzego, modified by community. See post 'Timeline' for change history
# Retrieved 2026-04-01, License - CC BY-SA 3.0
def get_pos() -> tuple[int, int] | None:
    buf = ""
    stdin = sys.stdin.fileno()
    tattr = termios.tcgetattr(stdin)

    try:
        tty.setcbreak(stdin, termios.TCSANOW)
        sys.stdout.write("\x1b[6n")
        sys.stdout.flush()
        while True:
            buf += sys.stdin.read(1)
            if buf[-1] == "R":
                break
    finally:
        termios.tcsetattr(stdin, termios.TCSANOW, tattr)

    # Reading the actual values, but what if a keystroke appears while reading
    # from stdin? As dirty work around, getpos() returns if this fails: None
    try:
        matches = re.match(get_pos_regex, buf)
        groups = matches.groups()
    except AttributeError:
        return None

    return (int(groups[0]), int(groups[1]))


def inp() -> str:
    init_ln, init_col = get_pos()
    cur_ln, cur_col = 0, 0
    prev_ch = None
    ch = None
    ln_buf = []
    f = open("quark.txt", "w")

    while True:
        ch = getch()

        # Move to start of line
        if ch == "\x01":
            # cur_col = 0
            # ugen.write(f"\x1b[{cur_ln};{init_col}H")
            pass
        elif ch == "\x03":
            raise KeyboardInterrupt
        elif ch == "\x04":
            raise EOFError
        # Move to end of line
        elif ch == "\x05":
            cur_col = len(ln_buf)

        f.write(repr(ch) + "\n")
        cur_col += 1
        ln_buf.insert(cur_col, ch)
        ugen.write(f"\x1b[{init_ln};{init_col}H" + str_join(ln_buf))

        if ch == "\r":
            ugen.write("\n")
            break
        else:
            ugen.write("\x1b[0K")

    f.close()
    return str_join(ln_buf)


def parse_argv(passed_params: list[str]) -> MainProgParsed:
    """
    Parse parameters passed to the main program.

    :param passed_params: A list of strings, which is the passed parameters to
                        the main program.
    :type passed_params: list[str]

    :returns: An object that contains all the data that can be received from
              the arguments, options and flags that can be provided to the main
              program.
    :rtype: MainProgParsed
    """
    len_passed_params = len(passed_params)
    skip = 0

    pre_ld_ext_cmds = False
    stdout_ansi = False
    stderr_ansi = False
    log_lvl = ulog.WARN
    debug_time_expo = 6

    for i, param in enumerate(passed_params):
        if skip:
            skip -= 1
            continue

        # Flag: preload external commands
        if param in ("-e", "--load-external"):
            pre_ld_ext_cmds = True
        # Flag: Show debug
        elif param in ("-d", "--debug"):
            log_lvl = ulog.DEBUG
        elif param in ("-po", "--preserve-ANSI-stdout"):
            stdout_ansi = True
        # Flag: Preserve ANSI colour codes in STDERR redirects
        elif param in ("-pe", "--preserve-ANSI-stderr"):
            stderr_ansi = True
        # Flag: Show info
        elif param in ("-i", "--info"):
            log_lvl = ulog.INFO
        # Flag: No warnings
        elif param in ("-W", "--no-warnings"):
            if log_lvl <= ulog.WARN:
                log_lvl = ulog.ERR
        elif param in ("-h", "--help"):
            ugen.write(HELP_TXT)
            sys.exit(uerr.ERR_ALL_GOOD)
        # Option: Debug time unit conversion exponent
        elif param == "--debug-time-unit":
            # No value for the option found...
            if i == len_passed_params - 1:
                ugen.err_Q(f"Expected value for '{param}'\n")
                sys.exit(uerr.ERR_MP_EXPECTED_VAL_FOR_OPT)
            val = passed_params[i + 1]
            if val == "ms":
                debug_time_expo = 6
            elif val == "us":
                debug_time_expo = 3
            elif val == "ns":
                debug_time_expo = 0
            elif val == "s":
                debug_time_expo = 9
            else:
                ugen.err_Q(f"Invalid value for '{param}': '{val}'\n")
                sys.exit(uerr.ERR_MP_INV_VAL)
            skip += 1
        else:
            ugen.err_Q(f"Unknown parameter: '{param}'\n")
            sys.exit(uerr.ERR_MP_UNK_TOK)

    return MainProgParsed(
        pre_ld_ext_cmds=pre_ld_ext_cmds,
        stdout_ansi=stdout_ansi,
        stderr_ansi=stderr_ansi,
        log_lvl=log_lvl,
        debug_time_expo=debug_time_expo
    )


def main() -> None:
    """
    """
    try:
        parsed_params = parse_argv(sys.argv[1 :])
        lgrs = ulog.init_lgrs(
            parsed_params.log_lvl,
            parsed_params.log_lvl,
            ulog.CRIT
        )
        ugen.set_lgrs(lgrs)
        cfg = cmgr.get_cfg()
        intrpr = ieng.Intrpr(
            cfg=cfg,
            pre_ld_ext_cmds=parsed_params.pre_ld_ext_cmds,
            stdout_ansi=parsed_params.stdout_ansi,
            stderr_ansi=parsed_params.stderr_ansi,
            debug_time_expo=parsed_params.debug_time_expo,
            log_lvl=parsed_params.log_lvl
        )
    except Exception as e:
        ugen.fatal_Q(
            f"During initialisation: {e.__class__.__name__}: {e}",
            uerr.ERR_UNK_FATAL,
            exc_txt=tb.format_exc()
        )

    while True:
        try:
            ugen.write(intrpr.reslv_prompt(intrpr.env_vars.get("_PROMPT_")))
            raw_ln = input()
            cmd_ret = intrpr.execute(raw_ln)
            intrpr.env_vars.set("_LAST_RET_", cmd_ret)
        # ^c on a built-in command
        except KeyboardInterrupt:
            intrpr.env_vars.set("_LAST_RET_", uerr.ERR_KEYBOARD_INTERR)
            print()
        # ^c on an external command
        except ugen.KeyboardInterruptWPrevileges as e:
            intrpr.env_vars.set("_LAST_RET_", uerr.ERR_KEYBOARD_INTERR)
            os.kill(e.child_pid, sig.SIGKILL)
            print()
        except EOFError:
            print()
            sys.exit(uerr.ERR_ALL_GOOD)
        except Exception as e:
            ugen.fatal_Q(
                f"In main interpreter loop: {e.__class__.__name__}: {e}",
                uerr.ERR_UNK_FATAL,
                exc_txt=tb.format_exc()
            )


if __name__ == "__main__":
    main()
    # x = inp()
