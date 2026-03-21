import logging as lg
import os
import typing as ty

import utils.consts as uconst

DEBUG = lg.DEBUG
INFO = lg.INFO
WARN = lg.WARNING
ERR = lg.ERROR
CRIT = lg.CRITICAL
FATAL = 60
LOG_FL = os.path.join(uconst.RUN_PTH, "quark.log")


class QuarkLogger(lg.getLoggerClass()):
    """
    Custom logger extending the logging.Logger class to add separate
    functionality to the FATAL log level.
    """

    def __init__(self, name: str, level: int | str = lg.NOTSET) -> None:
        super().__init__(name, level)
        lg.addLevelName(FATAL, "FATAL")

    def fatal(self, msg: str, *args: ty.Any, **kwargs: ty.Any) -> None:
        if self.isEnabledFor(FATAL):
            self._log(FATAL, msg, args, **kwargs)


class QuarkFormatter(lg.Formatter):
    """
    Apply custom formatting to the log message.
    """
    def __init__(
            self,
            fmt: str | None = None,
            datefmt: str | None = None,
            style: ty.Literal["%"] | ty.Literal["{"] | ty.Literal["$"] = "%",
            validate: bool = True,
            *,
            defaults: ty.Mapping[str, ty.Any] | None = None,
        ) -> None:
        self.log_lvl_chrs = {
            DEBUG: "D",
            INFO: "I",
            WARN: "W",
            ERR: "E",
            CRIT: "C",
            FATAL: "F",
        }
        super().__init__(fmt, datefmt, style, validate, defaults=defaults)

    def format(self, record: lg.LogRecord) -> str:
        src = ""
        if record.name.endswith("LGR_Q"):
            src = "Q"

        prefix_chrs = self.log_lvl_chrs[record.levelno] + src +  ":"

        if record.levelno >= ERR:
            record.clred_prefix_chrs = uconst.ANSI_BOLD_RED \
                + prefix_chrs \
                + uconst.ANSI_RESET
        elif record.levelno >= WARN:
            record.clred_prefix_chrs = uconst.ANSI_BOLD_YELLOW \
                + prefix_chrs \
                + uconst.ANSI_RESET
        else:
            record.clred_prefix_chrs = uconst.ANSI_BOLD \
                + prefix_chrs \
                + uconst.ANSI_RESET
        return super().format(record)


class AllLgrs(ty.NamedTuple):
    lgr: lg.Logger
    lgr_c: lg.Logger
    lgr_q: lg.Logger
    fl_lgr: lg.Logger

    def __iter__(self):
        for i in (self.lgr, self.lgr_c, self.lgr_q, self.fl_lgr):
            yield i


def init_lgrs(
        log_lvl_c: int,
        log_lvl_q: int,
        log_lvl_fl: int
    ) -> AllLgrs:
    """
    Initialise the logging components and the logger.
    1. cn_fatal_q_lgr handles the console logging of fatal and lesser errors
       originating from Quark itself;
    2. cn_fatal_lgr handles the console logging of fatal and lesser errors
       originating from other sources;
    3. cn_info_q_lgr handles the console logging of info and lesser
       messages originating from Quark itself;
    4. cn_info_lgr handles the console logging of info and lesser messages
       from other sources;
    5. fl_lgr handles the logging to the log file.
    I hate this function. I really fucking hate this function.

    :returns: Collection of Logger objects after application of formatting
              rules and addition of handlers
    :rtype: AllLgrs
    """
    lg.captureWarnings(True)
    lg.setLoggerClass(QuarkLogger)

    # Create the loggers
    lgr = lg.getLogger(__name__)
    lgr_c = lgr.getChild("LGR_C")
    lgr_q = lgr.getChild("LGR_Q")
    fl_lgr = lgr.getChild("FL")

    # Define the format strings
    lgr_c_fmt_str = (
        f"%(clred_prefix_chrs)s %(message)s"
    )
    lgr_q_fmt_str = (
        f"%(clred_prefix_chrs)s %(message)s"
    )
    fl_fmt_str = (
        "[%(asctime)s.%(msecs)03d]\n"
        "%(levelname)s:%(module)s:%(funcName)s:\n"
        "%(message)s\n"
        "--------"
    )

    # Create formatters
    lgr_c_fmter = QuarkFormatter(fmt=lgr_c_fmt_str)
    lgr_q_fmter = QuarkFormatter(fmt=lgr_q_fmt_str)
    fl_fmter = QuarkFormatter(
        fmt=fl_fmt_str,
        datefmt="%z/%d-%m-%Y/%H:%M:%S"
    )

    # Create handlers
    lgr_c_hdlr = lg.StreamHandler()
    lgr_q_hdlr = lg.StreamHandler()
    fl_hdlr = lg.FileHandler(LOG_FL, "a", encoding="utf-8")

    # Add formatters to handlers
    lgr_c_hdlr.setFormatter(lgr_c_fmter)
    lgr_q_hdlr.setFormatter(lgr_q_fmter)
    fl_hdlr.setFormatter(fl_fmter)

    # Set log levels
    lgr_c.setLevel(log_lvl_c)
    lgr_q.setLevel(log_lvl_q)
    fl_lgr.setLevel(log_lvl_fl)

    # Add handlers to loggers
    lgr_c.addHandler(lgr_c_hdlr)
    lgr_q.addHandler(lgr_q_hdlr)
    fl_lgr.addHandler(fl_hdlr)

    return AllLgrs(lgr, lgr_c, lgr_q, fl_lgr)

