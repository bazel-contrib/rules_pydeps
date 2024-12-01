from __future__ import annotations

import dataclasses
import pathlib
import sys
from collections import defaultdict

import click

from pydeps.private.bazel import external_deps as ed
from pydeps.private.bazel import requirement as br
from pydeps.private.bazel import targets as bt
from pydeps.private.py import python_module as pym
from pydeps.private.py import source_files as pys


@dataclasses.dataclass(frozen=True)
class DependencyReport:
    referenced_deps: set[str]
    """Dependencies the source files reference."""

    unreferenced_deps: set[str]
    """Dependencies the target declares but the source files do not reference."""

    used_runtime_deps: set[str]
    """Dependencies the target declares as runtime dependencies but the source files reference."""

    missing_deps: set[str]
    """Dependencies the source files references that the target does not declare."""

    # python modules
    unresolved_modules: set[pym.PythonModule]
    """Modules the source files reference that are not in any declared dependencies."""


def create_module_index(deps: set[str]) -> dict[pym.PythonModule, bt.BazelTarget]:
    """
    Convert aspect provided set of (target)=(filename) to an de-duplicated
    index of (python module)->(requirement).
    """
    # a map of Bazel requirement to the modules it contains
    target_to_modules: dict[bt.BazelTarget, set[pym.PythonModule]] = defaultdict(set)
    for dep in deps:
        [req, filename] = dep.split("=", 2)
        module = pym.PythonModule.from_path(pathlib.Path(filename))
        target_to_modules[bt.BazelTarget(req)].add(module)

    # a map of Python module to the Bazel requirement needed to import it
    module_index: dict[pym.PythonModule, bt.BazelTarget] = dict()
    for req, modules in target_to_modules.items():
        for module in modules:
            if module not in module_index:
                module_index[module] = req
            else:
                # multiple targets claim the source file, prefer the more specific target
                existing_req = module_index[module]
                target_1_weight = len(target_to_modules[existing_req])
                target_2_weight = len(target_to_modules[req])
                if target_2_weight < target_1_weight:
                    module_index[module] = req

    return module_index


def diff_deps(
    *,
    internal_module_index: dict[pym.PythonModule, bt.BazelTarget],
    external_module_index: dict[pym.PythonModule, br.Requirement],
    python_imported_deps: pys.SourceFileDependencies,
    runtime_deps: set[str],
    declared_deps: set[str],
) -> DependencyReport:
    resolved_internal_deps: set[str] = set()
    resolved_external_deps: set[br.Requirement] = set()
    unresolved_modules: set[pym.PythonModule] = set()
    for module in python_imported_deps.deps:
        if module in internal_module_index:
            resolved_internal_deps.add(internal_module_index[module])
        elif module in external_module_index:
            resolved_external_deps.add(external_module_index[module])
        else:
            unresolved_modules.add(module)

    all_resolved_deps = set(
        [str(d) for d in resolved_internal_deps]
        + [d.render() for d in resolved_external_deps]
    )
    extra_deps = declared_deps - runtime_deps - all_resolved_deps
    missing_deps = all_resolved_deps - declared_deps
    used_runtime_deps = set.intersection(runtime_deps, all_resolved_deps)

    return DependencyReport(
        referenced_deps=all_resolved_deps,
        unreferenced_deps=extra_deps,
        used_runtime_deps=used_runtime_deps,
        missing_deps=missing_deps,
        unresolved_modules=unresolved_modules,
    )


