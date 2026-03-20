import os
import typing as ty

import utils.gen as ugen
import utils.consts as uconst
import utils.err_codes as uerr

HELP = ugen.HelpObj(
    usage="set nm val",
    summary="Set an interpreter variable",
    details=(
        "ARGUMENTS",
        ("nm", "Variable name"),
        ("val", "Variable value"),
        "OPTIONS",
        ("none", ""),
        "FLAGS",
        ("none", "")
    )
)

CMD_SPEC = ugen.CmdSpec(
    min_args=2,
    max_args=2,
    opts=(),
    flags=()
)


def run(data: ugen.CmdData) -> int:
    err_code = uerr.ERR_ALL_GOOD
    var_nm = data.args[0]
    var_val = data.args[1]
    try:
        data.env_vars.set(var_nm, var_val)
    except ugen.InvVarTypErr:
        err_code = uerr.ERR_ENV_VAR_INV_TYP
        ugen.err("Invalid variable type for '{var_nm}': '{var_val.__name__}'")
    except ugen.InvVarNmErr:
        err_code = uerr.ERR_ENV_VAR_INV_NM
        ugen.err("Invalid variable name: '{var_nm}'")
    except ugen.UnkVarErr:
        err_code = uerr.ERR_ENV_UNK_VAR
        ugen.err("Unknown variable: '{var_nm}'")

    return err_code

