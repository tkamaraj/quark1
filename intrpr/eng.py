import importlib.util as ilu
import inspect as ins
import io
import logging as lg
import multiprocessing as mp
import os
import pathlib as pl
import platform as pf
import pwd
import re
import struct as st
import sys
import time
import traceback as tb
import typing as ty

import intrpr.cfg_mgr as cmgr
import intrpr.cmd_reslvr as icrsr
import intrpr.internals as iint
import parser.eng as peng
import utils.gen as ugen
import utils.consts as uconst
import utils.debug as udeb
import utils.err_codes as uerr

if ty.TYPE_CHECKING:
    import parser.internals as pint

TH_TokGrp = tuple[list[str], "pint.SpChr"]
TH_CmdFn = ty.Callable[[ugen.CmdData], int]
TH_GetCmdRes = tuple[TH_CmdFn, ugen.CmdSpec]


class CmdReslnRes(ty.NamedTuple):
    cmd_fn: ty.Callable[[ugen.CmdData], int]
    cmd_spec: ugen.CmdSpec
    cmd_src: str


def fmt_t_ns(time_expo: int, ns: int) -> str:
    if time_expo == 3:
        unit = "us"
    elif time_expo == 6:
        unit = "ms"
    elif time_expo == 0:
        unit = "ns"
    elif time_expo == 9:
        unit = "s"
    else:
        ugen.fatal(
            "Unrecognised debug time unit; this is not supposed to happen",
            uerr.ERR_UNK_ERR
        )

    return str(round(ns / 10 ** time_expo, 3)) + unit


