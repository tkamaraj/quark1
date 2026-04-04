import datetime as dt
import itertools as it
import math
import os
import pathlib as pl
import pwd
import stat
import typing as ty

import utils.consts as uconst
import utils.err_codes as uerr
import utils.gen as ugen

HELP = ugen.HelpObj(
    usage="ls [flag ...] [dir ...]",
    summary="List files and directories",
    details=(
        "ARGUMENTS",
        ("none", "List current directory"),
        ("dir", "Directory to list"),
        "OPTIONS",
        ("none", ""),
        "FLAGS",
        ("-a, --all", "Display all (including hidden files)"),
        ("-c, --ctime", "Display CTIME instead of MTIME"),
        ("-e, --case-sensitive", "Case sensitive sort"),
        ("-h, --human-readable", "Display human-readable sizes"),
        ("-i, --inode", "Display inode number in long listing"),
        ("-l, --long-list", "Use long listing format"),
        ("-N, --no-symlink-symbols", "Suppress symlink indicators"),
        ("-o, --iso", "Use ISO-8601 for dates and times"),
        ("-S, --no-slashes", "Suppress slashes at the end of directory names"),
        ("-u, --unsorted", "Unsorted listing"),
        ("-X, --no-executable-symbols", "Suppress executable indicators")
    )
)

CMD_SPEC = ugen.CmdSpec(
    min_args=0,
    max_args=float("inf"),
    opts=(),
    flags=(
        "-a", "--all",
        "-c", "--ctime",
        "-e", "--case-sensitive",
        "-h", "--human-readable",
        "-i", "--inode",
        "-l", "--long-list",
        "-N", "--no-symlink-symbols",
        "-o", "--iso",
        "-S", "--no-slashes",
        "-u", "--unsorted",
        "-X", "--no-executable-symbols"
    )
)

PERM_LOOKUP = {
    0: "---",
    1: "--x",
    2: "-w-",
    3: "-wx",
    4: "r--",
    5: "r-x",
    6: "rw-",
    7: "rwx"
}

QUOTES = "\'\""
SP_CHRS = "".join(uconst.SP_CHRS)
WS = " \t\r\n"
BSLASH = "\\"
OTHER = "@*"
QUOTE_STR = QUOTES + SP_CHRS + WS + BSLASH + OTHER


class SplDirEntry:
    def __init__(self, pth: str):
        self.path = os.path.realpath(pth)
        self.name = os.path.basename(pth)
        self.actual_name = os.path.basename(self.path)
        self.is_dir = os.path.isdir(self.path)
        self.stat = lambda: os.stat(self.path)


class EscWhichObj(ty.NamedTuple):
    quotes: bool = True
    sp_chrs: bool = True
    ws: bool = True
    bslash: bool = True
    other: bool = True


def esc_item_nm(nm: str, esc_which: EscWhichObj = EscWhichObj()) -> str:
    # TODO: Implement regex for this
    str_arr = []
    for ch in nm:
        if esc_which.quotes and ch in QUOTES and ch != "\'":
            str_arr.append("\\" + ch)
            continue
        elif esc_which.sp_chrs and ch in SP_CHRS:
            str_arr.append("\\" + ch)
            continue
        elif esc_which.bslash and ch in BSLASH:
            str_arr.append("\\" + ch)
            continue
        elif esc_which.other and ch in OTHER:
            str_arr.append("\\" + ch)
            continue
        str_arr.append(ch)

    if esc_which.ws:
        return (
            "".join(str_arr)
              .replace("\n", "\\n")
              .replace("\r", "\\r")
              .replace("\t", "\\t")
        )
    else:
        return "".join(str_arr)


