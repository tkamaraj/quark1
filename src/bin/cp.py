import os
import shutil as sh
import typing as ty

import utils.err_codes as uerr
import utils.gen as ugen

HELP = ugen.HelpObj(
    usage="cp [flag ...] [opt ...] src [...] dst",
    summary="Copy file/directories to another location",
    details=(
        "ARGUMENTS",
        ("src", "Source file/directory"),
        ("dst", "Destination file/directory"),
        "OPTIONS",
        ("-m metadata", "Amount of metadata to copy with the file"),
        "FLAGS",
        ("-r, --recursive", "Copy recursively"),
        ("-o, --overwrite", "Overwrite destination if it exists"),
        ("-d, --dangling-symlinks", "Check for dangling symlinks"),
        ("-f, --follow-symlinks", "Follow symlinks"),
        ("-c, --create-intermediate", "Create intermediate directories to destination")
    )
)

CMD_SPEC = ugen.CmdSpec(
    min_args=2,
    max_args=float("inf"),
    opts=("-m", "--metadata"),
    flags=(
        "-r", "--recursive",
        "-o", "--overwrite",
        "-d", "--dangling-symlinks",
        "-f", "--follow-symlinks",
        "-c", "--create-intermediate"
    )
)

ERR_OVERWRITE_NON_DIR_W_DIR = 1000
ERR_NOT_A_DIR = 1001
ERR_DIR_NOT_RECUR = 1002


def cp_fl(
    src: str,
    dst: str,
    cp_fn: ty.Callable[[ty.Any, ...], ty.Any],
    follow_symlnks: bool,
    overwrite: bool
) -> int:
    # If the destination is a existing directory, then the plan is to copy
    # the file into the destination directory
    if os.path.isdir(dst):
        dst = os.path.join(dst, os.path.basename(os.path.abspath(src)))
    # If the destination is a file, but overwrite flag isn't given...
    if os.path.isfile(dst) and not overwrite:
        ugen.err(f"File exists: \"{dst}\"")
        return uerr.ERR_FL_EXISTS

    try:
        cp_fn(src, dst, follow_symlinks=follow_symlnks)
    except PermissionError:
        ugen.err(f"Access denied: cannot copy \"{src}\" => \"{dst}\"")
        return uerr.ERR_PERM_DENIED
    except OSError:
        ugen.err("Invalid argument")
        return uerr.ERR_INV_ARG

    return uerr.ERR_ALL_GOOD


def cp_dir(
    src: str,
    dst: str,
    cp_fn: ty.Callable[[ty.Any, ...], ty.Any],
    recursive: bool,
    follow_symlnks: bool,
    chk_dang_symlnks: bool,
    crt_interm_dirs: bool
) -> int:
    if not recursive:
        ugen.err(f"Omitting \"{src}\"; '-r' not specified")
        return ERR_DIR_NOT_RECUR

    src_base = os.path.basename(os.path.abspath(src))

    # If the destination is a file, it cannot be overwritten by a
    # directory, can it be?
    if os.path.isfile(dst):
        return ERR_OVERWRITE_NON_DIR_W_DIR

    # If the destination directory does NOT exist, create a directory
    # with the name/path for the destination provided, then copy everything
    # inside the source directory into it
    if not os.path.isdir(dst):
        try:
            os.makedirs(dst) if crt_interm_dirs else os.mkdir(dst)
        except FileNotFoundError:
            ugen.err(f"Cannot find parents to destination: \"{dst}\"")
            return uerr.ERR_DIR_404

        try:
            sh.copytree(
                src,
                dst,
                copy_function=cp_fn,
                ignore_dangling_symlinks=not chk_dang_symlnks,
                dirs_exist_ok=True,
                symlinks=follow_symlnks
            )
        except sh.Error as e:
            for i in e:
                ugen.err(f"{i[0]} -> {i[1]}: {i[2]}")
            return uerr.ERR_PLACEHOLDER

    # If the destination directory exists, then create a new directory
    # inside it with the base name of the source directory, and copy
    # everything inside the source directory into it
    else:
        try:
            sh.copytree(
                src,
                os.path.join(dst, src_base),
                copy_function=cp_fn,
                ignore_dangling_symlinks=not chk_dang_symlnks,
                symlinks=follow_symlnks
            )
        except FileExistsError:
            ugen.err(
                f"Directory exists: \"{os.path.join(dst, src_base)}\""
            )
            return uerr.ERR_DIR_EXISTS
        except sh.Error as e:
            for i in e:
                ugen.err(f"{i[0]} -> {i[1]}: {i[2]}")
            return uerr.ERR_PLACEHOLDER

    return uerr.ERR_ALL_GOOD


