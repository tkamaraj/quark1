import utils.err_codes as uerr
import utils.gen as ugen
import intrpr.eng as ieng

HELP = ugen.HelpObj(
    usage="echo [flag ...] [opt ...] [str ...]",
    summary="Output text to standard output",
    details=(
        "ARGUMENTS",
        ("none", "Outputs nothing"),
        ("str", "String to be output on STDOUT"),
        "OPTIONS",
        ("-s sep", "Define separation string"),
        ("-e end", "Define terminal character"),
        "FLAGS",
        ("-T", "Kill terminal character")
    )
)

CMD_SPEC = ugen.CmdSpec(
    min_args=0,
    max_args=float("inf"),
    opts=("-s", "-e"),
    flags=("-T",)
)


def run(data: ugen.CmdData) -> int:
    err_code = uerr.ERR_ALL_GOOD
    sep_str = " "
    end_str = "\n"
    trailing = True

    for opt in data.opts:
        val = data.opts[opt]
        if opt == "-s":
            sep_str = val
        elif opt == "-e":
            end_str = val

    for flag in data.flags:
        if flag == "-T":
            trailing = not trailing

    ugen.write(sep_str.join(data.args) + (end_str if trailing else ""))
    return err_code

