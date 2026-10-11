from pydeps.private.bazel import requirement as br
from pydeps.private.bazel import targets as bt
from pydeps.private.enforcer import deps_cli
from pydeps.private.py import python_module as pm
from pydeps.private.py import source_files as sf


def _report(*imports: str) -> deps_cli.DependencyReport:
    return deps_cli.diff_deps(
        internal_module_index={
            pm.PythonModule("thm.lib"): bt.BazelTarget("//thm:lib"),
            pm.PythonModule("thm.lib.core"): bt.BazelTarget("//thm:lib"),
        },
        external_module_index={
            pm.PythonModule("yaml"): br.Requirement.from_raw(raw="pyyaml", kind=br.Kind.PIP),
        },
        python_imported_deps=sf.SourceFileDependencies(
            system=set(),
            local={pm.PythonModule("thm.app")},
            deps={pm.PythonModule(i) for i in imports},
        ),
        runtime_deps=set(),
        declared_deps={"//thm:lib", 'requirement("pyyaml")'},
    )


def test__diff_deps__name_imported_from_module_resolves_to_module() -> None:
    report = _report("thm.lib.core.helper", "yaml.safe_load")

    assert report.unresolved_modules == set()
    assert report.missing_deps == set()
    assert report.unreferenced_deps == set()


def test__diff_deps__submodule_still_wins_over_package() -> None:
    report = _report("thm.lib.core")

    assert report.referenced_deps == {"//thm:lib"}


def test__diff_deps__unknown_root_is_unresolved() -> None:
    report = _report("numpy.linalg.norm")

    assert report.unresolved_modules == {pm.PythonModule("numpy.linalg.norm")}
