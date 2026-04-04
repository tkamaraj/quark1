# QUARK

Quark is a command-line interpreter written in pure Python. It aims to be
extensible and easy to use. It supports minimal scripting with its own
scripting language. For advanced scripting, it uses Python.

## Building

Nuitka 4.0.5 is (currently) required for building the project.

    python -m pip install nuitka

Change to the directory `pc.py` is in and run the build script as:

    python ./pc.py ./main.py

~~See `python ./pc.py -h` for help.~~ The help text is not available as of now,
so please go through the source to find out what is supported and what options
are available.

Alternatively, pre-built binaries for the build script are also available.
Check the [Releases](https://github.com/tkamaraj/quark1/releases/) page.

## Usage

Use the `-h` flag for the help text.
