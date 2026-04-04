import importlib as il
import importlib.util as ilu
import inspect as ins
import os
import pathlib as pl
import pkgutil as pu
import time
import types
import typing as ty
import utils.consts as uconst
import utils.gen as ugen
import utils.err_codes as uerr

import intrpr.internals as iint


class CmdReslvr:
    def __init__(
            self,
            ext_cached_cmds: dict[str, iint.CmdCacheEntry],
            debug_time_expo: int
        ) -> None:

        self.builtin_cmds: dict[
            str,                                   # Command name
            tuple[
                ty.Callable[[ugen.CmdData], int],  # Command function
                ugen.CmdSpec,                      # Command spec
                ugen.HelpObj                       # Help string
            ]
        ]

        self.debug_time_expo = debug_time_expo
        self.builtin_cmds = {}
        self.gather_builtin_cmds(ext_cached_cmds)

    def fmt_t_ns(self, ns: int) -> str:
        if self.debug_time_expo == 3:
            char = "u"
        elif self.debug_time_expo == 6:
            char = "m"
        elif self.debug_time_expo == 0:
            char = "n"
        elif self.debug_time_expo == 9:
            char = ""
        else:
            raise NotImplementedError("FOOL!")

        return str(round(ns / 10 ** self.debug_time_expo, 3)) + char + "s"

    def _is_new_ld_reqd(
            self,
            fl_stat: os.stat_result,
            cache_entry: iint.CmdCacheEntry
        ) -> bool:
        return (
            fl_stat.st_mtime != cache_entry.mtime
            or fl_stat.st_size != cache_entry.sz
        )

    def ld_mod(
            self,
            cmd: str,
            ext_cached_cmds: dict[str, iint.CmdCacheEntry],
            dir_pths: tuple[str],
        ) -> types.ModuleType | int:
        """
        Load an external command file (module).

        :param cmd: The command name.
        :type cmd: str

        :param dir_pths: A tuple of paths to check for the module
        :type dir_pths: tuple[str]

        :returns: The module object if successful, integer error code
                  otherwise.
        :rtype: types.ModuleType | int
        """
        fl: pl.Path

        # DEBUG: Module load time start
        _t_mod_ld = time.perf_counter_ns()

        for dir_pth in dir_pths:
            fl_str = os.path.join(dir_pth, cmd + ".py")
            fl = pl.Path(fl_str).expanduser().resolve()
            fl_stat = None
            cache_entry = ext_cached_cmds.get(cmd)
            try:
                fl_stat = fl.stat(follow_symlinks=False)
            except FileNotFoundError as e:
                continue

            if cache_entry is not None \
                    and not self._is_new_ld_reqd(
                        fl_stat,
                        cache_entry
                    ):
                return cache_entry.mod

            mod_spec = ilu.spec_from_file_location(cmd, fl)
            if mod_spec is None or mod_spec.loader is None:
                continue

            # Try to load the module from the spec
            try:
                cmd_mod = ilu.module_from_spec(mod_spec)
                mod_spec.loader.exec_module(cmd_mod)
            # ImportError is raised if the spec has a exec_module() attribute but
            # not a create_module() attribute, which I understand nothing about
            # right now.
            # FileNotFoundError is raised by _io.open_code(...) in
            # importlib._bootstrap_external.py if the file is not found [called due
            # to loader.exec_module(...)]
            except (FileNotFoundError, ImportError) as e:
                continue
            except SyntaxError:
                return uerr.ERR_CMD_SYN_ERR
            except Exception as e:
                ugen.err(
                    f"Raised from the command resolver; command raised {e.__class__.__name__}"
                )
                ugen.err(e.__class__.__name__ + ": " + str(e))
                return uerr.ERR_CANT_LD_CMD_MOD
            # except RecursionError:
            #     return uerr.ERR_RECUR_ERR

            ext_cached_cmds[cmd] = iint.CmdCacheEntry(
                cmd,
                mod_spec,
                cmd_mod,
                fl_stat.st_size,
                fl_stat.st_mtime
            )

            # DEBUG: Module load time end
            _t_mod_ld = time.perf_counter_ns() - _t_mod_ld
            ugen.debug_Q(
                ugen.fmt_d_stmt("time", f"ld_mod {cmd}",
                                self.fmt_t_ns(_t_mod_ld))
            )

            return cmd_mod

        return uerr.ERR_BAD_CMD

    def gather_builtin_cmds(
        self,
        ext_cached_cmds: dict[str, iint.CmdCacheEntry]
    ) -> None:
        """
        Gather the built-in command functions, specs and help objects from
        individual modules.
        Edits the object attribute self.builtin_cmds.
        Intended to be used when this object is initialised.
        """
        # DEBUG: Load built-in commands time start
        _t_ld_bcmds = time.perf_counter_ns()

        num_lded_builtin = 0
        builtins_lded = []

        for mod_fl in pu.iter_modules([uconst.BUILTIN_PTH]):
            if mod_fl.name == "__init__":
                continue

            cmd_nm = mod_fl.name
            mod = il.import_module(f"intrpr.builtin_cmds.{cmd_nm}")
            help_obj = getattr(mod, "HELP")
            cmd_spec = getattr(mod, "CMD_SPEC")
            cmd_fn = getattr(mod, "run")

            self.builtin_cmds[cmd_nm] = (cmd_fn, cmd_spec, help_obj)
            builtins_lded.append(cmd_nm)
            num_lded_builtin += 1

        # DEBUG: Load built-in commands time end
        _t_ld_bcmds = time.perf_counter_ns() - _t_ld_bcmds

        ugen.debug_Q(ugen.fmt_d_stmt("ld_bltns", ", ".join(builtins_lded)))
        ugen.debug_Q(
            ugen.fmt_d_stmt("time", "tot_ld_bltns",
                            self.fmt_t_ns(_t_ld_bcmds))
        )
        ugen.info_Q(f"built-ins loaded: {num_lded_builtin}")

    def get_builtin_help(self, cmd: str) -> ugen.HelpObj | int:
        """
        Get the help string for a built-in command.

        :param cmd: The name of the command.
        :type cmd: str

        :returns: The help object if available, integer error code otherwise.
        :rtype: utils.gen.HelpObj | int
        """
        # TODO: Decide a better name for variable tmp
        tmp = self.builtin_cmds.get(cmd)
        if tmp is None:
            return uerr.ERR_BAD_CMD
        # Guaranteed to be available because it's fucking built-in
        help_obj = tmp[2]
        return help_obj

    def get_ext_help(
            self,
            cmd: str,
            ext_cached_cmds: dict[str, iint.CmdCacheEntry],
            pths: tuple[str, ...]
        ) -> ugen.HelpObj | int:
        """
        Get the help string from an external command file.

        :param cmd: The command name
        :type cmd: str

        :param pths: A tuple of paths to check for the command in
        :type pths: tuple[str]

        :returns: The help object, if it was found and valid, integer error
                  code otherwise
        :rtype: utils.gen.HelpObj | int
        """
        tmp_mod = self.ld_mod(cmd, ext_cached_cmds, pths)
        if isinstance(tmp_mod, int):
            return tmp_mod
        cmd_mod = tmp_mod

        if not hasattr(cmd_mod, "HELP"):
            return uerr.ERR_NO_HELP_OBJ

        help_obj = getattr(cmd_mod, "HELP")
        if not isinstance(help_obj, ugen.HelpObj):
            return uerr.ERR_INV_HELP_OBJ
        return help_obj

    def get_builtin_cmd(self, cmd: str) -> \
            tuple[ty.Callable[[ugen.CmdData], int], ugen.CmdSpec] | int:
        """
        Get a built-in command function and spec.
        You cannot live-reload (or whatever the fuck you call that) built-in
        commands.

        :param cmd: The command name.
        :type cmd: str

        :returns: If the built-in command and spec are valid, a tuple
                  containing:
            - the command run function, and
            - the command spec.
            Otherwise, an integer error code.
        :rtype: tuple[ty.Callable[[ugen.CmdData], int], ugen.CmdSpec] | int
        """
        # Note that built-in command functions and specs aren't validated,
        # because they are assumed valid. Because, well, they are built-in.
        # Duh. If they are not, that's really not my problem

        # TODO: Decide a better name for variable tmp
        tmp = self.builtin_cmds.get(cmd)
        if tmp is None:
            return uerr.ERR_BAD_CMD

        cmd_fn, cmd_spec, _ = tmp
        return cmd_fn, cmd_spec

    def get_ext_cmd(
            self,
            cmd: str,
            pths: tuple[str],
            ext_cached_cmds: dict[str, iint.CmdCacheEntry]
        ) -> tuple[ty.Callable[[ugen.CmdData], int], ugen.CmdSpec] | int:
        """
        Get an external command function and spec.
        A valid command file satisfies the following conditions:
        - Has a function with the name of the command, which accepts a single
          argument of type intrpr.internals.CmdData, and returns an int, and
        - Has a global variable CMD_SPEC, which is an instance of CmdSpec

        :param cmd: The command name.
        :type cmd: str

        :param pths: A tuple of paths to check for the command in.
        :type cmd: tuple[str]

        :returns: If a valid command file exists, a tuple containing:
            - the command run function, and
            - the command spec.
            Otherwise, an integer error code.
        :rtype: tuple[ty.Callable[[ugen.CmdData], int], ugen.CmdSpec] | int
        """
        # Load command file
        tmp_mod = self.ld_mod(cmd, ext_cached_cmds, pths)
        if isinstance(tmp_mod, int):
            return tmp_mod
        cmd_mod = tmp_mod

        # Check for command function and spec
        has_cmd_fn = hasattr(cmd_mod, "run")
        has_cmd_spec = hasattr(cmd_mod, "CMD_SPEC")
        if not has_cmd_fn:
            return uerr.ERR_NO_CMD_FN
        if not has_cmd_spec:
            return uerr.ERR_NO_CMD_SPEC

        # Get command function and spec and validate both
        cmd_fn = getattr(cmd_mod, "run")
        cmd_spec = getattr(cmd_mod, "CMD_SPEC")
        is_fn_callable = callable(cmd_fn)
        is_num_fn_params_ok = (is_fn_callable
                               and cmd_fn.__code__.co_argcount == 1)
        is_spec_ok = isinstance(cmd_spec, ugen.CmdSpec)
        if not is_fn_callable:
            return uerr.ERR_UNCALLABLE_CMD_FN
        if not is_num_fn_params_ok:
            return uerr.ERR_INV_NUM_PARAMS
        if not is_spec_ok:
            return uerr.ERR_MALFORMED_CMD_SPEC

        return (cmd_fn, cmd_spec)

