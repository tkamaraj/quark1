import os
import runpy as rp
import typing as ty

import utils.consts as uconst
import utils.gen as ugen
import utils.err_codes as uerr


class Cfg(ty.NamedTuple):
    prompt: str
    pth: tuple[str]


def sandbox_runpy(fl: str) -> dict[str, ty.Any] | None:
    try:
        return rp.run_path(fl)
    except FileNotFoundError:
        return None


def get_cfg() -> Cfg:
    prompt = uconst.Defaults.PROMPT
    pth = uconst.Defaults.PTH
    cfg = sandbox_runpy(uconst.CFG_FL)
    err_report = lambda key: ugen.err_Q(
        f"Invalid type for config option '{key}'; using default value"
    )

    if cfg is None:
        return Cfg(prompt=prompt, pth=pth)

    for key in cfg:
        if key == "prompt":
            if not isinstance(cfg[key], str):
                err_report(key)
                continue
            prompt = cfg[key]
        elif key == "pth":
            if not isinstance(cfg[key], tuple):
                err_report(key)
                continue
            pth = cfg[key]

    return Cfg(prompt=prompt, pth=pth)

