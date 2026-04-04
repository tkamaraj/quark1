import os
import pwd

import utils.err_codes as uerr
import utils.gen as ugen

HELP = ugen.HelpObj(
    usage="whoami",
    summary="Display current username",
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
    flags=("-i", "-a")
)


def run(data: ugen.CmdData) -> int:
    err_code = uerr.ERR_ALL_GOOD
    show_uid = False
    show_usernm = True

    for flag in data.flags:
        if flag == "-i":
            show_uid = True
            show_usernm = False
        elif flag == "-a":
            show_uid = True
            show_usernm = True

    uid = os.getuid()

    if show_uid and show_usernm:
        usernm = pwd.getpwuid(uid).pw_name
        ugen.write(f"{uid}: {usernm}\n")
    elif show_usernm:
        usernm = pwd.getpwuid(uid).pw_name
        ugen.write(f"{usernm}\n")
    elif show_uid:
        ugen.write(f"{uid}\n")

    return err_code

