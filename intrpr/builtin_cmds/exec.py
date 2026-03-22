import math
import traceback as tb

import utils.err_codes as uerr
import utils.gen as ugen

HELP = ugen.HelpObj(
    usage="exec str [...]",
    summary="Execute strings in the Python interpreter",
    details=(
        "ARGUMENTS",
        ("str", "The string to be executed in the Python interpreter")
    )
)

CMD_SPEC = ugen.CmdSpec(
    min_args=1,
    max_args=math.inf,
    opts=(),
    flags=()
)

ERR_EXEC_ERR = 1000


def run(data: ugen.CmdData) -> int:
    err_code = uerr.ERR_ALL_GOOD

    for i in data.args:
        try:
            exec(i)
        except Exception as e:
            exc = tb.format_exception(e)
            err_code = err_code or ERR_EXEC_ERR
            ugen.err(f"{e.__class__.__name__}: {e}\n{''.join(exc)}")

    return err_code
