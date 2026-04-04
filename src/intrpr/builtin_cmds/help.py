import math
import os
import typing as ty

import utils.consts as uconst
import utils.err_codes as uerr
import utils.gen as ugen

if ty.TYPE_CHECKING:
    import intrpr.cmd_reslvr as icres
    import intrpr.internals as iint

HELP = ugen.HelpObj(
    usage="help [cmd ...]",
    summary="Display help for commands",
    details=(
        "ARGUMENTS",
        ("none", "Display help summaries of built-in commands"),
        ("cmd", "Command to fetch help text for"),
        "OPTIONS",
        ("none", ""),
        "FLAGS",
        ("-a, --all", "Display help summaries of all recognised commands"),
        ("-e, --external", "Display help summaries of external commands"),
    )
)

CMD_SPEC = ugen.CmdSpec(
    min_args=0,
    max_args=math.inf,
    opts=(),
    flags=(
        "-a", "--all",
        "-e", "--external"
    )
)

ERR_NO_SUCH_CMD = 1000


class Out:
    def __init__(self, cmd: str, help_str: str, nl_after_cmd: bool) -> None:
        self.cmd = cmd
        self.help_str = help_str
        self.nl_after_cmd = nl_after_cmd


class Err:
    def __init__(self, msg: str, code: int) -> None:
        self.msg = msg
        self.code = code


def cons_detailed_help_str(
    help_obj: ugen.HelpObj,
    term_sz: os.terminal_size,
    is_tty: bool
) -> str:
    # TODO: Make the padding only depend on parameter names of the current
    # section, like separate padding amounts for "ARGUMENTS", "OPTIONS",
    # "FLAGS"
    details_str = []
    max_param_len = 0
    max_sgl_ln_param_len = 10
    tab = "\t".expandtabs(uconst.TAB_SZ)

    # To determine maximum length of arguments, options and flags
    for i in help_obj.details:
        if isinstance(i, str):
            continue
        # If the length of the parameter is longer than the maximum accepted
        # length for same-line printing, then it shouldn't accept the maximum
        # parameter length, which is used to determine padding for same-line
        # printing
        if len(i[0]) > max_sgl_ln_param_len:
            continue
        max_param_len = max(max_param_len, len(i[0]))

    for i in help_obj.details:
        nl = False
        # For heading like "ARGUMENTS", "OPTIONS", "FLAGS"...
        if isinstance(i, str):
            details_str.append(ugen.S.fmt(i, is_tty, ugen.S.magenta_4))
            continue
        if len(i[0]) > max_param_len:
            nl = True
        # Newline and same line mixed format detailed help strings
        clred_i0 = ugen.S.fmt(i[0], is_tty, ugen.S.blue_4)
        wrap_amt = term_sz.columns - len(2 * tab + max_param_len * " " + tab)
        string = [i[1][j : j + wrap_amt] for j in range(0, len(i[1]), wrap_amt)]
        full_ln = (
            tab
            + (clred_i0 if nl else (ugen.ljust(clred_i0, max_param_len) + tab))
            + (("\n" + 2 * tab + max_param_len * " " + tab) if nl else "")
            + ("\n" + 2 * tab + max_param_len * " " + tab).join(string)
        )
        details_str.append(full_ln)

    return (
        tab + help_obj.summary
        + "\n" + tab + ugen.S.fmt("USAGE", is_tty, ugen.S.magenta_4)
        + "\n" + tab * 2 + help_obj.usage
        + "\n" + tab
        + ("\n" + tab).join(details_str)
    )


def get_detailed_help(
    cmd_reslvr: "icres.CmdReslvr",
    ext_cached_cmds: dict[str, "iint.CmdCacheEntry"],
    pths: tuple[str, ...],
    args: tuple[str, ...],
    term_sz: os.terminal_size,
    is_tty: bool
) -> list[Out | Err]:
    op_buf: list[Out | Err]
    op_buf = []

    for cmd_nm in args:
        help_obj = cmd_reslvr.get_builtin_help(cmd_nm)
        if isinstance(help_obj, ugen.HelpObj):
            op_buf.append(
                Out(
                    ugen.S.fmt(cmd_nm, is_tty, ugen.S.green_4),
                    cons_detailed_help_str(help_obj, term_sz, is_tty),
                    nl_after_cmd=True
                )
            )
            continue

        help_obj = cmd_reslvr.get_ext_help(cmd_nm, ext_cached_cmds, pths)
        if isinstance(help_obj, ugen.HelpObj):
            op_buf.append(
                Out(
                    ugen.S.fmt(cmd_nm, is_tty, ugen.S.green_4),
                    cons_detailed_help_str(help_obj, term_sz, is_tty),
                    nl_after_cmd=True
                )
            )
            continue

        err_str = "Where's the error message?"
        if help_obj == uerr.ERR_BAD_CMD:
            err_str = f"No such command: '{cmd_nm}'"
        elif help_obj == uerr.ERR_NO_HELP_OBJ:
            err_str = f"No help object: '{cmd_nm}'"
        elif help_obj == uerr.ERR_INV_HELP_OBJ:
            err_str = f"Invalid help object: '{cmd_nm}'"
        elif help_obj == uerr.ERR_CANT_LD_CMD_MOD:
            err_str = f"Could not load command module: '{cmd_nm}'"
        op_buf.append(Err(err_str, help_obj))

    return op_buf


