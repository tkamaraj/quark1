import typing as ty


def pprn(obj: ty.Any, depth: int = 0, indent_sz: int = 4, comma: bool = False) -> None:
    """
    Pretty print function.

    :param obj: The object to pretty print.
    :type obj: ty.Any

    :param depth: The indentation
    """
    pad = " " * (depth * indent_sz)

    if isinstance(obj, list):
        print(pad + "[")
        for i in obj:
            pprn(i, depth=depth + 1, comma=True)
        print(pad + "]" + ("," if comma else ""))
    elif isinstance(obj, tuple):
        print(pad + "(")
        for i in obj:
            pprn(i, depth=depth + 1, comma=True)
        print(pad + ")" + ("," if comma else ""))
    elif isinstance(obj, set):
        print(pad + "{")
        for i in obj:
            pprn(i, depth=depth + 1, comma=True)
        print(pad + "}" + ("," if comma else ""))
    elif isinstance(obj, dict):
        print(pad + "{")
        for key in obj:
            pprn(f"{key}: {obj[key]}", depth=depth + 1, comma=True)
        print(pad + "}" + ("," if comma else ""))
    else:
        print(pad + str(obj) + "," if comma else "")

