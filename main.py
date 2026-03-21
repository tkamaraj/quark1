import logging as lg
import sys
import traceback as tb
import typing as ty

import intrpr.eng as ieng
import intrpr.cfg_mgr as cmgr
import utils.err_codes as uerr
import utils.gen as ugen
import utils.loggers as ulog

HELP_TXT = f"""USAGE
\t{sys.argv[0]} [flag ...]
ARGUMENTS
\tnone
OPTIONS
\tnone
FLAGS
\t-d    Enable debugging mode
\t-e    Load all external commands on startup
""".expandtabs(2)

class MainProgParsed(ty.NamedTuple):
    pre_ld_ext_cmds: bool
    log_lvl: int
    debug_time_expo: int


def parse_argv(passed_toks: list[str]) -> MainProgParsed:
    """
    Parse tokens passed to the main program.

    :returns: An object that contains all the data that can be received from
              the arguments, options and flags that can be provided to the main
              program.
    :rtype: MainProgParsed
    """
    len_passed_toks = len(passed_toks)
    skip = 0

    pre_ld_ext_cmds = False
    log_lvl = ulog.WARN
    debug_time_expo = 6

    for i, tok in enumerate(passed_toks):
        if skip:
            skip -= 1
            continue

        # Flag: preload external commands
        if tok == "-e":
            pre_ld_ext_cmds = True
        # Flag: Show debug
        elif tok == "-d":
            log_lvl = ulog.DEBUG
        # Flag: Show info
        elif tok == "-i":
            log_lvl = ulog.INFO
        # Flag: No warnings
        elif tok == "-W":
            if log_lvl <= ulog.WARN:
                log_lvl = ulog.ERR
        elif tok == "-h" or tok == "--help":
            ugen.write(HELP_TXT)
            sys.exit(uerr.ERR_ALL_GOOD)
        # Option: Debug time unit conversion exponent
        elif tok == "--debug-time-unit":
            # No value for the option found...
            if i == len_passed_toks - 1:
                ugen.err_Q(f"Expected value for '{tok}'\n")
                sys.exit(uerr.ERR_MP_EXPECTED_VAL_FOR_OPT)
            val = passed_toks[i + 1]
            if val == "ms":
                debug_time_expo = 6
            elif val == "us":
                debug_time_expo = 3
            elif val == "ns":
                debug_time_expo = 0
            elif val == "s":
                debug_time_expo = 9
            else:
                ugen.err_Q(f"Invalid value for '{tok}': '{val}'\n")
                sys.exit(uerr.ERR_MP_INV_VAL)
            skip += 1
        else:
            ugen.err_Q(f"Unknown token: '{tok}'\n")
            sys.exit(uerr.ERR_MP_UNK_TOK)

    return MainProgParsed(
        pre_ld_ext_cmds=pre_ld_ext_cmds,
        log_lvl=log_lvl,
        debug_time_expo=debug_time_expo
    )


def main() -> None:
    try:
        passed_toks = sys.argv[1 :]
        parsed_argv = parse_argv(passed_toks)
        lgrs = ulog.init_lgrs(parsed_argv.log_lvl,
                              parsed_argv.log_lvl,
                              ulog.CRIT)
        ugen.set_lgrs(lgrs)
        cfg = cmgr.get_cfg()
        intrpr = ieng.Intrpr(
            cfg=cfg,
            pre_ld_ext_cmds=parsed_argv.pre_ld_ext_cmds,
            debug_time_expo=parsed_argv.debug_time_expo,
            log_lvl=parsed_argv.log_lvl
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
        except KeyboardInterrupt:
            intrpr.env_vars.set("_LAST_RET_", uerr.ERR_KEYBOARD_INTERR)
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

