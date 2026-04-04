import io
import sys

import concurrent.futures as confut
import multiprocessing    as mp
import threading          as th
import typing             as ty

import core.built_in_cmds as bicmds
import public.engine      as peng
import utils.engine_utils as ueng


class CmdExecObj:
    def __init__(
            self,
            cmd: str,
            func: ty.Callable[[peng.CmdData], int],
            data: peng.CmdData,
            inpStream: str,
            outStream: str,
            isBg: bool,
        ):
        self.cmd       = cmd
        self.func      = func
        self.data      = data
        self.output    = ""
        self.inpStream = inpStream
        self.outStream = outStream
        self.isBg      = isBg
        self.status    = "init"
        self.proc      = mp.Process(
            name=cmd,
            target=func,
            args=(data,),
            daemon=True
        )

    def start(self) -> int:
        self.status = "running"

        self.proc.start()
        if not self.isBg:
            self.proc.join()

        return self.func(self.data)

    def fKill(self) -> int:
        self.proc.kill()
        return 0

    def proclaimYourself(self) -> None:
        print(
            "MY NAME IS " + self.cmd,
            "MY RUN FUNCTION IS " + str(self.func),
            "COMMAND DATA SUPPLIED IS " + str(self.data),
            "INPUT STREAM " + self.inpStream,
            "OUTPUT STREAM " + self.outStream,
            "IS BACKGROUND PROCESS " + str(self.isBg),
        )


class GlobalEnv:
    def __init__(self, env: dict[str, str] | None = None) -> None:
        self.env = {} if env is None else env


if __name__ == "__main__":
    x = CmdExecObj("test", bicmds.CD, peng.CmdData("test", {}, {}, {}), '', '', True)
    x.start()
