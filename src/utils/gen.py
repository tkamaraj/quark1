import os
import pathlib as pl
import re
import sys
import types
import typing as ty

import utils.consts as uconst
import utils.loggers as ulog

if ty.TYPE_CHECKING:
    import intrpr.cmd_reslvr as icrsr
    import intrpr.internals as iint


class LogicalErr(Exception):
    pass


class KeyboardInterruptWPrevileges(Exception):
    def __init__(self, msg: str, child_pid: int) -> None:
        super().__init__(msg)
        self.child_pid = child_pid


class InvVarTypErr(Exception):
    def __init__(self, var_nm: str, var_typ: type, got_typ: type,
                 *args, **kwargs):
        self.var_nm = var_nm
        self.var_typ = var_typ
        self.got_typ = got_typ


class InvVarNmErr(Exception):
    def __init__(self, var_nm: str, *args, **kwargs):
        self.var_nm = var_nm


class UnkVarErr(Exception):
    def __init__(self, var_nm: str, *args, **kwargs):
        self.var_nm = var_nm


class CmdData(ty.NamedTuple):
    cmd_nm: str
    args: tuple[str, ...]
    opts: dict[str, str]
    flags: tuple[str, ...]
    cmd_reslvr: "icrsr.CmdReslvr"
    env_vars: "iint.Env"
    ext_cached_cmds: dict[str, "iint.CmdCacheEntry"]
    term_sz: os.terminal_size
    is_tty: bool
    stdin: str | None
    exec_fn: ty.Callable[["ieng.Intrpr", str], int | ty.NoReturn]
    operation: str = ""


class CmdSpec(ty.NamedTuple):
    min_args: int
    max_args: int | float
    opts: tuple[str, ...]
    flags: tuple[str, ...]


class HelpObj(ty.NamedTuple):
    usage: str
    summary: str
    details: tuple[str | tuple[str, ...], ...]


class Path:
    def __init__(self, pth: str) -> None:
        self.pth = os.path.expanduser(pth)
        self.abs_pth = os.path.abspath(self.pth)
        self.reslvd_pth = os.path.realpath(self.abs_pth)

    def join_pth(self, pth2: str) -> pl.Path:
        return pl.Path(os.path.join(self.abs_pth, pth2))

    def exists(self) -> bool:
        return os.path.exists(self.reslvd_pth)


class WrapGeneratorToStealReturn:
    def __init__(self, gen: ty.Generator[ty.Any, ty.Any, ty.Any]) -> None:
        self.gen = gen
        self.val = None

    def __iter__(self) -> ty.Generator[ty.Any, ty.Any, ty.Any]:
        self.val = yield from self.gen
        return self.val


class StyleObj:
    """
    Style object to apply formatting to text objects.
    """
    reset = "\x1b[0m"
    bold = "\x1b[1m"

    red_4 = "\x1b[31m"
    green_4 = "\x1b[32m"
    yellow_4 = "\x1b[33m"
    blue_4 = "\x1b[34m"
    magenta_4 = "\x1b[35m"
    cyan_4 = "\x1b[36m"

    green_bg_8 = "\x1b[48;5;22m"
    magenta_bg_8 = "\x1b[48;5;55m"
    white_bg_8 = "\x1b[48;5;248m"
    black_fg_8 = "\x1b[38;5;0m"

    def fmt(self, string: str, apply_fmting: bool, *args: str) -> str:
        return (
            ("".join(args) + string + self.reset) if apply_fmting else string
        )


def ljust(string: str, amt: int) -> str:
    return string.ljust(amt + len(string) - len(rm_ansi("", string)))


def rjust(string: str, amt: int) -> str:
    return string.rjust(amt + len(string) - len(rm_ansi("", string)))


def set_lgrs(lgrs) -> None:
    global _lgrs
    _lgrs = lgrs


def write(s: str, flush: bool = True) -> None:
    sys.stdout.write(s)
    sys.stdout.flush() if flush else None


