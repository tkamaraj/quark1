import os
import subprocess as sp
import sys
import typing as ty

called_nm = os.path.basename(sys.argv[0])


class Cfg(ty.NamedTuple):
    no_docstrs: bool
    lto: bool
    rm_build: bool
    rm_pyi: bool
    quiet: bool
    show_mods: bool
    run: bool
    out_dir: str | None
    out_fl_nm: str | None
    args: list[str]


def parse_args() -> Cfg:
    no_docstrs = True
    lto = False
    rm_build = True
    rm_pyi = True
    quiet = True
    show_mods = False
    run = True
    out_dir = None
    out_fl_nm = None
    args = []

    toks = sys.argv[1 :]
    len_toks = len(toks)
    parse_opts_flags = True
    skip = 0

    for i, tok in enumerate(toks):
        if skip:
            skip -= 1
            continue
        if not parse_opts_flags:
            args.append(tok)

        if tok in ("-h", "--help"):
            print("See the source, fuckass")
            sys.exit(1)
        if tok == "-R":
            run = False
        elif tok == "-lto":
            lto = True
        elif tok == "-ds":
            no_docstrs = False
        elif tok == "-pyi":
            rm_pyi = False
        elif tok == "-bd":
            rm_build = False
        elif tok == "-Q":
            quiet = False
        elif tok == "-sm":
            show_mods = True
        elif tok == "-outdir":
            if i == len_toks - 1:
                sys.stderr.write(f"{called_nm}: Expected value for option '{tok}'\n")
                sys.exit(1)
            out_dir = toks[i + 1]
            skip = 1
        elif tok == "-outflnm":
            if i == len_toks - 1:
                sys.stderr.write(f"{called_nm}: Expected value for option '{tok}'\n")
                sys.exit(1)
            out_fl_nm = toks[i + 1]
            skip = 1
        elif tok == "--":
            parse_opts_flags = False
        else:
            args.append(tok)

    min_num_of_args = 1
    max_num_of_args = 1
    if len(args) < min_num_of_args:
        sys.stderr.write(
            f"{called_nm}: Insufficient arguments; expected at least {min_num_of_args}, got {len(args)}\n"
        )
        sys.exit(2)
    elif len(args) > max_num_of_args:
        sys.stderr.write(
            f"{called_nm}: Unexpected arguments; expected at most {max_num_of_args}, got {len(args)}\n"
        )
        sys.exit(2)

    return Cfg(
        no_docstrs=no_docstrs,
        lto=lto,
        rm_build=rm_build,
        rm_pyi=rm_pyi,
        quiet=quiet,
        show_mods=show_mods,
        run=run,
        out_dir=out_dir,
        out_fl_nm=out_fl_nm,
        args=args
    )


def main() -> None:
    cfg = parse_args()

    sys.stdout.write(f"{called_nm}: Using Python at {sys.executable}\n")
    basenm = os.path.splitext(os.path.basename(cfg.args[0]))[0]
    cmd = [
        "python",
        "-m",
        "nuitka",
        "--mode=standalone",
        "--follow-imports",
        "--python-flag=no_docstrings" if cfg.no_docstrs else "",
        "--lto=yes" if cfg.lto else "--lto=no",
        "--run" if cfg.run else "",
        "--remove-output" if cfg.rm_build else "",
        "--no-pyi-file" if cfg.rm_pyi else "",
        "--quiet" if cfg.quiet else "",
        "--show-modules" if cfg.show_mods else "",
        "--include-package=intrpr.builtin_cmds",
        "--output-folder-name=build",
        f"--output-dir={cfg.out_dir}" if cfg.out_dir is not None else "",
        f"--output-filename=" + (cfg.out_fl_nm if cfg.out_fl_nm is not None else basenm),
        cfg.args[0]
    ]

    sp.run(
        [i for i in cmd if i],
        text=True,
        capture_output=False
    )

    sp.run(["rm", "-r", "build"], stderr=sp.DEVNULL, text=True, capture_output=False)
    sp.run(["mv", "build.dist", "build"], stderr=sp.DEVNULL, text=True, capture_output=False)


if __name__ == "__main__":
    main()