def check_deps(
    *,
    target: str,
    kind: str,
    sources: set[str],
    declared_deps: set[str],
    runtime_deps: set[str],
    internal_module_index: dict[pym.PythonModule, bt.BazelTarget],
    external_module_index: dict[pym.PythonModule, br.Requirement],
    tags: set[str],
) -> str:
    errors = ""
    python_imported_deps = pys.get_dependencies(
        pathlib.Path(".").absolute(), set(pathlib.Path(src) for src in sources)
    )

    report = diff_deps(
        internal_module_index=internal_module_index,
        external_module_index=external_module_index,
        python_imported_deps=python_imported_deps,
        runtime_deps=runtime_deps,
        declared_deps=declared_deps,
    )

    if kind == "py_test":
        report.used_runtime_deps.discard('requirement("pytest")')

    if len(report.unreferenced_deps) > 0:
        details = " - " + "\n - ".join(sorted(report.unreferenced_deps))
        errors += f"Bazel target {target} declares dependencies that are not used:\n{details}\n\n"

    if len(report.missing_deps) > 0:
        details = " - " + "\n - ".join(sorted([str(d) for d in report.missing_deps]))
        errors += f"Bazel target {target} is missing requirements:\n{details}\n\n"

    if len(report.unresolved_modules) > 0:
        details = " - " + "\n - ".join(
            sorted([str(d) for d in report.unresolved_modules])
        )
        errors += f"Sources in Bazel target {target} have imports that could not be resolved:\n{details}\n\n"

    if len(report.used_runtime_deps) > 0:
        details = " - " + "\n - ".join(sorted(report.used_runtime_deps))
        errors += f"Bazel target {target} depends on not_imported_deps:\n{details}\n\n"

    return errors


def _resolve_bazel_labels(
    external_label_index: dict[str, br.Requirement], labels: tuple[str, ...]
) -> set[str]:
    depset = set()
    for dep in labels:
        if dep in external_label_index:
            depset.add(external_label_index[dep].render())
        else:
            depset.add(dep.removeprefix("@@"))
    return depset


def _get_args(args_file: str, required_first_arg: str) -> list[str]:
    """Get the arguments list from the provided file, removing the first argument"""
    with open(args_file, "r") as f:
        args = f.read().splitlines()
        if len(args) < 1:
            print("No arguments were passed.", file=sys.stderr)
            sys.exit(1)

        first = args.pop(0)
        if first != required_first_arg:
            print(f"First argument must be `{required_first_arg}`", file=sys.stderr)
            sys.exit(1)

        return args


@click.group(invoke_without_command=True)
@click.option("--args-file", "-a", "args_file")
@click.pass_context
def main(ctx: click.Context, args_file: str) -> None:
    """Entrypoint that enables indirection through an arguments file."""
    if ctx.invoked_subcommand is None:
        aspect.main(args=_get_args(args_file, "aspect"))


@main.command()
@click.option("--target", "-g", "target")
@click.option("--kind", "-k", "kind")
@click.option("--source", "-s", "sources", multiple=True)
@click.option("--dependency", "-d", "declared_deps", multiple=True)
@click.option("--runtime-dependency", "-r", "runtime_deps", multiple=True)
@click.option("--dep-file", "-f", "dep_files", multiple=True)
@click.option("--index", "-i", "index", multiple=True)
@click.option("--output-file", "-o")
@click.option("--tag", "-t", "tags", multiple=True)
def aspect(
    target: str,
    kind: str,
    sources: tuple[str, ...],
    declared_deps: tuple[str, ...],
    runtime_deps: tuple[str, ...],
    dep_files: tuple[str, ...],
    index: tuple[str, ...],
    output_file: str,
    tags: tuple[str, ...],
) -> None:
    if len(index) > 1:
        raise RuntimeError(f"Found more than one pip_deps_index. {set(index)}")
    pip_deps_index = list(index)[0]

    internal_module_index = create_module_index(set(dep_files))
    external_module_index = ed.module_index(pip_deps_index)
    external_label_index = ed.label_index(pip_deps_index)

    errors = check_deps(
        target=target,
        kind=kind,
        sources=set(sources),
        declared_deps=_resolve_bazel_labels(external_label_index, declared_deps),
        runtime_deps=_resolve_bazel_labels(external_label_index, runtime_deps),
        internal_module_index=internal_module_index,
        external_module_index=external_module_index,
        tags=set(tags),
    )

    with open(output_file, "w") as f:
        if errors:
            print(errors, file=f)
            print(errors, file=sys.stderr)

    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
