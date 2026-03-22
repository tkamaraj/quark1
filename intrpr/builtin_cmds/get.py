import math
import os
import typing as ty

import utils.gen as ugen
import utils.consts as uconst
import utils.err_codes as uerr

HELP = ugen.HelpObj(
    usage="get [nm ...]",
    summary="Get an interpreter variable",
    details=(
        "ARGUMENTS",
        ("nm", "Variable name"),
        "OPTIONS",
        ("none", ""),
        "FLAGS",
        ("none", "")
    )
)

CMD_SPEC = ugen.CmdSpec(
    min_args=0,
    max_args=math.inf,
    opts=(),
    flags=()
)


def run(data: ugen.CmdData) -> int:
    err_code = uerr.ERR_ALL_GOOD
    max_nm_len = 0

    if not data.args:
        for var in data.env_vars:
            max_nm_len = max(max_nm_len, len(var.nm))

        for var in data.env_vars:
            ugen.write(
                ugen.ljust(ugen.S.fmt(var.nm, data.is_tty, ugen.S.green),
                           max_nm_len)
                + " = "
                + repr(var.val)
                + "\n"
            )

    # This is needed here, with the get statement, to prevent unknown variable
    # names influencing padding
    for arg in data.args:
        try:
            data.env_vars.get(arg)
            max_nm_len = max(max_nm_len, len(arg))
        except ugen.UnkVarErr:
            pass

    for arg in data.args:
        try:
            var_val = data.env_vars.get(arg)
            ugen.write(
                ugen.ljust(ugen.S.fmt(arg, data.is_tty, ugen.S.green),
                           max_nm_len)
                + " = "
                + repr(var_val)
                + "\n"
            )
        except ugen.UnkVarErr:
            err_code = err_code or uerr.ERR_ENV_UNK_VAR
            ugen.err(f"Unknown variable: '{arg}'")

    return err_code

