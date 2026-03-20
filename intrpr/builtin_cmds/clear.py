import utils.err_codes as uerr
import utils.gen as ugen

HELP = ugen.HelpObj(
    usage="clear",
    summary="Clears the terminal screen",
    details=(
        "ARGUMENTS",
        "\t<none>",
        "\t\tClears the terminal"
    )
)

CMD_SPEC = ugen.CmdSpec(
    min_args=0,
    max_args=0,
    opts=(),
    flags=()
)

CLEAR_SCR = "\033[2J"
MV_CUR_TO_TOP = "\033[H"


def run(data: ugen.CmdSpec) -> int:
    err_code = uerr.ERR_ALL_GOOD
    ugen.write(CLEAR_SCR + MV_CUR_TO_TOP)
    return err_code