def _old_short_list_prn(
    items: list[tuple[pl.Path, os.stat_result]],
    slashes: bool,
    is_tty: bool,
    term_sz: os.terminal_size
) -> int:
    # Behold the most unoptimised and brain-dead algorithm known to mankind
    to_prn = []
    max_len = 0
    padding = 3
    for_quotes = False

    for (item, item_stat) in items:
        quotes = False
        if " " in item.name:
            for_quotes = True

        if stat.S_ISDIR(item_stat.st_mode):
            if tmp := [char for char in item.name if char in " \t\r\n\'\""]:
                quotes = True
            tmp = item.name + (os.sep if slashes else "")
            tmp_w_quotes = f"\"{tmp}\"" if quotes else tmp
            to_prn.append(tmp_w_quotes)
            max_len = max(max_len, len(tmp_w_quotes))
        elif stat.S_ISREG(item_stat.st_mode):
            to_prn.append(
                f"\"{item.name}\"" if " " in item.name else item.name
            )
            max_len = max(max_len, len(item.name))
        elif stat.S_ISLNK(item_stat.st_mode):
            to_prn.append(
                f"\"{item.name}\"" if " " in item.name else item.name
            )
            max_len = max(max_len, len(item.name))

    if is_tty:
        # Assume a 80-character terminal for if errors are encountered when
        # determining the number of columns
        cols_avail = 80
        try:
            cols_avail = term_sz.columns
        except OSError:
            # Happens when STDOUT is not a tty or something? Happened when I
            # piped output to less
            pass
        max_cols = (cols_avail - for_quotes) // (max_len + padding)
        if max_cols == 0:
            max_cols = 1

        tmp = []

        for i in range(len(to_prn))[:: max_cols]:
            tmp.append(to_prn[i : i + max_cols])

        for i in tmp:
            for idx, j in enumerate(i):
                has_quotes = "\"" in j
                ugen.write(
                    ("" if has_quotes else " ")
                    + j.ljust(max_len)
                    + (" " if has_quotes else "")
                    + "  "
                )
            ugen.write("\n")

    else:
        for i in to_prn:
            ugen.write(i)


def get_items(
    pth: str,
    hidden: bool,
    case_sensi: bool,
    unsorted: bool
) -> tuple[list[tuple[pl.Path, os.stat_result]], int]:
    """
    List a directory.

    :param pth: The path of the file/directory.
    :type pth: str

    :returns: A tuple containing:
                 - a list of:
                     - a tuple containing the path object and stat result of
                       each item and
                 - an integer, which is the error code.
    :rtype: tuple[list[str], int]
    """
    err_code = uerr.ERR_ALL_GOOD
    typ = ""
    items = []

    # Is a file
    if os.path.isfile(pth):
        try:
            pth_obj = pl.Path(pth).resolve()
        except FileNotFoundError:
            err_code = uerr.ERR_FL_DIR_404
            ugen.err(f"No such file/directory: \"{pth}\"")

    # Is a directory
    elif os.path.isdir(pth):
        try:
            # Unsorted option
            if unsorted:
                iterator = os.scandir(pth)
            else:
                # Case-sensitivity of sorting by name
                sort_fn = lambda e: e.name if case_sensi else e.name.lower()
                iterator = sorted(os.scandir(pth), key=sort_fn)

            # Special directories, i.e. ".." and "."
            if hidden:
                parent = SplDirEntry("..")
                curr = SplDirEntry(".")
                items.append((parent, parent.stat()))
                items.append((curr, curr.stat()))

            for i in iterator:
                # Hidden option filtering
                if not hidden and i.name.startswith("."):
                    continue
                items.append((i, i.stat(follow_symlinks=False)))

        except FileNotFoundError:
            err_code = uerr.ERR_FL_DIR_404
            ugen.err(f"No such file/directory: \"{pth}\"")
        except PermissionError:
            err_code = uerr.ERR_PERM_DENIED
            ugen.err(f"Access denied: \"{pth}\"")
        # Don't think this is reachable, but is here just to be on the safer
        # side
        except OSError:
            err_code = uerr.ERR_INV_PTH
            ugen.err(f"Invalid path: \"{pth}\"")

    # Doesn't exist
    else:
        err_code = uerr.ERR_FL_DIR_404
        ugen.err(f"No such file/directory: \"{pth}\"")

    return (items, err_code)


