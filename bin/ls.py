import datetime as dt
import os
import pathlib as pl
import pwd
import stat

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
        ("-l, --long-list", "Use long listing format"),
        ("-S, --no-slashes", "Do not insert slashes at the end of directory names"),
        ("-i, --inode", "Display inode number in long listing"),
        ("-h, --human-readable", "Display human-readable sizes in long listing"),
        ("-c, --ctime", "Display CTIME instead MTIME in long listing"),
        ("-a, --all", "Display all (including hidden files)"),
        ("-e, --case-sensitive", "Case sensitive sort"),
        ("-u, --unsorted", "Unsorted listing")
    )
)

CMD_SPEC = ugen.CmdSpec(
    min_args=0,
    max_args=float("inf"),
    opts=(),
    flags=(
        "-l", "--long",
        "-S", "--no-slash",
        "-i", "--inode",
        "-h", "--human-readable",
        "-c", "--ctime",
        "-a", "--all",
        "-e", "--case-sensitive",
        "-u", "--unsorted"
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


class SplDirEntry:
    def __init__(self, pth: str):
        self.path = os.path.realpath(pth)
        self.name = os.path.basename(pth)
        self.actual_name = os.path.basename(self.path)
        self.is_dir = os.path.isdir(self.path)
        self.stat = lambda: os.stat(self.path)


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
        slashes: bool,
        inodes: bool,
        human_rdable: bool,
        disp_ctime: bool
    ) -> int:
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
        ctime = dt.datetime.utcfromtimestamp(int(item_stat.st_ctime))
        mtime = dt.datetime.utcfromtimestamp(int(item_stat.st_mtime))

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
        entry["name"] = item.name + (os.sep if slashes and typ == "d" else "")

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
        slashes: bool
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


    # Assume a 80-character terminal for if errors are encountered when
    # determining the number of columns
    cols_avail = 80
    try:
        cols_avail = os.get_terminal_size().columns
    except OSError:
        # Happens when STDOUT is not a tty or something? Happened when I piped
        # output to less
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


def prn_items(
        arg_dir: str,
        items: list[tuple[pl.Path, os.stat_result]],
        long_list: bool,
        slashes: bool,
        inodes: bool,
        human_rdable: bool,
        disp_ctime: bool,
        hidden: bool,
        case_sensi: bool,
        unsorted: bool,
        is_tty: bool
    ) -> int:
    """
    Print the items fetched with stat information to stdout.

    :param items: 
    """
    ugen.write(ugen.S.fmt(arg_dir, is_tty, ugen.S.green) + "\n")
    if not long_list:
        short_list_prn(items, slashes)
    else:
        long_list_prn(items, slashes, inodes, human_rdable, disp_ctime)


def run(data: ugen.CmdData) -> int:
    err_code = uerr.ERR_ALL_GOOD
    long_list = False
    slashes = True
    inodes = False
    human_rdable = False
    disp_ctime = False
    hidden = False
    case_sensi = False
    unsorted = False

    # Detect flags
    for flag in data.flags:
        if flag in ("-l", "--long"):
            long_list = True
        elif flag in ("-S", "--no-slash"):
            slashes = False
        elif flag in ("-i", "--inode"):
            inodes = True
        elif flag in ("-h", "--human-readable"):
            human_rdable = True
        elif flag in ("-c", "--ctime"):
            disp_ctime = True
        elif flag in ("-a", "--all"):
            hidden = True
        elif flag in ("-e", "--case-sensitive"):
            case_sensi = True
        elif flag in ("-u", "--unsorted"):
            unsorted = True

    # No arguments
    if not data.args:
        items, err_code = get_items(
            os.path.expanduser("."),
            hidden=hidden,
            case_sensi=case_sensi,
            unsorted=unsorted
        )

        # No errors encountered when getting items from current directory
        if not err_code:
            prn_items(
                "./",
                items,
                long_list=long_list,
                slashes=slashes,
                inodes=inodes,
                human_rdable=human_rdable,
                disp_ctime=disp_ctime,
                hidden=hidden,
                case_sensi=case_sensi,
                unsorted=unsorted,
                is_tty=data.is_tty
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

            prn_items(
                arg,
                items,
                long_list=long_list,
                slashes=slashes,
                inodes=inodes,
                human_rdable=human_rdable,
                disp_ctime=disp_ctime,
                hidden=hidden,
                case_sensi=case_sensi,
                unsorted=unsorted,
                is_tty=data.is_tty
            )

    return err_code