def cp_src_to_dst(
    src: str,
    dst: str,
    metadata: str,
    recursive: bool,
    follow_symlnks: bool,
    chk_dang_symlnks: bool,
    overwrite: bool,
    crt_interm_dirs: bool
) -> int:
    if metadata == "none":
        cp_fn = sh.copyfile
    elif metadata == "limited":
        cp_fn = sh.copy
    elif metadata == "all":
        cp_fn = sh.copy2

    if os.path.isfile(src):
        return cp_fl(src, dst, cp_fn, follow_symlnks, overwrite)
    elif os.path.isdir(src):
        return cp_dir(
            src,
            dst,
            cp_fn,
            recursive,
            follow_symlnks,
            chk_dang_symlnks,
            crt_interm_dirs
        )
    else:
        ugen.err(f"No such file/directory: \"{src}\"")
        return uerr.ERR_FL_DIR_404


def run(data: ugen.CmdData) -> int:
    err_code = uerr.ERR_ALL_GOOD
    ugen.debug("cp executing")

    metadata = "limited"
    recursive = False
    chk_dang_symlnks = False
    overwrite = False
    follow_symlnks = False
    crt_interm_dirs = False

    for flag in data.flags:
        if flag in ("-r", "--recursive"):
            recursive = True
        elif flag in ("-d", "--dangling-symlinks"):
            chk_dang_symlnks = True
        elif flag in ("-o", "--overwrite"):
            overwrite = True
        elif flag in ("-f", "--follow-symlinks"):
            follow_symlnks = True
        elif flag in ("-c", "--create-intermediate"):
            crt_interm_dirs = True

    for opt in data.opts:
        val = data.opts[opt]

        if opt in ("-m", "--metadata"):
            if val in ("n", "none"):
                metadata = "none"
            elif val in ("l", "limited"):
                metadata = "limited"
            elif val in ("a", "all"):
                metadata = "all"
            else:
                ugen.err(f"Invalid value for option '{opt}': '{val}'")
                return uerr.ERR_INV_VAL_OPT

    srcs = data.args[: -1]
    dst = data.args[-1]

    if len(srcs) == 1:
        src = srcs[0]
        tmp_code = cp_src_to_dst(
            src,
            dst,
            metadata=metadata,
            recursive=recursive,
            follow_symlnks=follow_symlnks,
            chk_dang_symlnks=chk_dang_symlnks,
            overwrite=overwrite,
            crt_interm_dirs=crt_interm_dirs
        )
        err_code = err_code or tmp_code

    else:
        # Multiple sources, but no directory to copy to
        if not os.path.isdir(dst):
            ugen.err(f"No such directory: \"{dst}\"")
            return uerr.ERR_DIR_404

        for i in srcs:
            tmp_code = cp_src_to_dst(
                i,
                dst,
                metadata=metadata,
                recursive=recursive,
                follow_symlnks=follow_symlnks,
                chk_dang_symlnks=chk_dang_symlnks,
                overwrite=overwrite,
                crt_interm_dirs=crt_interm_dirs
            )
            err_code = err_code or tmp_code

    return err_code
