# TODO: Add process filtering
import subprocess as sp
import typing as ty

import utils.err_codes as uerr
import utils.gen as ugen

HELP = ugen.HelpObj(
    usage="pl [flag]",
    summary="Get a list of running processes",
    details=(
        "ARGUMENTS",
        ("none", ""),
        "OPTIONS",
        ("none", ""),
        "FLAGS",
        ("-l, --long", "Process long listing")
    )
)

CMD_SPEC = ugen.CmdSpec(
    min_args=0,
    max_args=0,
    opts=(),
    flags=("-l", "--long")
)

ERR_CANT_GET_PROC_LIST = 1000

T = ty.TypeVar("T")
tuple4 = tuple[T, T, T, T]
tuple7 = tuple[T, T, T, T, T, T, T]


def run(data: ugen.CmdData) -> int:
    err_code = uerr.ERR_ALL_GOOD
    long = "-l" in data.flags or "--long" in data.flags

    if long:
        ps_fmt_str = "uid,pid,ppid,psr,stime,time,cmd"
    else:
        ps_fmt_str = "pid,stime,time,comm"

    num_cols = ps_fmt_str.count(",")

    rn_cmd = ["ps", "-eo", ps_fmt_str, "--no-headers"]
    compd_proc = sp.run(rn_cmd, capture_output=True, text=True)
    if compd_proc.returncode != 0:
        ugen.err("Could not get process list")
        return ERR_CANT_GET_PROC_LIST
    stdout = compd_proc.stdout.splitlines()

    op_buf = []
    len_arr = []

    for ln in stdout:
        # https://docs.python.org/3.14/library/stdtypes.html#str.split
        # "If sep is not specified or is None, a different splitting algorithm
        # is applied: runs of consecutive whitespace are regarded as a single
        # separator, [...]"
        out = ln.split(None, maxsplit=num_cols - 1)
        op_buf.append(tuple(out))
        len_arr.append(tuple(map(len, out)))

    # Determine the length of the longest element in each column.
    # Iterate over the lengths array, which is a list of tuples of containing
    # column length for each process
    max_len_arr = [0] * num_cols
    for j in range(num_cols):
        max_len_arr[j] = max(col_len[j] for col_len in len_arr)

    for proc_entry in op_buf:
        to_write = "  ".join(
            [
                (item.ljust(max_len_arr[j]) if j < num_cols - 1 else item)
                for j, item in enumerate(proc_entry)
            ]
        )
        if len(to_write) > data.term_sz.columns:
            ugen.write(to_write[: data.term_sz.columns - 1] + ">\n")
        else:
            ugen.write(to_write + "\n")

    return err_code
