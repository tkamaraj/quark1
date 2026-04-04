import os
import sys
import typing as ty

import utils.gen as ugen
import utils.err_codes as uerr

HELP = ugen.HelpObj(
    usage="exit [flag] [code]",
    summary="Exit the interpreter",
    details=(
        "ARGUMENTS",
        ("code", "Exit code to return to calling program"),
        "OPTIONS",
        ("none", ""),
        "FLAGS",
        ("-T, --no-exit-text", "Suppress exit text"),
    )
)

CMD_SPEC = ugen.CmdSpec(
    min_args=0,
    max_args=1,
    opts=(),
    flags=("-T")
)


def run(data: ugen.CmdData) -> ty.NoReturn | int:
    exit_code = uerr.ERR_ALL_GOOD
    exit_txt = "-T" not in data.flags and "--no-exit-text" not in data.flags

    if data.args:
        exit_code = data.args[0]
        try:
            exit_code = int(exit_code)
        except ValueError:
            ugen.err(f"Cannot cast to int: '{exit_code}'")
            return uerr.ERR_CANT_CAST_VAL
        except OverflowError:
            ugen.err(f"Integer overflow")
            return uerr.ERR_INT_OVERFLOW

    if exit_txt:
        ugen.write("bye\n")
    sys.exit(exit_code)
