"Tools for extracting dependency information from source files."

import dataclasses
import pathlib
import sys
from typing import override

import libcst as cst
from libcst import helpers as h
from libcst import metadata as cst_metadata

from pydeps.private.py import python_module as pm


@dataclasses.dataclass(frozen=True)
class SourceFileDependencies:
    system: set[pm.PythonModule]
    """Python system level dependencies"""

    local: set[pm.PythonModule]
    """Dependencies that are in the root source tree and part of the current target."""

    deps: set[pm.PythonModule]
    """Dependencies of the current target."""


class _ImportFinder(cst.BatchableMetadataProvider[str]):
    METADATA_DEPENDENCIES = (cst_metadata.PositionProvider,)

    def __init__(self) -> None:
        super().__init__()

    @override
    def visit_Import(self, node: cst.Import) -> None:
        for name in node.names:
            self.set_metadata(node, f"{h.get_full_name_for_node(name.name)}")

    @override
    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        if not isinstance(node.names, cst.ImportStar):
            for name in node.names:
                if node.module:
                    self.set_metadata(
                        node,
                        f"{h.get_full_name_for_node(node.module)}.{name.name.value}",
                    )


def _allow_non_module_init_imports(
    module_path: pathlib.Path, module_imports: set[str]
) -> set[str]:
    """
    Update `module_imports` to allow for __init__ files to handle explicit re-exporting.

    We special-case __init__ files to handle explicit re-exporting, such as:
        from thm.dwl._dataset import Dataset as Dataset

    The specific situation we wish to allow involves re-export of local modules
    or sub-modules. But, submodules must still appear as imports, so we re-write
    the concrete imports to be the init module's path plus one component.

    In the example above, our import finder discovers:
        thm.dwl._dataset.Dataset

    And we rewrite the import to
        thm.dwl._dataset

    To ensure that we correctly handle sub-module re-exports, which should still demand
    an import, we do not exclude local source modules in this method.
    """
    if module_path.name != "__init__.py":
        return module_imports

    adjusted_module_imports = set()
    module = str(pm.PythonModule.from_path(module_path))
    exclude = len(module.split(".")) + 1
    for import_ in module_imports:
        if import_.startswith(module):
            adjusted_module_imports.add(".".join(import_.split(".")[:exclude]))
        else:
            adjusted_module_imports.add(import_)

    return adjusted_module_imports


def _to_sfd(imports: set[str], local: set[pm.PythonModule]) -> SourceFileDependencies:
    system_deps: set[pm.PythonModule] = set()
    deps: set[pm.PythonModule] = set()

    for dep in imports:
        mod = pm.PythonModule(dep)
        path = dep.split(".")
        if path[0] == "__future__" or path[0] in sys.stdlib_module_names:
            system_deps.add(mod)
        elif mod not in local:
            deps.add(mod)

    return SourceFileDependencies(
        system=system_deps,
        local=local,
        deps=deps,
    )


def _get_sfd_for_str(
    content: str, path: pathlib.Path, local: set[pm.PythonModule]
) -> SourceFileDependencies:
    wrapper = cst.MetadataWrapper(cst.parse_module(content))
    imports = set(wrapper.resolve(_ImportFinder).values())
    imports = _allow_non_module_init_imports(path, imports)
    return _to_sfd(imports, local)


def _get_sfd_for_file(
    working_dir: pathlib.Path, path: pathlib.Path, local: set[pm.PythonModule]
) -> SourceFileDependencies:
    with open(working_dir.joinpath(path), "r") as file:
        return _get_sfd_for_str(file.read(), path, local)


def get_dependencies(
    working_dir: pathlib.Path, sources: set[pathlib.Path]
) -> SourceFileDependencies:
    """
    Returns a SourceFileDependencies record for the collection of sources.

    Args:
        working_dir: absolute path to the working directory/Python root.
        sources: set of relative paths to source files.

    Returns: a SourceFileDependencies descriptor of the source collection.
    """
    if not working_dir.is_absolute():
        raise ValueError(f"working_dir must be absolute, found {working_dir}")

    if any(src.is_absolute() for src in sources):
        raise ValueError(
            f"Some source files were provided with absolute paths, found: {sources}"
        )

    system: set[pm.PythonModule] = set()
    deps: set[pm.PythonModule] = set()

    # all source files in the provided set are considered local
    # and we turn the files into a set of modules
    local = {pm.PythonModule.from_path(src) for src in sources}

    for source in sources:
        sfd = _get_sfd_for_file(working_dir, source, local)
        system.update(sfd.system)
        deps.update(sfd.deps)

    return SourceFileDependencies(system=system, local=local, deps=deps)
