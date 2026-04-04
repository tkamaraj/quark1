import os

import utils.err_codes as uerr
import utils.gen as ugen

HELP = ugen.HelpObj(
    usage="pwd",
    summary="Print the current working directory",
    details=(
        "ARGUMENTS",
        ("none", ""),
        "OPTIONS",
        ("none", ""),
        "FLAGS",
        ("none", "")
    )
)

CMD_SPEC = ugen.CmdSpec(
    min_args=0,
    max_args=0,
    opts=(),
    flags=()
)


def run(data: ugen.CmdData) -> int:
    err_code = uerr.ERR_ALL_GOOD

    try:
        ugen.write(os.getcwd() + "\n")
    # Don't know if this is possible... but just in case
    except PermissionError:
        err_code = uerr.ERR_PERM_DENIED
        ugen.err("Access denied")

    return err_code

