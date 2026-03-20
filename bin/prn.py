import math
import pathlib as pl

import utils.err_codes as uerr
import utils.gen as ugen

HELP = ugen.HelpObj(
    usage="prn fl ...",
    summary="Dump file content",
    details=(
        "ARGUMENTS",
        ("fl", "File to dump")
    )
)

CMD_SPEC = ugen.CmdSpec(
    min_args=1,
    max_args=math.inf,
    opts=(),
    flags=()
)


def run(data: ugen.CmdData) -> int:
    err_code = uerr.ERR_ALL_GOOD

    for arg in data.args:
        fl = pl.Path(arg).resolve()
        try:
            with open(fl) as f:
                fl_cntnt = f.read()
        except FileNotFoundError:
            ugen.err(f"No such file: \"{arg}\"")
            err_code = err_code or uerr.ERR_FL_404
            continue
        except PermissionError:
            ugen.err(f"Access denied: \"{arg}\"")
            err_code = err_code or uerr.ERR_PERM_DENIED
            continue
        except OSError:
            ugen.err(f"Invalid argument: \"{arg}\"")
            err_code = err_code or uerr.ERR_INV_ARG
            continue
        except Exception as e:
            ugen.err(f"Unknown error when loading file: \"{arg}\"")
            err_code = err_code or err.ERR_UNK_ERR
            continue

        ugen.write(ugen.S.fmt(arg, data.is_tty, ugen.S.green) + "\n"
                   + fl_cntnt)

    return err_code

