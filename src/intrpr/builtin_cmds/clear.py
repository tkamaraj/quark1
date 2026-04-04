import utils.err_codes as uerr
import utils.gen as ugen

HELP = ugen.HelpObj(
    usage="clear",
    summary="Clear the terminal screen",
    details=(
        "ARGUMENTS",
        ("none", ""),
        "OPTIONS",
        ("none", ""),
        "FLAGS",
        ("-k, --keep-scrollback", "Keep the scrollback buffer")
    )
)

CMD_SPEC = ugen.CmdSpec(
    min_args=0,
    max_args=0,
    opts=(),
    flags=("-k", "--keep-scrollback")
)

MV_CUR_TO_HOME_POS = "\x1b[H"
ERASE_SCR = "\x1b[2J"
ERASE_SAVED_LNS = "\x1b[3J"


def run(data: ugen.CmdSpec) -> int:
    err_code = uerr.ERR_ALL_GOOD
    keep_scrollback = "-k" in data.flags or "--keep-scrollback" in data.flags

    ugen.write(
        MV_CUR_TO_HOME_POS
        + ERASE_SCR
        + (ERASE_SAVED_LNS if not keep_scrollback else "")
    )
    return err_code
