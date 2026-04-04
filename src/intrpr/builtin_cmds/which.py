import math
import pathlib as pl
import pkgutil as pu
import types
import typing as ty

import utils.consts as uconst
import utils.gen as ugen
import utils.err_codes as uerr

HELP = ugen.HelpObj(
    usage="which [flag ...] cmd ...",
    summary="Display command locations",
    details=(
        "ARGUMENTS",
        ("cmd", "Command to locate"),
        "OPTIONS",
        ("none", ""),
        "FLAGS",
        ("-a", "Show all locations instead of just first hit"),
        ("-s", "Suppress command names in output")
    )
)

CMD_SPEC = ugen.CmdSpec(
    min_args=1,
    max_args=math.inf,
    opts=(), flags=("-a", "-s")
)

ERR_CANT_LOCATE_CMD = 1000


class Out:
    def __init__(self, cmd: str, pth: str) -> None:
        self.cmd = cmd
        self.pth = pth


class Err:
    def __init__(self, msg: str, code: int) -> None:
        self.msg = msg
        self.code = code


def is_valid_cmd_mod(mod: ty.Any) -> bool:
    if not isinstance(mod, types.ModuleType):
        return False

    try:
        return (
            callable(mod.run)
            and isinstance(mod.CMD_SPEC, ugen.CmdSpec)
            and isinstance(mod.HELP, ugen.HelpObj)
        )
    except AttributeError:
        return False


def run(data: ugen.CmdData) -> int:
    op_buf: list[Out | Err]

    err_code = uerr.ERR_ALL_GOOD
    dir_pths = data.env_vars.get("_PTH_")
    show_all = False
    short_op = False

    for flag in data.flags:
        if flag == "-a":
            show_all = True
        elif flag == "-s":
            short_op = True

    op_buf = []
    max_arg_len = 0

    for arg in data.args:
        op_arg_local_buf = []

        for mod_fl in pu.iter_modules([uconst.BUILTIN_PTH]):
            if mod_fl.name == "__init__":
                continue
            if mod_fl.name != arg:
                continue
            op_arg_local_buf.append(Out(arg, "built-in"))
            break

        # Show all option not given and one match has already been found in the
        # built-in commands
        if not show_all and op_arg_local_buf:
            max_arg_len = max(max_arg_len, len(arg))
            op_buf.extend(op_arg_local_buf)
            continue

        for dir_pth in dir_pths:
            mod = data.cmd_reslvr.ld_mod(arg, data.ext_cached_cmds, (dir_pth,))
            if not is_valid_cmd_mod(mod):
                continue

            dir_pth = pl.Path(dir_pth).expanduser().absolute()
            fl_pth = dir_pth / f"{arg}.py"
            op_arg_local_buf.append(Out(arg, str(fl_pth)))

            # If show all option is not given, break out after first hit
            if not show_all:
                break

        if op_arg_local_buf:
            max_arg_len = max(max_arg_len, len(arg))
            op_buf.extend(op_arg_local_buf)
        else:
            op_buf.append(
                Err(f"Cannot locate command: '{arg}'",
                    ERR_CANT_LOCATE_CMD)
            )

    # 1 to compensate for the colon character being added to write calls in the
    # following loop. Don't want to do that calculation everytime the loop
    # runs, and it looks ugly, too
    # 1 to compensate for the space to be inserted between the command name and
    # file path when short output flag is not given
    max_arg_len += 2
    for i in op_buf:
        if isinstance(i, Err):
            err_code = i.code
            ugen.err(i.msg)
            continue

        cmd_nm_w_spices = ugen.S.fmt(i.cmd, data.is_tty, ugen.S.green_4) + ':'
        ljustd = ugen.ljust(cmd_nm_w_spices, max_arg_len)
        ugen.write((ljustd if not short_op else "") + f"{i.pth}\n")

    return err_code
