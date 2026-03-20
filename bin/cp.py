# Do the controls manually to have control over overwriting of files and directories
###

import os
import shutil as sh

import utils.err_codes as uerr
import utils.gen as ugen

HELP = ugen.HelpObj(
    usage="",
    summary="",
    details=""
)

CMD_SPEC = ugen.CmdSpec(
    min_args=2,
    max_args=float("inf"),
    opts=(),
    flags=("-r", "-o")
)

ERR_OVERWRITE_NON_DIR_W_DIR = 1000


def cp_single_src_to_dest(
        src: str,
        dst: str,
        metadata: str,
        follow_symlnks: bool,
        chk_dang_symlnks: bool,
        overwrite: bool
    ) -> int:
    if metadata == "none":
        cp_fn = sh.copyfile
    elif metadata == "limited":
        cp_fn = sh.copy
    elif metadata == "all":
        cp_fn = sh.copy2

    if os.path.isfile(src):
        # The destination is an existing directory; this block is needed to
        # prevent overwriting of file unless the overwrite option is passed
        if os.path.isdir(dst):
            dst_reslvd = os.path.join(dst, os.path.basename(src))
        if os.path.isfile(dst_reslvd) and not overwrite:
            ugen.err(f"The file exists at the destination: \"{src}\"")
            return uerr.ERR_FL_EXISTS
        try:
            cp_fn(src, dst, follow_symlinks=follow_symlnks)
        except PermissionError:
            ugen.err(f"Access denied: cannot copy file \"{src}\" to \"{dst}\"")
            return uerr.ERR_PERM_DENIED
        except OSError:
            # No idea if this could even happen
            ugen.err("Invalid argument")
            return uerr.ERR_INV_ARG

    elif os.path.isdir(src):
        try:
            # sh.copytree(
            #     src,
            #     dest,
            #     copy_function=cp_fn,
            #     ignore_dangling_symlinks=not chk_dang_symlnks,
            #     dirs_exist_ok=overwrite,
            #     symlinks=follow_symlnks
            # )
            src_basenm = os.path.basename(src)

            # File/directory at destination already exists
            if not overwrite and os.path.exists(os.path.join(dst, src_basenm)):
                return uerr.ERR_FL_DIR_EXISTS

            # Cannnot overwrite non-directory with directory
            if os.path.isfile(os.path.join(dst, src_basenm)):
                return ERR_OVERWRITE_NON_DIR_W_DIR

            if not os.path.isdir(dst):
                if not crt_interm_dirs:
                    return uerr.ERR_DIR_404
                try:
                    os.makedirs(dst, exist_ok=True)
                # Occurs when there already exists a file with path dst
                except FileNotFoundError:
                    pass

            for pth, dir_nms, fl_nms in os.walk(src):
                for fl in fl_nms:
                    sh.copy2(os.path.join(pth, fl), )
        except FileExistsError:
            ugen.err(f"The directory exists: \"{dst}\"")
            return uerr.ERR_DIR_EXISTS
        except sh.Error as e:
            for i in e:
                ugen.err(f"{i[0]} -> {i[1]}: {i[2]}")
            return uerr.ERR_PLACEHOLDER


    else:
        ugen.err(f"No such source file/directory: \"{src}\"")
        return uerr.ERR_FL_DIR_404


def run(data: ugen.CmdData) -> int:
    err_code = uerr.ERR_ALL_GOOD
    ugen.debug("cp executing")

    recursive = False
    metadata = "limited"
    chk_dang_symlnks = False
    overwrite = False
    follow_symlnks = False
    crt_interm_dirs = False

    for flag in data.flags:
        if flag == "-r":
            recursive = not recursive
        elif flag == "-ds":
            chk_dang_symlnks = not chk_dang_symlnks
        elif flag == "-o":
            overwrite = not overwrite
        elif flag == "-fs":
            follow_symlnks = not follow_symlnks
        elif flag == "-cid":
            crt_interm_dirs = True

    for opt in data.opts:
        val = data.opts[opt]

        if opt == "-m":
            if val == "n" or val == "none":
                metadata = "none"
            elif val == "l" or val == "limited":
                metadata = "limited"
            elif val == "a" or val == "all":
                metadata = "all"

    srcs = data.args[: -1]
    dest = data.args[-1]

    if len(srcs) == 1:
        src = srcs[0]
        cp_single_src_to_dest(
            src,
            dest,
            metadata=metadata,
            follow_symlnks=follow_symlnks,
            chk_dang_symlnks=chk_dang_symlnks,
            overwrite=overwrite
        )

    else:
        for i in srcs:
            cp_single_src_to_dest(
                src,
                dest,
                metadata=metadata,
                follow_symlnks=follow_symlnks,
                chk_dang_symlnks=chk_dang_symlnks,
                overwrite=overwrite
            )

    return err_code

