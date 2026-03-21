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
import utils.err_codes as uerr

if ty.TYPE_CHECKING:
    import parser.internals as pint


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
        # TODO: Change!
        raise NotImplementedError("FOOL!")

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

        ugen.warn("Exercise caution when running untrusted commands")

        self.ext_cached_cmds = {}

        self.cfg = cfg
        self.stderr_ansi = stderr_ansi
        self.debug_time_expo = debug_time_expo
        self.log_lvl = log_lvl
        self.env_vars = iint.Env()
        self.parser = peng.Parser()
        self.cmd_reslvr = icrsr.CmdReslvr(self.ext_cached_cmds,
                                          self.debug_time_expo)

        self.usr_dir = pl.Path("~").expanduser()
        self.uid = str(os.getuid())
        self.usernm = pwd.getpwuid(int(self.uid)).pw_name
        self.is_usr_root = self.uid == "0"

        self.env_vars.set("_USR_DIR_", self.usr_dir)
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

        os.chdir(self.usr_dir)

        # Interpreter initialisation time end
        _t_intrpr_init = time.perf_counter_ns() - _t_intrpr_init

        ugen.debug_Q(
            ugen.fmt_d_stmt("time", "tot_init_intrpr",
                            fmt_t_ns(self.debug_time_expo, _t_intrpr_init))
        )

    def reslv_prompt(self, prompt: str | None) -> str:
        # Pretty bad design, I guess, handling the None case for var prompt in
        # this method, but I don't want to clutter up the main file
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
                    f"^{re.escape(str(self.env_vars.get('_USR_DIR_')))}",
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
                    f"^{self.env_vars.get('_USR_DIR_')}",
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
        self.env_vars.set("_PROMPT_", self.cfg.prompt)
        pths = []
        for i in self.cfg.pth:
            if i == ".":
                pths.append(uconst.BIN_PTH)
            else:
                pths.append(str(pl.Path(i).expanduser().resolve()))
        self.env_vars.set("_PTH_", tuple(pths))

    def ld_all_ext_mods(self) -> None:
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
            tuple[ty.Callable[[ugen.CmdData], int], ugen.CmdSpec] | int,
            str
        ]:

        builtin_cmd = self.cmd_reslvr.get_builtin_cmd(cmd_nm)
        if isinstance(builtin_cmd, tuple):
            return (builtin_cmd, "built-in")

        ext_cmd = self.cmd_reslvr.get_ext_cmd(cmd_nm,
                                              env_vars.get("_PTH_"),
                                              ext_cached_cmds)
        return (ext_cmd, "external")

    def classi_parser_output(
            self,
            tok_grp: "list[pint.Tok]",
            cmd_spec: ugen.CmdSpec
        ) -> tuple[tuple[str, ...], dict[str, str], tuple[str, ...]] | int:
        """
        Helper function to classify parser output into arguments, flags and
        options.

        :param tok_grp: Token group yielded from the parser
        :type tok_grp: list[parser.internals.Tok]

        :param cmd_spec: Command spec from the command file
        :type cmd_spec: utils.gen.CmdSpec

        :returns: If no errors occured, a tuple containing:
            - a tuple of strings (argument array),
            - a dictionary of string keys and string values (option array) and
            - a tuple of strings (flag array).
            Otherwise, an error code.
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
                if tok_val not in cmd_spec.opts \
                        and tok_val not in cmd_spec.flags:
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
        chunks = []
        total = 0

        while total < n:
            chunk = os.read(fd, n - total)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)

        return b"".join(chunks)

    def execute(self, ln: str) -> int:
        """
        Execute input line.

        :param ln: The input line to execute.
        :type ln: str

        :returns: An error code.
        :rtype: int
        """
        # DEBUG: Full execution time start
        _t_full_exec = time.perf_counter_ns()

        parser_out = tuple(self.parser.parse(ln))
        len_parser_out = len(parser_out)
        stdin = None
        stderr = None
        # To prevent empty commands making previous command exit code as 0
        is_empty = True
        skip_grp = 0
        err_code = uerr.ERR_ALL_GOOD

        for idx, (tok_grp, sp_chr) in enumerate(parser_out):
            # Skip groups already consumed
            if skip_grp:
                skip_grp -= 1
                continue

            ugen.debug_Q(f"raw_toks: {tok_grp}")

            buf_stdout = io.StringIO()
            buf_stderr = io.StringIO()

            # Empty input line
            if not tok_grp:
                continue
            is_empty = False
            cmd = tok_grp[0]
            cmd_nm = cmd.val
            if cmd_nm == "snoo":
                ugen.fatal_Q("Beauty overload", uerr.ERR_BEAUTY_OVERLD)

            # DEBUG: Command resolution time start
            _t_cmd_resln = time.perf_counter_ns()

            # Get command function and spec
            get_cmd_res, cmd_src = self.get_cmd(
                cmd_nm,
                self.ext_cached_cmds,
                self.cmd_reslvr,
                self.env_vars
            )
            if isinstance(get_cmd_res, int):
                err_msg = self.GET_CMD_ERR_MSG_MAP.get(get_cmd_res,
                                                       "missing_err_msg")
                ugen.err_Q(f"{err_msg}: '{cmd_nm}'")
                return get_cmd_res

            # DEBUG: Command resolution time end
            _t_cmd_resln = time.perf_counter_ns() - _t_cmd_resln
            ugen.debug_Q(
                ugen.fmt_d_stmt("time", "cmd_reslv",
                                fmt_t_ns(self.debug_time_expo, _t_cmd_resln))
            )

            cmd_fn, cmd_spec = get_cmd_res

            # DEBUG: Actual command execution time start
            _t_actual = time.perf_counter_ns()

            old_stdout = sys.stdout
            old_stderr = sys.stderr

            # Piping
            if sp_chr.val == "|":
                sys.stdout = buf_stdout

            # STDERR redirection
            elif sp_chr.val == "?":
                # Get the next token to 
                # CURSED
                try:
                    nxt_grp, sp_chr = parser_out[idx + 1]
                    stderr_fl = nxt_grp[0]
                except IndexError:
                    err_code = err_code or uerr.ERR_MISSING_FL_STDERR_REDIR
                    ugen.err_Q("Missing filename for STDERR redirection")
                    break
                # Add the next token group to the current token group,
                # excluding the STDERR redirect filename
                tok_grp.extend(nxt_grp[1 :])
                skip_grp += 1

                sys.stderr = buf_stderr
                # Loop through the handlers and set their streams to the
                # buffer created
                for lgr in lg.Logger.manager.loggerDict.values():
                    if isinstance(lgr, lg.PlaceHolder):
                        continue
                    for hdlr in lgr.handlers:
                        if hdlr.stream is old_stderr:
                            hdlr.stream = buf_stderr

            # STDOUT redirection
            elif sp_chr.val == ">":
                pass

            # Classify parser output into arguments, options and flags
            classi_res = self.classi_parser_output(tok_grp, cmd_spec)
            if isinstance(classi_res, int):
                return classi_res
            args, opts, flags = classi_res

            # TODO: Remove!
            ugen.debug_Q(f"cmd:   '{cmd_nm}'")
            ugen.debug_Q(f"args:  {args}")
            ugen.debug_Q(f"opts:  {opts}")
            ugen.debug_Q(f"flags: {flags}")

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
                        # No need to read in child process
                        os.close(r)
                        cmd_ret = self.rn_cmd_fn(cmd_fn, data)
                        if type(cmd_ret) != int:
                            ugen.crit("Last command returned non-integer")
                            cmd_ret = uerr.ERR_CMD_RETD_NON_INT
                        elif not (-2 ** 31 <= cmd_ret < 2 ** 31):
                            ugen.crit(
                                "Command return value exceeds 32-bit integer limit"
                            )
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

                    # Some issue, cannot fork
                    elif pid < 0:
                        ugen.crit(
                            "Failed to fork current process; try re-running the command"
                        )
                        err_code = err_code or uerr.ERR_CANT_FORK_PROC

                    # Parent process
                    else:
                        # Do NOT rely on the child's exit code! It can be wrong
                        # because the OS only recognises 8-bit ints for exit
                        # codes
                        # No need to write in parent process
                        os.close(w)
                        ret_packed = self.rd_from_fd(r, 4)
                        ret_code = st.unpack("!i", ret_packed)[0]
                        stdin_sz_packed = self.rd_from_fd(r, 8)
                        stdin_sz = st.unpack("!Q", stdin_sz_packed)[0]
                        # I have absolutely no idea how this can possibly work,
                        # but it does. In this current design, no pipe output
                        # and empty pipe output both have stdin_sz 0. I don't
                        # know how the program is able to differentiate between
                        # no pipe output and empty pipe output. No fucking idea
                        # how.
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
                for lgr in lg.Logger.manager.loggerDict.values():
                    if isinstance(lgr, lg.PlaceHolder):
                        continue
                    for hdlr in lgr.handlers:
                        # This check is needed, because otherwise, the file
                        # logger's STDERR is changed too
                        if hdlr.stream is buf_stderr:
                            hdlr.stream = old_stderr

            # If stderr is not None, then write to the file named the token
            # just after the '?' symbol
            if stderr is not None:
                try:
                    with open(stderr_fl.val, "w") as f:
                        if self.stderr_ansi:
                            f.write(stderr)
                        else:
                            f.write(ugen.rm_ansi("", stderr))
                    continue
                except PermissionError:
                    err_code = err_code or uerr.ERR_PERM_DENIED
                    ugen.err_Q(f"Access denied; cannot write STDERR to file \"{stderr_fl.val}\"")
                except FileNotFoundError:
                    err_code = err_code or uerr.ERR_EMPTY_FL_REDIR
                    ugen.err_Q(f"Empty file; cannot write STDERR to file \"{stderr_fl.val}\"")
                except Exception as e:
                    err_code = err_code or uerr.ERR_UNK_ERR
                    ugen.fatal_Q(
                        f"Unknown error ({e}); cannot write STDERR to file \"{stderr_fl.val}\"",
                        uerr.ERR_UNK_FATAL,
                        tb.format_exc()
                    )

            # DEBUG: Actual command execution time end
            _t_actual = time.perf_counter_ns() - _t_actual
            ugen.debug_Q(
                ugen.fmt_d_stmt("time", "actual_exec",
                                fmt_t_ns(self.debug_time_expo, _t_actual))
            )

            ugen.debug_Q(f"env_vars:")
            # TODO: Remove!
            for i in self.env_vars:
                ugen.debug_Q(ugen.fmt_d_stmt("env_var", str(i)))

        # DEBUG: Full execution time end
        _t_full_exec = time.perf_counter_ns() - _t_full_exec
        ugen.debug_Q(
            ugen.fmt_d_stmt("time", "full_exec",
                            fmt_t_ns(self.debug_time_expo, _t_full_exec))
        )

        if is_empty:
            return self.env_vars.get("_LAST_RET_")
        return err_code

    def rn_cmd_fn(
            self,
            cmd_fn: ty.Callable[[ugen.CmdData], int],
            data: ugen.CmdData
        ) -> int:
        cmd_ret = 0

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

