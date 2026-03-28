import ast
import builtins
import os
import typing as ty

import utils.gen as ugen
import utils.consts as uconst
import utils.err_codes as uerr

HELP = ugen.HelpObj(
    usage="set nm val [typ]",
    summary="Set an interpreter variable",
    details=(
        "ARGUMENTS",
        ("nm", "Variable name"),
        ("val", "Variable value"),
        ("typ", "Variable type (Python built-in type)"),
        "OPTIONS",
        ("none", ""),
        "FLAGS",
        ("none", "")
    )
)

CMD_SPEC = ugen.CmdSpec(
    min_args=2,
    max_args=3,
    opts=(),
    flags=()
)

ERR_NO_SUCH_TYP_IN_BUILTINS = 1000
ERR_INV_VAL_FOR_TYP = 1001


class NoTypSpecified:
    pass


def run(data: ugen.CmdData) -> int:
    err_code = uerr.ERR_ALL_GOOD
    var_nm = data.args[0]
    var_val = data.args[1]
    var_typ = data.args[2] if len(data.args) == 3 else NoTypSpecified()

    if not isinstance(var_typ, NoTypSpecified):
        for nm, obj in vars(builtins).items():
            if nm == var_typ:
                var_obj = obj
                found = True
                break
        else:
            ugen.err(f"No such type in scope: '{var_typ}'")
            return ERR_NO_SUCH_TYP_IN_BUILTINS

        # There's a problem with this code segment. What happens is that
        # ast.literal_eval raises a ValueError when trying to evaluate a string
        # literal. Like, say this: `set _PTH_ foo str`. This raises a
        # ValueError, and thus control falls into the except block, which
        # produces a misleading error message, even though the value was
        # perfectly OK
        # OK, I checked, and you need quotes around the literal to be evaluated
        # as a string. Not quotes in the interpreter raw input line. Escaped
        # quotes.
        # TODO: Check and resolve this
        try:
            var_val = var_obj(ast.literal_eval(var_val))
        except ValueError:
            ugen.err(f"Invalid value for type '{var_typ}': '{var_val}'")
            return ERR_INV_VAL_FOR_TYP

    try:
        data.env_vars.set(var_nm, var_val)
    except ugen.InvVarTypErr:
        err_code = uerr.ERR_ENV_VAR_INV_TYP
        ugen.err(
            f"Invalid variable value type for '{var_nm}': '{var_val.__class__.__name__}'"
        )
    except ugen.InvVarNmErr:
        err_code = uerr.ERR_ENV_VAR_INV_NM
        ugen.err(f"Invalid variable name: '{var_nm}'")
    except ugen.UnkVarErr:
        err_code = uerr.ERR_ENV_UNK_VAR
        ugen.err(f"Unknown variable: '{var_nm}'")

    return err_code