def long_list_prn(
    items: list[tuple[pl.Path, os.stat_result]],
    is_tty: bool,
    slashes: bool,
    inodes: bool,
    symlnk_syms: bool,
    xble_syms: bool,
    human_rdable: bool,
    disp_ctime: bool,
    iso: bool
) -> None:
    entry: dict[str, ty.Any]

    # pwd.getpwuid(...) calls are real fucking expensive
    uid_cache = {}
    to_prn = []
    max_sz_len = 0
    max_inode_len = 0
    max_owner_nm_len = 0

    for (item, item_stat) in items:
        entry = {}
        mode = item_stat.st_mode

        # Get the item type
        if stat.S_ISDIR(mode):
            typ = "d"
        elif stat.S_ISREG(mode):
            typ = "f"
        elif stat.S_ISLNK(mode):
            typ = "l"
        elif stat.S_ISCHR(mode):
            typ = "c"
        elif stat.S_ISBLK(mode):
            typ = "b"
        elif stat.S_ISFIFO(mode):
            typ = "p"
        elif stat.S_ISSOCK(mode):
            typ = "s"
        else:
            typ = "u"

        # Permissions
        owner_perms = PERM_LOOKUP[(mode >> 6) & 7]
        grp_perms = PERM_LOOKUP[(mode >> 3) & 7]
        others_perms = PERM_LOOKUP[mode & 7]

        # Times, CTIME and MTIME
        fmt_str = r"%Y-%m-%d %H:%M:%S" if iso else r"%d-%m-%Y %H:%M.%S"
        ctime_timestamp = int(item_stat.st_ctime)
        mtime_timestamp = int(item_stat.st_mtime)
        ctime = dt.datetime.fromtimestamp(ctime_timestamp).strftime(fmt_str)
        mtime = dt.datetime.fromtimestamp(mtime_timestamp).strftime(fmt_str)

        # Size
        sz = item_stat.st_size
        sz_char = ""
        if human_rdable:
            sz_len = len(str(sz))
            if 0 <= sz_len <= 3:
                sz_char = "B"
            elif 4 <= sz_len <= 6:
                sz //= 10 ** 3
                sz_char = "kB"
            elif 7 <= sz_len <= 9:
                sz //= 10 ** 6
                sz_char = "MB"
            elif 10 <= sz_len <= 12:
                sz //= 10 ** 9
                sz_char = "GB"
            else:
                sz //= 10 ** 12
                sz_char = "TB"
        max_sz_len = max(max_sz_len, len(str(sz) + sz_char))

        # Owner ID
        owner_id = item_stat.st_uid
        if owner_id not in uid_cache:
            uid_cache[owner_id] = pwd.getpwuid(owner_id).pw_name
        owner_nm = uid_cache[owner_id]
        max_owner_nm_len = max(max_owner_nm_len, len(owner_nm))

        # Inode number
        inode = item_stat.st_ino
        max_inode_len = max(max_inode_len, len(str(inode)))

        nm = item.name
        if is_tty:
            if [ch for ch in nm if ch in QUOTE_STR]:
                nm = esc_item_nm(nm, esc_which=EscWhichObj(sp_chrs=False))
                nm = "\"" + nm + "\""

            if typ == "d":
                nm = ugen.S.fmt(nm, is_tty, ugen.S.green_4)
            else:
                nm = ugen.S.fmt(nm, is_tty, ugen.S.blue_4)

            if slashes and typ == "d":
                nm += os.sep
            elif symlnk_syms and typ == "l":
                nm += ugen.S.fmt("@", is_tty, ugen.S.magenta_4)
            # Executable files
            if xble_syms and typ != "d" and os.access(item.path, os.X_OK):
                nm += ugen.S.fmt("*", is_tty, ugen.S.cyan_4)

        entry["mode"] = mode
        entry["typ"] = typ
        entry["owner_perms"] = owner_perms
        entry["grp_perms"] = grp_perms
        entry["others_perms"] = others_perms
        entry["ctime"] = ctime
        entry["mtime"] = mtime
        entry["sz"] = sz
        entry["sz_char"] = sz_char
        entry["owner_id"] = owner_id
        entry["owner_nm"] = owner_nm
        entry["inode"] = inode
        entry["name"] = nm

        to_prn.append(entry)

    # Actually print the data obtained
    for i in to_prn:
        sz_w_chr = str(i["sz"]) + i["sz_char"]
        item_perms = i["owner_perms"] + i["grp_perms"] + i["others_perms"]
        c_or_mtime = str(i["ctime"]) if disp_ctime else str(i["mtime"])

        ugen.write(
            i["typ"]
            + " " + item_perms
            + (("  " + str(i["inode"]).rjust(max_inode_len)) if inodes else "")
            + "  " + i["owner_nm"].ljust(max_owner_nm_len)
            + "  " + c_or_mtime
            + "  " + sz_w_chr.rjust(max_sz_len)
            + "  " + i["name"]
            + "\n"
        )


