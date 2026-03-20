import os
import pathlib as pl
import typing as ty

import utils.gen as ugen
import utils.consts as uconst
import utils.err_codes as uerr

if ty.TYPE_CHECKING:
    import intrpr.internals as iint

HELP = ugen.HelpObj(
    usage="cd [flag] [pth]",
    summary="Changes the current working directory of the interpreter",
    details=(
        "ARGUMENTS",
        "\t<none>",
        "\t\tChange to user directory",
        "\tpth",
        "\t\tDirectory to change to",
        "FLAGS",
        "\t-!",
        "\t\tChange to directory previously in",
        "\t-p",
        "\t\tPrint directory after changing to it",
        "\t-m",
        "\t\tMake directories before changing",
        "\t--tmp",
        "\t\tCreate temporary directory and change to it"
    )
)

CMD_SPEC = ugen.CmdSpec(
    min_args=0,
    max_args=1,
    opts=(),
    flags=("-!", "-p", "-m", "--tmp")
)

ERR_CANT_ALLOT_TMP_DIR = 1000


def actually_chg_dir(
        pth: pl.Path,
        prn_dir: bool,
        env_vars: "iint.Env"
    ) -> int:
    """
    The actual directory changing component of the cd command.

    :param pth: The path to change CWD to.
    :type pth: str

    :returns: Integer error code.
    :rtype: int
    """
    err_code = uerr.ERR_ALL_GOOD

    try:
        before = os.getcwd()
        os.chdir(pth)
        env_vars.set("_PREV_CWD_", before)
        if prn_dir:
            ugen.write(str(pth) + "\n")
    except FileNotFoundError:
        err_code = uerr.ERR_DIR_404
        ugen.err(f"No such file/directory: \"{pth}\"")
    except NotADirectoryError:
        err_code = uerr.ERR_NOT_DIR
        ugen.err(f"Not a directory: \"{pth}\"")
    except PermissionError:
        err_code = uerr.ERR_PERM_DENIED
        ugen.err(f"Access denied: \"{pth}\"")
    # Don't think this is reachable, but let's be on the safer side
    except OSError:
        err_code = uerr.ERR_INV_ARG
        ugen.err(f"Invalid argument: \"{pth}\"")

    return err_code


def run(data: ugen.CmdData) -> int:
    chg_to: pl.Path | str

    err_code = uerr.ERR_ALL_GOOD
    chg_to_prev_cwd = False
    prn_dir = False
    mk_dirs = False
    tmp_dir = False

    for flag in data.flags:
        if flag == "-!":
            chg_to_prev_cwd = True
        elif flag == "-p":
            prn_dir = True
        elif flag == "-m":
            mk_dirs = True
        elif flag == "--tmp":
            tmp_dir = True

    if chg_to_prev_cwd and data.args:
        ugen.err(
            "Cannot change to previous and specified directory at the same time"
        )
        return uerr.ERR_INV_USAGE

    if chg_to_prev_cwd and tmp_dir:
        ugen.err(
            "Cannot change to previous and temporary directory at the same time"
        )
        return uerr.ERR_INV_USAGE

    # Change to previous directory option
    if chg_to_prev_cwd:
        chg_to = pl.Path(data.env_vars.get("_PREV_CWD_")).expanduser().resolve()

    # Temporary directory
    elif tmp_dir:
        for i in range(100):
            dir_pth = f"/tmp/quark_cd_{i}/"
            if os.path.exists(dir_pth):
                continue
            # What the helly? This is for the small chance that a
            # file/directory of the name of the temporary directory is created
            # before it could be created by us
            try:
                os.makedirs(dir_pth)
                chg_to = dir_pth
                break
            except FileExistsError:
                continue
        else:
            ugen.err("Too unlucky... cannot allot temporary directory")
            return ERR_CANT_ALLOT_TMP_DIR

    elif data.args:
        chg_to = pl.Path(data.args[0]).expanduser().resolve()

    else:
        chg_to = pl.Path("~").expanduser()

    # Make directories before changing
    if mk_dirs:
        try:
            os.makedirs(chg_to, exist_ok=True)
        except FileExistsError:
            ugen.err(f"Cannot make directory; File exists: \"{chg_to}\"")
            return uerr.ERR_FL_EXISTS
        except PermissionError:
            ugen.err(f"Cannot make directory; Access denied: \"{chg_to}\"")
            return uerr.ERR_PERM_DENIED
        except OSError:
            ugen.err(
                f"No idea how this might have happened. Invalid path? \"{chg_to}\"",
            )
            return uerr.ERR_UNK_ERR

    err_code = actually_chg_dir(chg_to, prn_dir, data.env_vars)
    return err_code