class Intrpr:
    def __init__(
            self,
            cfg: cmgr.Cfg,
            pre_ld_ext_cmds: bool,
            stderr_ansi: bool,
            debug_time_expo: int,
            log_lvl: int
        ) -> None:
        self.ext_cached_cmds: dict[str, iint.CmdCacheEntry]

        # Interpreter initialisation time start
        _t_intrpr_init = time.perf_counter_ns()

        self.GET_CMD_ERR_MSG_MAP = {
            uerr.ERR_BAD_CMD: f"Bad command",
            uerr.ERR_NOT_VALID_CMD: f"No valid command file",
            uerr.ERR_NO_CMD_FN: f"No command function",
            uerr.ERR_NO_CMD_SPEC: f"Cannot find command spec",
            uerr.ERR_UNCALLABLE_CMD_FN: f"Uncallable command function",
            uerr.ERR_INV_NUM_PARAMS: f"Invalid number of command function parameters",
            uerr.ERR_MALFORMED_CMD_SPEC: f"Malformed command spec",
            uerr.ERR_RECUR_ERR: "Recursion depth exceeded; did you import the interpreter engine?",
            uerr.ERR_CMD_SYN_ERR: "Syntax error in command module"
        }

        ugen.warn_Q("Exercise caution when running untrusted commands")

        self.usr_dir = pl.Path("~").expanduser()
        self.uid = str(os.getuid())
        self.usernm = pwd.getpwuid(int(self.uid)).pw_name
        self.is_usr_root = (self.uid == "0")

        self.ext_cached_cmds = {}
        self.cfg = cfg
        self.stderr_ansi = stderr_ansi
        self.debug_time_expo = debug_time_expo
        self.log_lvl = log_lvl
        self.env_vars = iint.Env()
        self.parser = peng.Parser()
        self.cmd_reslvr = icrsr.CmdReslvr(self.ext_cached_cmds,
                                          self.debug_time_expo)

        self.env_vars.set("_USR_DIR_", str(self.usr_dir))
        self.env_vars.set("_PREV_CWD_", os.getcwd())
        self.env_vars.set("_LAST_BAD_PROMPT_", "")
        self.env_vars.set("_LAST_RET_", uerr.ERR_ALL_GOOD)

        self.use_cfg()

        if pre_ld_ext_cmds:
            # DEBUG: Pre-load external modules time start
            _t_pre_ld = time.perf_counter_ns()
            self.ld_all_ext_mods()
            # DEBUG: Pre-load external module time end
            _t_pre_ld = time.perf_counter_ns() - _t_pre_ld
            ugen.debug_Q(
                ugen.fmt_d_stmt("time", "tot_pre_ld_ext",
                                fmt_t_ns(self.debug_time_expo, _t_pre_ld))
            )

        try:
            os.chdir(udeb.TMP_DIR)
        except FileNotFoundError:
            pass
        except PermissionError:
            pass
        except OSError:
            pass

        # Interpreter initialisation time end
        _t_intrpr_init = time.perf_counter_ns() - _t_intrpr_init

        ugen.debug_Q(
            ugen.fmt_d_stmt("time", "tot_init_intrpr",
                            fmt_t_ns(self.debug_time_expo, _t_intrpr_init))
        )

    def reslv_prompt(self, prompt: str | None) -> str:
        """
        "Resolve" the prompt, i.e. do all prompt substitutions.

        :param prompt: Prompt string.
        :type prompt: str | None

        :returns: Prompt string after prompt substitutions are performed.
        :rtype: str
        """
        # Pretty bad design, I guess, handling the None case for variable
        # prompt in this method, but I don't want to clutter up the main file
        prompt = prompt or uconst.Defaults.PROMPT
        len_prompt = len(prompt)
        final_prompt = ""
        skip = 0

        for i, char in enumerate(prompt):
            if skip:
                skip -= 1
                continue
            if char != "!":
                final_prompt += char
                continue
            # ! at the end of prompt
            if i == len_prompt - 1:
                # Issue warning only once
                if self.env_vars.get("_LAST_BAD_PROMPT_") != prompt:
                    ugen.warn_Q(
                        "Unescaped '!' in prompt variable; using default prompt",
                    )
                    self.last_bad_prompt = prompt
                return self.reslv_prompt(uconst.Defaults.PROMPT)

            # Condensed path
            if prompt[i + 1] == "p":
                cwd_conden = re.sub(
                    f"^{re.escape(str(self.usr_dir))}",
                    "~",
                    os.getcwd()
                )
                final_prompt += cwd_conden
                skip += 1
                continue

            # Condensed path with slashes at the end for all directories
            # except the root and user directory
            elif prompt[i + 1] == "P":
                cwd_conden = re.sub(
                    f"^{self.usr_dir}",
                    "~",
                    os.getcwd()
                )
                final_prompt += cwd_conden
                if not (cwd_conden == "~" or cwd_conden == "/"):
                    final_prompt += "/"
                skip += 1
                continue

            # Expanded path
            elif prompt[i + 1] == "e":
                cwd = os.getcwd()
                final_prompt += cwd
                skip += 1
                continue

            # Username
            elif prompt[i + 1] == "u":
                final_prompt += self.usernm
                skip += 1
                continue

            elif prompt[i + 1] == "U":
                final_prompt += self.uid
                skip += 1
                continue

            # Hostname
            elif prompt[i + 1] == "h":
                final_prompt += pf.node()
                skip += 1
                continue

            # Quark version
            elif prompt[i + 1] == "v":
                final_prompt += uconst.VER
                skip += 1
                continue

            # Elevation symbols (how else can I describe this?)
            elif prompt[i + 1] == "$":
                if self.is_usr_root:
                    final_prompt += "%"
                else:
                    final_prompt += "$"
                skip += 1
                continue

            elif prompt[i + 1] == "?":
                final_prompt += str(self.env_vars.get("_LAST_RET_"))
                skip += 1
                continue

            # Literal '!'
            elif prompt[i + 1] == "!":
                final_prompt += "!"
                skip += 1
                continue

            else:
                # Issue warning only once
                if self.env_vars.get("_LAST_BAD_PROMPT_") != prompt:
                    ugen.warn_Q(
                        f"Invalid prompt substitution symbol: '!{prompt[i + 1]}'; using default prompt"
                    )
                    self.env_vars.set("_LAST_BAD_PROMPT_", prompt)
                return self.reslv_prompt(uconst.Defaults.PROMPT)

        return final_prompt

    def use_cfg(self) -> None:
        """
        Use user-provided config values, i.e. set interpreter attributes as per
        config given.
        """
        self.env_vars.set("_PROMPT_", self.cfg.prompt)
        pths = []
        for i in self.cfg.pth:
            if i == ".":
                pths.append(uconst.BIN_PTH)
            else:
                pths.append(str(pl.Path(i).expanduser().resolve()))
        self.env_vars.set("_PTH_", tuple(pths))

    def ld_all_ext_mods(self) -> None:
        """
        Load all external modules into cache. Intended to be used at
        interpreter startup.
        """
        pths = self.env_vars.get("_PTH_")
        for pth in pths:
            pth = pl.Path(pth).expanduser().resolve()
            for i in os.scandir(pth):
                if os.path.isdir(i):
                    continue
                if not i.name.endswith(".py"):
                    continue
                if i.name == "__init__.py":
                    continue
                self.cmd_reslvr.ld_mod(
                    os.path.splitext(i.name)[0],
                    self.ext_cached_cmds,
                    pths
                )

    def get_cmd(
        self,
        cmd_nm: str,
        ext_cached_cmds: dict[str, iint.CmdCacheEntry],
        cmd_reslvr: icrsr.CmdReslvr,
        env_vars: iint.Env
    ) -> tuple[
        ty.Callable[[ugen.CmdData], int],
        ugen.CmdSpec,
        str
    ] | int:
        """
        Get the command function, command spec and command source using the
        command resolver.

        :param cmd_nm: Command name
        :type cmd_nm: str

        :param ext_cached_cmds: Cached external commands
        :type ext_cached_cmds: dict[str, intrpr.internals.CmdCacheEntry]

        :param cmd_reslvr: Command resolver object
        :type cmd_reslvr: intrpr.cmd_reslvr.CmdReslvr

        :param env_vars: Environment variables
        :type env_vars: intrpr.internals.Env

        :returns: If successful in fetching the command function and spec, a
                  tuple containing:
                      - the command function and
                      - the command spec.
                  Else, an integer error code.
        :rtype: tuple[
                    typing.Callable[[utils.gen.CmdData], int],
                    utils.gen.CmdSpec,
                    str
                ] | int
        """
        builtin_cmd = self.cmd_reslvr.get_builtin_cmd(cmd_nm)
        if isinstance(builtin_cmd, tuple):
            return (*builtin_cmd, "built-in")

        ext_cmd = self.cmd_reslvr.get_ext_cmd(
            cmd_nm,
            env_vars.get("_PTH_"),
            ext_cached_cmds
        )
        if isinstance(ext_cmd, int):
            return ext_cmd
        return (*ext_cmd, "external")

    def classi_par_out(
        self,
        tok_grp: "list[pint.Tok]",
        cmd_spec: ugen.CmdSpec
    ) -> tuple[tuple[str, ...], dict[str, str], tuple[str, ...]] | int:
        """
        Helper function to classify parser output into arguments, flags and
        options.

        :param tok_grp: Token group yielded from parser.
        :type tok_grp: list[parser.internals.Tok]

        :param cmd_spec: Command spec from command file.
        :type cmd_spec: utils.gen.CmdSpec

        :returns: If no errors occured, a tuple containing:
                      - a tuple of strings (argument array),
                      - a dictionary of string keys and string values (option
                        array) and
                      - a tuple of strings (flag array).
                  Otherwise, an integer error code.
        """
        args = []
        opts = {}
        flags = []
        arg_cnt = 0
        skip = 0

        # Iterate through the parser output
        for idx, tok in enumerate(tok_grp[1 :]):
            tok_val = tok.val
            if skip:
                skip -= 1
                continue

            # An option or a flag
            if tok_val.startswith("-") and not tok.escd_hyphen:
                # Not in spec
                if tok_val not in (*cmd_spec.opts, *cmd_spec.flags):
                    ugen.err(f"Invalid option/flag: '{tok.val}'")
                    return uerr.ERR_INV_OPTS_FLAGS
                # Flags are given more preference
                if tok_val in cmd_spec.flags:
                    flags.append(tok_val)
                # Then options
                else:
                    if idx >= len(tok_grp) - 2:
                        ugen.err(f"Expected value for option: '{tok.val}'")
                        return uerr.ERR_EXPECTED_VAL_FOR_OPT
                    opts[tok_val] = tok_grp[idx + 2].val
                    skip += 1

                continue

            # An argument
            arg_cnt += 1
            if arg_cnt > cmd_spec.max_args:
                ugen.err(
                    f"Unexpected arguments; expected at most {cmd_spec.max_args}, got {arg_cnt}"
                )
                return uerr.ERR_UNEXPD_ARGS
            args.append(tok_val)

        if arg_cnt < cmd_spec.min_args:
            ugen.err(
                f"Insufficient arguments; expected at least {cmd_spec.min_args}, got {arg_cnt}"
            )
            return uerr.ERR_INSUFF_ARGS

        return (tuple(args), opts, tuple(flags))

    def rd_from_fd(self, fd: io.IOBase, n: int) -> bytes:
        """
        Read data from stream.

        :param fd: Stream to read data from.
        :type fd: io.IOBase

        :param n: Number of bytes to read.
        :type n: int

        :returns: Bytes object read.
        :rtype: bytes
        """
        chunks = []
        total = 0

        while total < n:
            chunk = os.read(fd, n - total)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)

        return b"".join(chunks)

    def write_to_stderr(
        self,
        stderr: str | None,
        stderr_fl: "pint.Tok | None"
    ) -> int:
        """
        :param stderr: Text captured for STDERR redirection.
        :type stderr: str | None

        :param stderr_fl: File to redirect STDERR to.
        :type stderr_fl: parser.internals.Tok | None

        :returns: Integer error code.
        :rtype: int
        """
        if stderr is None or stderr_fl is None:
            return uerr.ERR_ALL_GOOD

        try:
            with open(stderr_fl.val, "w") as f:
                if self.stderr_ansi:
                    f.write(stderr)
                else:
                    f.write(ugen.rm_ansi("", stderr))
        except PermissionError:
            ugen.err_Q(f"Access denied; cannot write STDERR to file \"{stderr_fl.val}\"")
            return uerr.ERR_PERM_DENIED
        except FileNotFoundError:
            ugen.err_Q(f"Empty file; cannot write STDERR to file \"{stderr_fl.val}\"")
            return uerr.ERR_EMPTY_FL_REDIR
        except Exception as e:
            ugen.fatal_Q(
                f"Unknown error ({e}); cannot write STDERR to file \"{stderr_fl.val}\"",
                uerr.ERR_UNK_FATAL,
                tb.format_exc()
            )
            return uerr.ERR_UNK_ERR

    def loop_set_lgr_streams(
        self,
        chk_if: io.TextIOBase,
        set_to: io.TextIOBase
    ) -> None:
        """
        Loop through and set logger streams.

        :param chk_if: Object to check if streams against
        :type chk_if: io.TextIOBase

        :param set_to: Object to set streams to
        :type set_to: io.TextIOBase
        """
        for lgr in lg.Logger.manager.loggerDict.values():
            if isinstance(lgr, lg.PlaceHolder):
                continue
            for hdlr in lgr.handlers:
                if hdlr.stream is chk_if:
                    hdlr.stream = set_to

    def cmd_resln(
        self,
        cmd_nm: str,
        buf_stderr: io.StringIO,
        stderr_fl: str | None
    ) -> CmdReslnRes | int:
        # DEBUG: Command resolution time start
        _t_cmd_resln = time.perf_counter_ns()

        err_code = uerr.ERR_ALL_GOOD
        get_cmd_res = self.get_cmd(
            cmd_nm,
            self.ext_cached_cmds,
            self.cmd_reslvr,
            self.env_vars
        )

        if isinstance(get_cmd_res, int):
            # Write error message to current STDERR
            err_msg = self.GET_CMD_ERR_MSG_MAP.get(
                get_cmd_res,
                "missing_err_msg"
            )
            err_code = get_cmd_res
            ugen.err_Q(f"{err_msg}: '{cmd_nm}'")
            self.write_to_stderr(buf_stderr.getvalue(), stderr_fl)
            return get_cmd_res

        # DEBUG: Command resolution time end
        _t_cmd_resln = time.perf_counter_ns() - _t_cmd_resln
        ugen.debug_Q(
            ugen.fmt_d_stmt(
                "time",
                "cmd_reslv",
                fmt_t_ns(self.debug_time_expo, _t_cmd_resln)
            )
        )

        return CmdReslnRes(*get_cmd_res)

    def hdl_op_stderr_redir(
        self,
        par_out: tuple[TH_TokGrp],
        tok_grp: TH_TokGrp,
        idx: int,
        old_stderr: io.TextIOBase,
        buf_stderr: io.StringIO
    ) -> tuple[TH_TokGrp, int, str] | int:
        """
        Handle the STDOUT redirection operation.

        :param par_out: Whole output from the parser for the whole input line
        :type par_out: tuple[TH_TokGrp]

        :param tok_grp: Current token group (one element of par_out)
        :type tok_grp: TH_TokGrp

        :param idx: Index of current token group in whole parser output
        :type idx: int

        :param old_stderr: Original STDERR stream
        :type old_stderr: io.TextIOBase

        :param buf_stderr: STDERR buffer created
        :type buf_stderr: io.StringIO

        :returns: If no errors were encountered, a tuple containing:
                      - the patched token group,
                      - the number of token groups to skip next and
                      - STDERR redirect output filename.
                  Else, an integer error code.
        :rtype: tuple[TH_TokGrp, int, str] | int
        """
        # CURSED
        try:
            nxt_grp, sp_chr = par_out[idx + 1]
            stderr_fl = nxt_grp[0]
        except IndexError:
            ugen.err_Q("Missing filename for STDERR redirection")
            return uerr.ERR_MISSING_FL_STDERR_REDIR

        # Add the next token group to the current token group, excluding the
        # STDERR redirect filename
        tok_grp.extend(nxt_grp[1 :])
        skip_grp = 1

        sys.stderr = buf_stderr
        # Loop through handlers and set their streams to the buffer created
        self.loop_set_lgr_streams(old_stderr, buf_stderr)
        return (tok_grp, skip_grp, stderr_fl)

    def child_proc(
        self,
        cmd_fn: TH_CmdFn,
        data: ugen.CmdData,
        w: int,
        stdin: str | None,
        old_stdout: io.TextIOBase,
        buf_stdout: io.StringIO
    ) -> ty.NoReturn:
        cmd_ret = self.rn_cmd_fn(cmd_fn, data)

        if type(cmd_ret) != int:
            ugen.crit("Last command returned non-integer")
            cmd_ret = uerr.ERR_CMD_RETD_NON_INT
        elif not (-2 ** 31 <= cmd_ret < 2 ** 31):
            ugen.crit("Command return value exceeds 32-bit integer limit")
            cmd_ret = uerr.ERR_RET_INT_TOO_LARGE

        stdin_sz = 0
        if sys.stdout != old_stdout:
            stdin_sz = buf_stdout.tell()
            stdin = buf_stdout.getvalue()
        # Pass command exit code, size of stdin buffer and
        # stdin buffer to parent process
        os.write(w, st.pack("!iQ", cmd_ret, stdin_sz))
        if stdin is None:
            os.write(w, "".encode())
        else:
            os.write(w, stdin.encode())
        os._exit(cmd_ret)

    def execute(self, ln: str) -> int:
        """
        Execute an input line.

        :param ln: Input line to execute.
        :type ln: str

        :returns: Integer error code.
        :rtype: int
        """
        # DEBUG: Full execution time start
        _t_full_exec = time.perf_counter_ns()

        par_out = tuple(self.parser.parse(ln))
        len_par_out = len(par_out)
        stdin = None
        stderr = None
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        buf_stdout = io.StringIO()
        buf_stderr = io.StringIO()

        # To prevent empty commands making previous command exit code as 0
        is_empty = True
        skip_grp = 0
        err_code = uerr.ERR_ALL_GOOD

        for idx, (tok_grp, sp_chr) in enumerate(par_out):
            ###
            ### SKIP TOKEN GROUPS ALREADY CONSUMED
            ###
            if skip_grp:
                skip_grp -= 1
                continue

            ugen.debug_Q(f"raw_toks: {tok_grp}")

            ###
            ### EMPTY INPUT LINE
            ###
            if not tok_grp:
                continue
            is_empty = False
            cmd = tok_grp[0]
            cmd_nm = cmd.val
            if cmd_nm == "snoo":
                ugen.fatal_Q("Beauty overload", uerr.ERR_BEAUTY_OVERLD)

            ###
            ### PIPING, REDIRECTION AND OTHER OPERATIONS
            ###
            buf_stdout = io.StringIO()
            buf_stderr = io.StringIO()
            stderr_fl = None

            if sp_chr.val == "|":
                sys.stdout = buf_stdout

            elif sp_chr.val == "?":
                op_res = self.hdl_op_stderr_redir(
                    par_out,
                    tok_grp,
                    idx,
                    old_stderr,
                    buf_stderr
                )
                if isinstance(op_res, int):
                    err_code = err_code or op_res
                    break
                tok_grp = op_res[0]
                skip_grp += op_res[1]
                stderr_fl = op_res[2]

            ###
            ### RESOLVE COMMAND
            ###
            cmd_resln_res = self.cmd_resln(cmd_nm, buf_stderr, stderr_fl)
            if isinstance(cmd_resln_res, int):
                err_code = err_code or cmd_resln_res
                break
            cmd_fn = cmd_resln_res.cmd_fn
            cmd_spec = cmd_resln_res.cmd_spec
            cmd_src = cmd_resln_res.cmd_src

            ###
            ### CLASSIFY PARSER OUTPUT INTO ARGUMENTS, OPTIONS AND FLAGS
            ###
            classi_res = self.classi_par_out(tok_grp, cmd_spec)
            if isinstance(classi_res, int):
                err_code = err_code or classi_res
                # Write to file only if STDERR redirection is happening. Note
                # that stderr_fl will be defined only if stderr_redir is True
                self.write_to_stderr(buf_stderr.getvalue(), stderr_fl)
                break
            args, opts, flags = classi_res
            ugen.debug_Q(f"cmd:   '{cmd_nm}'")
            ugen.debug_Q(f"args:  {args}")
            ugen.debug_Q(f"opts:  {opts}")
            ugen.debug_Q(f"flags: {flags}")

            ###
            ### ACTUAL COMMAND EXECUTION
            ###
            # DEBUG: Actual command execution time start
            _t_actual = time.perf_counter_ns()

            data = ugen.CmdData(
                cmd_nm,
                tuple(args),
                opts,
                tuple(flags),
                self.cmd_reslvr,
                self.env_vars,
                self.ext_cached_cmds,
                term_sz=os.get_terminal_size(),
                stdin=stdin,
                is_tty=True
            )
            stdin = None
            stderr = None

            try:
                # External command, run in separate process
                if cmd_src == "external":
                    r, w = os.pipe()
                    pid = os.fork()

                    # Forked child process
                    if pid == 0:
                        os.close(r)
                        self.child_proc(
                            cmd_fn,
                            data,
                            w,
                            stdin,
                            old_stdout,
                            buf_stdout
                        )
                    # Some issue, cannot fork
                    elif pid < 0:
                        ugen.crit(
                            "Failed to fork current process; try re-running the command"
                        )
                        err_code = err_code or uerr.ERR_CANT_FORK_PROC
                    # Parent process
                    else:
                        # Do NOT rely on the child's exit code! It can be wrong
                        # because the OS only recognises 8-bit integers for
                        # exit codes
                        os.close(w)
                        # 4 bytes for command return code
                        # 8 bytes for the output length
                        # "Output length" bytes for the output
                        ret_packed = self.rd_from_fd(r, 4)
                        ret_code = st.unpack("!i", ret_packed)[0]
                        stdin_sz_packed = self.rd_from_fd(r, 8)
                        stdin_sz = st.unpack("!Q", stdin_sz_packed)[0]
                        # Absolutely no idea how this can possibly work, but it
                        # does. In the current design, no and empty pipe output
                        # both have stdin_sz 0. Don't know how the program's
                        # able to differentiate between no and empty pipe
                        # output.
                        stdin = self.rd_from_fd(r, stdin_sz).decode()
                        os.close(r)
                        err_code = err_code or ret_code

                # Built-in command, run in same process as the interpreter
                else:
                    cmd_ret = self.rn_cmd_fn(cmd_fn, data)
                    stdin = buf_stdout.getvalue()
                    err_code = err_code or cmd_ret

            # Restore output streams to original ones
            finally:
                sys.stdout = old_stdout

                # Update stderr only if STDERR redirection is done
                if sys.stderr is not old_stderr:
                    stderr = buf_stderr.getvalue()
                sys.stderr = old_stderr
                # Loop through the handlers and restore their streams to
                # original STDERR
                self.loop_set_lgr_streams(buf_stderr, old_stderr)

            self.write_to_stderr(stderr, stderr_fl)

            # DEBUG: Actual command execution time end
            _t_actual = time.perf_counter_ns() - _t_actual
            ugen.debug_Q(
                ugen.fmt_d_stmt(
                    "time",
                    "actual_exec",
                    fmt_t_ns(self.debug_time_expo, _t_actual)
                )
            )

            ugen.debug_Q(f"env_vars:")
            # TODO: Remove!
            for i in self.env_vars:
                ugen.debug_Q(ugen.fmt_d_stmt("env_var", str(i)))

        # DEBUG: Full execution time end
        _t_full_exec = time.perf_counter_ns() - _t_full_exec
        ugen.debug_Q(
            ugen.fmt_d_stmt(
                "time",
                "full_exec", fmt_t_ns(self.debug_time_expo, _t_full_exec)
            )
        )

        # Restore old STDOUT and STDERR, and restore log handlers' streams
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        self.loop_set_lgr_streams(buf_stderr, old_stderr)

        if is_empty:
            return self.env_vars.get("_LAST_RET_")
        return err_code

    def rn_cmd_fn(
        self,
        cmd_fn: TH_CmdFn,
        data: ugen.CmdData
    ) -> int:
        """
        Run a command function.

        :param cmd_fn: Command function to execute.
        :type cmd_fn: TH_CmdFn

        :param data: Data to be passed to the command function.
        :type data: utils.gen.CmdData

        :returns: Integer error code.
        :rtype: int
        """
        cmd_ret = uerr.ERR_ALL_GOOD

        try:
            cmd_ret = cmd_fn(data)
        # Variable type mismatch
        except ugen.InvVarTypErr as e:
            cmd_ret = cmd_ret or uerr.ERR_ENV_VAR_INV_TYP
            ugen.err_Q(
                f"Invalid variable type for '{e.var_nm}'; expected '{e.var_typ.__name__}', got '{e.got_typ.__name__}'"
            )
        # Invalid variable name
        except ugen.InvVarNmErr as e:
            cmd_ret = cmd_ret or uerr.ERR_ENV_VAR_INV_NM
            ugen.err_Q(f"Invalid variable name: '{e.var_nm}'")
        # Unknown variable
        except ugen.UnkVarErr as e:
            cmd_ret = cmd_ret or uerr.ERR_ENV_UNK_VAR
            ugen.err_Q(f"Unknown variable: '{e.var_nm}'")
        # Other exceptions raised
        except Exception as e:
            cmd_ret = cmd_ret or uerr.ERR_CMD_RNTIME_ERR
            ugen.crit_Q(f"Errant command: '{data.cmd_nm}'")
            ugen.crit_Q(f"Raised {e.__class__.__name__}")
            ugen.crit_Q(f"Message: {e}")
            ugen.crit_Q(tb.format_exc())
        # Command tried to quit
        except SystemExit as e:
            cmd_ret = cmd_ret or uerr.ERR_CMD_SYS_EXIT
            ugen.crit_Q(f"Abnormal exit: '{data.cmd_nm}'")
            ugen.crit_Q("Raised SystemExit")
            ugen.crit_Q(f"Message: {e}")
            ugen.crit_Q(tb.format_exc())

        return cmd_ret
