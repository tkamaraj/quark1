import math
import os
import pathlib as pl
import re
import sys

import utils.err_codes as uerr
import utils.gen as ugen

HELP = ugen.HelpObj(
    usage="cnt [flag ...] [fl ...] [STDIN]",
    summary="Count text objects",
    details=(
        "ARGUMENTS",
        ("fl", "Filename to read"),
        "OPTIONS",
        ("none", ""),
        "FLAGS",
        ("-N", "Include newlines in character count"),
        ("-p", "Include punctuation in word boundaries"),
        ("-b", "Count bytes (only files)"),
        ("-c", "Count characters"),
        ("-w", "Count words"),
        ("-l", "Count lines")
    )
)

CMD_SPEC = ugen.CmdSpec(
    min_args=0,
    max_args=math.inf,
    opts=(),
    flags=("-N", "-p", "-b", "-c", "-w", "-l")
)


class Out:
    def __init__(self, fl_nm: str, fl_sz: str, fl_chrs: int, fl_words: int,
                 fl_lns: int) -> None:
        self.fl_nm = fl_nm
        self.fl_sz = fl_sz
        self.fl_chrs = fl_chrs
        self.fl_words = fl_words
        self.fl_lns = fl_lns


class Err:
    def __init__(self, msg: str, code: int) -> None:
        self.msg = msg
        self.code = code


def ld_fl(fl_nm: str) -> tuple[int, str] | Err:
    fl_nm = pl.Path(fl_nm).expanduser().absolute().resolve()
    try:
        with open(fl_nm) as f:
            fl_cntnt = f.read()
        # Bytes
        fl_sz = pl.Path(fl_nm).stat().st_size
    except FileNotFoundError:
        return Err(f"No such file: \"{fl_nm}\"", uerr.ERR_FL_404)
    except PermissionError:
        return Err(f"Access denied: \"{fl_nm}\"", uerr.ERR_PERM_DENIED)
    except UnicodeDecodeError:
        return Err(f"Does not appear to contain text: \"{fl_nm}\"",
                   uerr.ERR_DECODE_ERR)
    except Exception:
        return Err(f"Unknown error ({e.__class__.__name__}): \"{fl_nm}\"",
                   uerr.ERR_UNK_ERR)

    return (str(fl_sz), fl_cntnt)


def get_txt_obj_cnt(txt: str, words_sepd_by_ws: bool, incl_nls_in_chrs: bool,
                    alpha_patt: re.Pattern) -> tuple[int, int, int]:
    # Lines
    lns = txt.count("\n")
    # Words
    if words_sepd_by_ws:
        words = len(txt.split())
    else:
        words = len(re.findall(alpha_patt, txt))
    # Characters
    if incl_nls_in_chrs:
        chrs = len(txt)
    else:
        chrs = len(txt.replace("\n", ""))

    return (str(lns), str(words), str(chrs))


def run(data: ugen.CmdData) -> int:
    err_code = uerr.ERR_ALL_GOOD
    incl_nls_in_chrs = True
    words_sepd_by_ws = True
    show_bytes = False
    show_chrs = False
    show_words = False
    show_lns = False
    alpha_patt = re.compile(r"[A-Za-z0-9]+")
    op_buf = []
    max_arg_len = 0
    max_fl_sz_len = 0
    max_fl_chrs_len = 0
    max_fl_words_len = 0
    max_fl_lns_len = 0

    for flag in data.flags:
        # Do not include newline characters in character count
        if flag == "-N":
            incl_nls_in_chrs = False
        # Include punctuation in word boundaries
        elif flag == "-p":
            words_sepd_by_ws = False
        # Filtering option: bytes
        elif flag == "-b":
            show_bytes = True
        # Filtering option: characters
        elif flag == "-c":
            show_chrs = True
        # Filtering option: words
        elif flag == "-w":
            show_words = True
        # Filtering option: lines
        elif flag == "-l":
            show_lns = True

    # No filtering option given, thus show all
    if not (show_bytes or show_chrs or show_words or show_lns):
        show_bytes = True
        show_chrs = True
        show_words = True
        show_lns = True

    # If input is available in STDIN
    if data.stdin is not None:
        in_lns, in_words, in_chrs = get_txt_obj_cnt(data.stdin,
                                                    words_sepd_by_ws,
                                                    incl_nls_in_chrs,
                                                    alpha_patt)

        # len("STDIN") is 5
        max_arg_len = max(max_arg_len, 5)
        max_fl_chrs_len = max(max_fl_chrs_len, len(in_chrs))
        max_fl_words_len = max(max_fl_words_len, len(in_words))
        max_fl_lns_len = max(max_fl_lns_len, len(in_lns))

        op_buf.append(Out("STDIN", "-", in_chrs, in_words, in_lns))

    # Go through arguments, which will considered filenames
    for arg in data.args:
        res = ld_fl(arg)
        if isinstance(res, Err):
            op_buf.append(res)
            continue

        fl_sz, fl_cntnt = res
        fl_lns, fl_words, fl_chrs = get_txt_obj_cnt(fl_cntnt,
                                                    words_sepd_by_ws,
                                                    incl_nls_in_chrs,
                                                    alpha_patt)

        max_arg_len = max(max_arg_len, len(arg))
        max_fl_sz_len = max(max_fl_sz_len, len(fl_sz))
        max_fl_chrs_len = max(max_fl_chrs_len, len(fl_chrs))
        max_fl_words_len = max(max_fl_words_len, len(fl_words))
        max_fl_lns_len = max(max_fl_lns_len, len(fl_lns))

        op_buf.append(
            Out(arg, fl_sz, fl_chrs, fl_words, fl_lns)
        )

    # 1 to account for the colon at the end of the filename
    max_arg_len += 1
    for i in op_buf:
        if isinstance(i, Err):
            err_code = err_code or i.code
            ugen.err(i.msg)
            continue

        fl_sz_fmted = ugen.ljust(i.fl_sz, max_fl_sz_len)
        fl_chrs_fmted = ugen.ljust(i.fl_chrs, max_fl_chrs_len)
        fl_words_fmted = ugen.ljust(i.fl_words, max_fl_words_len)
        fl_lns_fmted = ugen.ljust(i.fl_lns, max_fl_lns_len)
        ugen.write(
            ugen.ljust(ugen.S.fmt(i.fl_nm, data.is_tty, ugen.S.green) + ":",
                       max_arg_len)
            + ((f" b:" + fl_sz_fmted) if show_bytes else "")
            + ((f" c:" + fl_chrs_fmted) if show_chrs else "")
            + ((f" w:" + fl_words_fmted) if show_words else "")
            + ((f" l:" + fl_lns_fmted) if show_lns else "")
            + "\n"
        )

    return err_code

