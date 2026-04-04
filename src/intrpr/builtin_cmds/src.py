import math

import utils.err_codes as uerr
import utils.gen as ugen

HELP = ugen.HelpObj(
    usage="src fl [...]",
    summary="Run a script in the current process",
    details=(
        "ARGUMENTS",
        ("fl", "Script to run"),
        "OPTIONS",
        ("none", ""),
        "FLAGS",
        ("none", "")
    )
)

CMD_SPEC = ugen.CmdSpec(
    min_args=1,
    max_args=math.inf,
    opts=(),
    flags=()
)

ERR_FROM_CMD = 1000


def run(data: ugen.CmdData) -> int:
    for arg in data.args:
        try:
            with open(arg) as f:
                fl_cntnt = f.read()
        except FileNotFoundError:
            ugen.err(f"No such file/directory: \"{arg}\"")
            return uerr.ERR_FL_404
        except PermissionError:
            ugen.err(f"Access denied: \"{arg}\"")
            return uerr.ERR_PERM_DENIED
        except OSError:
            ugen.err(f"Invalid argument: \"{arg}\"")
            return uerr.ERR_INV_ARG

    err = uerr.ERR_ALL_GOOD
    for ln in fl_cntnt.splitlines():
        tmp = data.exec_fn(ln)
        err = err or tmp

    err_code = uerr.ERR_ALL_GOOD
    if err:
        err_code = ERR_FROM_CMD
    data.env_vars.set("_RN_CMD_RET_", err)
    return err_code
