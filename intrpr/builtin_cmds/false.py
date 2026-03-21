import utils.err_codes as uerr
import utils.gen as ugen

HELP = ugen.HelpObj(
    usage="false",
    summary=f"Just returns {uerr.ERR_FALSE}",
    details=()
)

CMD_SPEC = ugen.CmdSpec(
    min_args=0,
    max_args=0,
    opts=(),
    flags=()
)


def run(data: ugen.CmdData) -> int:
    return uerr.ERR_FALSE

