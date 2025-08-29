"""
Build a module index from provided arguments.

Note: this tool is intended to be run from a Bazel sandbox. YMMV when run elsewhere.
"""

import dataclasses
import json
import pathlib
import sys
from typing import Final

import click

from pydeps.private.py import python_module as pm

_IGNORE_MODULES: Final = {
    pm.PythonModule("tests"),
}


# TODO(mark): we should teach this class to have a real serde and move it to a library
#  so that it can be used for reading (elsewhere) as well as writing (here)
@dataclasses.dataclass(frozen=True)
class IndexFile:
    module_to_requirement: dict[str, str]
    label_to_requirement: dict[str, str]


def _filter_dep_file(file: str) -> bool:
    return "__pycache__" in file or ".dist-info/" in file or file == "py.py"


def _normalize_dep(raw: str) -> str:
    return raw.replace("_", "-").lower()


def _get_args(args_file: str, required_first_arg: str) -> list[str]:
    "Get the arguments list from the provided file, removing the first argument"
    with open(args_file, "r") as f:
        args = f.read().splitlines()
        if len(args) < 1:
            click.echo("No arguments were passed.", file=sys.stderr)
            sys.exit(1)

        first = args.pop(0)
        if first != required_first_arg:
            click.echo(
                f"First argument must be `{required_first_arg}`", file=sys.stderr
            )
            sys.exit(1)

        return args


@click.group(invoke_without_command=True)
@click.option("--args-file", "-a", "args_file")
@click.pass_context
def cli(ctx: click.Context, args_file: str) -> None:
    "Entrypoint that enables indirection through an arguments file."
    if ctx.invoked_subcommand is None:
        index.main(args=_get_args(args_file, "index"))


@cli.command()
@click.option("--module", type=(str, str), multiple=True)
@click.option("--src-file", type=(str, str), multiple=True)
@click.option("--output")
def index(
    module: tuple[tuple[str, str], ...],
    src_file: tuple[tuple[str, str], ...],
    output: str,
) -> None:
    index: dict[pm.PythonModule, str] = dict()
    for file, dep in list(src_file):
        if _filter_dep_file(file):
            continue

        try:
            mod = pm.PythonModule.from_path(pathlib.Path(file))
        except ValueError as ve:
            COLOR_PURPLE = "\033[35m"
            COLOR_RESET = "\033[0m"
            print(f"{COLOR_PURPLE}WARNING:{COLOR_RESET} {ve}")
            continue
        req = _normalize_dep(dep)

        if mod in _IGNORE_MODULES:
            continue

        if mod not in index:
            index[mod] = req
        elif index[mod] != req:
            raise ValueError(
                f"Found duplicate module ownership of module {mod} in {index[mod]} and {req}"
            )

    index_file = IndexFile(
        module_to_requirement={
            str(k): v for k, v in sorted(index.items(), key=lambda tup: tup[1])
        },
        label_to_requirement=dict(sorted(module, key=lambda tup: tup[0])),
    )

    with open(output, "w+") as outfile:
        json.dump(dataclasses.asdict(index_file), outfile, indent=True)


if __name__ == "__main__":
    cli()
