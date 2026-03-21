import utils.err_codes as uerr
import utils.gen as ugen

HELP = ugen.HelpObj(
    usage="true",
    summary=f"Just returns {uerr.ERR_ALL_GOOD}",
    details=()
)

CMD_SPEC = ugen.CmdSpec(
    min_args=0,
    max_args=0,
    opts=(),
    flags=()
)


def run(data: ugen.CmdData) -> int:
    return uerr.ERR_ALL_GOOD

