import utils.err_codes as uerr
import utils.gen as ugen

HELP = ugen.HelpObj(
    usage="",
    summary="",
    details=()
)

CMD_SPEC = ugen.CmdSpec(
    min_args=0,
    max_args=0,
    opts=(),
    flags=()
)


def run(data: ugen.CmdData) -> int:
    ugen.write(data.stdin)
    return uerr.ERR_ALL_GOOD