def short_list_prn(
    items: list[tuple[pl.Path, os.stat_result]],
    slashes: bool,
    symlnk_syms: bool,
    xble_syms: bool,
    is_tty: bool,
    term_sz: os.terminal_size,
) -> None:
    """
    Short listing for the ls command.

    :param items: Directory items fetched.
    :type items: list[tuple[pathlib.Path, os.stat_result]]

    :param slashes: Insert slashes at the end of directory names?
    :type slashes: bool

    :param symlnk_syms: Insert symlink symbol at the end of symlink names?
    :type symlnk_syms: bool

    :param xble_syms: Insert executable symbols at the end of executable names?
    :type xble_syms: bool

    :param is_tty: Is STDOUT a TTY?
    :type is_tty: bool

    :param term_sz: Terminal window size.
    :type term_sz: os.terminal_size
    """
    fmted_items = []
    fmted_items_app = fmted_items.append
    max_len = 0
    padding = 2

    for (item, item_stat) in items:
        nm = item.name
        mode = item_stat.st_mode

        quotes = False
        if [ch for ch in item.name if ch in QUOTE_STR]:
            quotes = True

        if is_tty:
            if quotes:
                nm = esc_item_nm(nm, esc_which=EscWhichObj(sp_chrs=False))
                nm = "\"" + nm + "\""

            is_dir = stat.S_ISDIR(mode)
            if is_dir:
                nm = ugen.S.fmt(nm, is_tty, ugen.S.green_4)
            else:
                nm = ugen.S.fmt(nm, is_tty, ugen.S.blue_4)

            # Directory symbols
            if slashes and is_dir:
                nm += os.sep
            # Symlink symbols
            if symlnk_syms and stat.S_ISLNK(mode):
                nm += ugen.S.fmt("@", is_tty, ugen.S.magenta_4)
            # Executable symbols
            if xble_syms and not is_dir and os.access(item.path, os.X_OK):
                nm += ugen.S.fmt("*", is_tty, ugen.S.cyan_4)

        fmted_items_app(nm)
        max_len = max(max_len, len(ugen.rm_ansi("", nm)))

    if is_tty:
        # Assume a 80-character terminal for if errors are encountered when
        # determining the number of columns
        cols_avail = term_sz.columns
        max_cols = cols_avail // (max_len + padding)
        if max_cols <= 0:
            max_cols = 1

        to_prn = []
        num_lns = math.ceil(len(fmted_items) / max_cols)
        for i in range(num_lns):
            # start = i * max_cols
            # to_prn.append(fmted_items[start : start + max_cols])
            to_prn.append(fmted_items[i * max_cols : (i + 1) * max_cols])

        # to_prn = [list(i) for i in zip(*to_prn)]
        for i in to_prn:
            padded_i = [ugen.ljust(j, max_len) for j in i]
            ugen.write((" " * padding).join(padded_i) + "\n")

    else:
        for i in fmted_items:
            ugen.write(i + "\n")


def run(data: ugen.CmdData) -> int:
    err_code = uerr.ERR_ALL_GOOD
    long_list = False
    slashes = True
    inodes = False
    human_rdable = False
    disp_ctime = False
    symlnk_syms = True
    xble_syms = True
    hidden = False
    case_sensi = False
    unsorted = False
    iso = False

    # Detect flags
    for flag in data.flags:
        if flag in ("-l", "--long-list"):
            long_list = True
        elif flag in ("-S", "--no-slashes"):
            slashes = False
        elif flag in ("-i", "--inode"):
            inodes = True
        elif flag in ("-h", "--human-readable"):
            human_rdable = True
        elif flag in ("-c", "--ctime"):
            disp_ctime = True
        elif flag in ("-N", "--no-symlink-symbols"):
            symlnk_syms = False
        elif flag in ("-X", "--no-executable-symbols"):
            xble_syms = False
        elif flag in ("-a", "--all"):
            hidden = True
        elif flag in ("-e", "--case-sensitive"):
            case_sensi = True
        elif flag in ("-u", "--unsorted"):
            unsorted = True
        elif flag in ("-o", "--iso"):
            iso = True

    # No arguments
    if not data.args:
        items, err_code = get_items(
            os.path.expanduser("./"),
            hidden=hidden,
            case_sensi=case_sensi,
            unsorted=unsorted
        )

        # No errors encountered when getting items from current directory
        if not err_code:
            ugen.write(ugen.S.fmt("./", data.is_tty, ugen.S.green_4) + "\n")
            if long_list:
                long_list_prn(
                    items,
                    data.is_tty,
                    slashes,
                    symlnk_syms,
                    xble_syms,
                    inodes,
                    human_rdable,
                    disp_ctime,
                    iso
                )
            else:
                short_list_prn(
                    items,
                    slashes,
                    symlnk_syms,
                    xble_syms,
                    data.is_tty,
                    data.term_sz
                )

    # Yes arguments
    else:
        for arg in data.args:
            items, tmp_err_code = get_items(
                os.path.expanduser(arg),
                hidden=hidden,
                case_sensi=case_sensi,
                unsorted=unsorted
            )
            err_code = err_code or tmp_err_code

            # Errors has been encountered when getting items for this argument
            if tmp_err_code:
                continue

            ugen.write(ugen.S.fmt(arg, data.is_tty, ugen.S.green_4) + "\n")
            if long_list:
                long_list_prn(
                    items,
                    data.is_tty,
                    slashes,
                    symlnk_syms,
                    xble_syms,
                    inodes,
                    human_rdable,
                    disp_ctime,
                    iso
                )
            else:
                short_list_prn(
                    items,
                    slashes,
                    symlnk_syms,
                    xble_syms,
                    data.is_tty,
                    data.term_sz
                )

    return err_code