def fatal(msg: str, ret: int, exc_txt: str | None = None) -> ty.NoReturn:
    """
    Reports a fatal error.

    :param msg: The message
    :type msg: str

    :param ret: Return code for the calling program
    :type ret: int

    :returns: Error code
    :rtype: int
    """
    _lgrs.lgr_c.fatal(msg)
    _lgrs.fl_lgr.fatal(msg if exc_txt is None else exc_txt)
    sys.exit(ret)


def fatal_Q(msg: str, ret: int, exc_txt: str | None = None) -> ty.NoReturn:
    """
    Reports a fatal interpreter error.

    :param msg: The message
    :type msg: str

    :param ret: Return code for the calling program
    :type ret: int

    :returns: Error code
    :rtype: int
    """
    _lgrs.lgr_q.fatal(msg)
    _lgrs.fl_lgr.fatal(msg if exc_txt is None else exc_txt)
    sys.exit(ret)


def crit(msg: str) -> None:
    """
    Reports a critical error.

    :param msg: The message
    :type msg: str

    :param ret: The return code to pass on
    :type ret: int
    """
    _lgrs.lgr_c.critical(msg)
    _lgrs.fl_lgr.critical(msg)


def crit_Q(msg: str) -> None:
    """
    Reports a critical interpreter error.

    :param msg: The message
    :type msg: str

    :param ret: The return code to pass on
    :type ret: int
    :rtype: int
    """
    _lgrs.lgr_q.critical(msg)
    _lgrs.fl_lgr.critical(msg)


def err(msg: str) -> None:
    """
    Reports an error.

    :param msg: The message
    :type msg: str

    :param ret: The return code to pass on
    :type ret: int
    """
    _lgrs.lgr_c.error(msg)
    _lgrs.fl_lgr.error(msg)


def err_Q(msg: str) -> None:
    """
    Reports an interpreter error.

    :param msg: The message
    :type msg: str

    :param ret: The return code to pass on
    :type ret: int
    """
    # To output to STDERR before the initialisation of loggers
    if _lgrs is not None:
        _lgrs.lgr_q.error(msg)
        _lgrs.fl_lgr.error(msg)
    else:
        sys.stderr.write(
            uconst.ANSI_BOLD_RED
            + "EQ:" 
            + uconst.ANSI_RESET
            + " "
            + msg
        )
        sys.stderr.flush()


def warn(msg: str) -> None:
    _lgrs.lgr_c.warning(msg)
    _lgrs.fl_lgr.warning(msg)


def warn_Q(msg: str) -> None:
    _lgrs.lgr_q.warning(msg)
    _lgrs.fl_lgr.warning(msg)


def info(msg: str) -> None:
    """
    Displays a message.

    :param msg: The message
    :type msg: str
    """
    _lgrs.lgr_c.info(msg)
    _lgrs.fl_lgr.info(msg)


def info_Q(msg: str) -> None:
    """
    Displays an interpreter message.

    :param msg: The message
    :type msg: str
    """
    _lgrs.lgr_q.info(msg)
    _lgrs.fl_lgr.info(msg)


def debug(msg: str) -> None:
    """
    Displays a debug message.

    :param msg: The message
    :type msg: str
    """
    _lgrs.lgr_c.debug(msg)
    _lgrs.fl_lgr.debug(msg)


def debug_Q(msg: str) -> None:
    """
    Displays an interpreter debug message.

    :param msg: The message
    :type msg: str
    """
    _lgrs.lgr_q.debug(msg)
    _lgrs.fl_lgr.debug(msg)


def fmt_d_stmt(src: str, lhs: str, rhs: str | None = None, pad: int = 24) \
        -> str:
    full_str = f"[{src}] {lhs}".ljust(pad)
    if rhs:
        full_str += f"-> {rhs}"
    return full_str


def transpose(arr: ty.Iterable) -> ty.Iterable:
    pass


rm_ansi = re.compile(r"""
    \x1b      # Literal ESC
    \[        # Literal [
    [;\d]*    # Zero or more digits or semicolons
    [A-Za-z]  # An alphabet
""", re.VERBOSE).sub
_lgrs = None
S = StyleObj()