def run(data: ugen.CmdData) -> int:
    op_buf: list[Out | Err]

    err_code = uerr.ERR_ALL_GOOD
    cmd_reslvr = data.cmd_reslvr
    all_cmds = False
    ext_cmds = False

    for flag in data.flags:
        if flag in ("-a", "--all"):
            all_cmds = True
        elif flag in ("-e", "--external"):
            ext_cmds = True

    if (all_cmds or ext_cmds) and data.args:
        ugen.err("Cannot use all or external command flags for detailed help")
        return uerr.ERR_INV_USAGE
    if all_cmds and ext_cmds:
        ugen.err("Cannot use all and external command flags simultaneously")
        return uerr.ERR_INV_USAGE

    op_buf = []
    max_arg_len = 0

    if not data.args:
        # Either all commands or just built-in ones
        if all_cmds or not ext_cmds:
            # Run, run, RUNNNNN through the built-ins available
            for elem in cmd_reslvr.builtin_cmds:
                op_buf.append(Out(
                    ugen.S.fmt(elem, data.is_tty, ugen.S.green_4),
                    cmd_reslvr.get_builtin_help(elem).summary,
                    False
                ))
                max_arg_len = max(max_arg_len, len(elem))

        # Either all commands or just external ones
        if all_cmds or ext_cmds:
            cmd_nm_arr = []
            pths = data.env_vars.get("_PTH_")
            # Run, run, RUNNNNN through paths in the path variable
            for pth in pths:
                try:
                    for item in os.listdir(pth):
                        if not os.path.isfile(os.path.join(pth, item)):
                            continue
                        if not item.endswith(".py"):
                            continue
                        cmd_nm_arr.append(os.path.splitext(item)[0])
                except FileNotFoundError:
                    continue

            for cmd_nm in cmd_nm_arr:
                retd = cmd_reslvr.get_ext_help(
                    cmd_nm,
                    data.ext_cached_cmds,
                    pths
                )
                if isinstance(retd, int):
                    # If there was no help object (uerr.ERR_NO_HELP_OBJ), don't
                    # report, as this is the listing of all summaries
                    if retd == uerr.ERR_NO_HELP_OBJ:
                        pass
                    elif retd == uerr.ERR_INV_HELP_OBJ:
                        op_buf.append(Err(
                            f"Invalid help object: '{cmd_nm}'",
                            uerr.ERR_INV_HELP_OBJ
                        ))
                    elif retd == uerr.ERR_CANT_LD_CMD_MOD:
                        op_buf.append(Err(
                            f"Could not load command module: '{cmd_nm}'",
                            uerr.ERR_CANT_LD_CMD_MOD
                        ))
                    continue

                op_buf.append(Out(
                    ugen.S.fmt(cmd_nm, data.is_tty, ugen.S.green_4),
                    retd.summary,
                    nl_after_cmd=False
                ))
                max_arg_len = max(max_arg_len, len(cmd_nm))

    # Otherwise, print detailed help text for args
    else:
        op_buf.extend(get_detailed_help(
            cmd_reslvr,
            data.ext_cached_cmds,
            data.env_vars.get("_PTH_"),
            data.args,
            data.term_sz,
            data.is_tty
        ))

    # To compensate for the colon character when all command help listing
    # takes place. Is modified here because detailed command listing doesn't
    # need max_arg_len
    max_arg_len += 1
    # Finally, write output to STDOUT and STDERR
    for i in op_buf:
        if isinstance(i, Err):
            err_code = err_code or i.code
            ugen.err(i.msg)
            continue

        cmd_nm = i.cmd
        if not i.nl_after_cmd:
            cmd_nm = ugen.ljust((cmd_nm + ":"), max_arg_len)

        ugen.write(
            cmd_nm
            + ("\n" if i.nl_after_cmd else " ")
            + i.help_str
            + "\n"
        )

    return err_code
