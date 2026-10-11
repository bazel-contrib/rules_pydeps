import pathlib

from pydeps.private.py import python_module as pm
from pydeps.private.py import source_files as sf


def _strip_prefix(content: str) -> str:
    return "\n".join([line.lstrip() for line in content.split("\n")])


def test__get_sfd_for_str__extracts_imports() -> None:
    sfd = sf._get_sfd_for_str(
        _strip_prefix(
            """
        import foo
        import foo.bar
        from foo import baz
        from thm import foo
        """
        ),
        pathlib.Path("thm/test/bar.py"),
        set(),
    )

    assert sfd.deps == {
        pm.PythonModule("foo"),
        pm.PythonModule("foo.bar"),
        pm.PythonModule("foo.baz"),
        pm.PythonModule("thm.foo"),
    }


def test__get_sfd_for_str__collects_every_name_of_a_from_import() -> None:
    sfd = sf._get_sfd_for_str(
        "from foo.bar import baz, qux\nfrom foo import *\n",
        pathlib.Path("thm/test/bar.py"),
        set(),
    )

    assert sfd.deps == {
        pm.PythonModule("foo.bar.baz"),
        pm.PythonModule("foo.bar.qux"),
        pm.PythonModule("foo"),
    }


def test__get_sfd_for_str__relative_imports_are_made_absolute() -> None:
    sfd = sf._get_sfd_for_str(
        _strip_prefix(
            """
        from . import sibling
        from .sibling import name
        from ..parent_mod import other
        """
        ),
        pathlib.Path("thm/pkg/sub/mod.py"),
        set(),
    )

    assert sfd.deps == {
        pm.PythonModule("thm.pkg.sub.sibling"),
        pm.PythonModule("thm.pkg.sub.sibling.name"),
        pm.PythonModule("thm.pkg.parent_mod.other"),
    }


def test__get_sfd_for_str__relative_import_from_init_uses_own_package() -> None:
    sfd = sf._get_sfd_for_str(
        "from .impl import thing\n",
        pathlib.Path("thm/pkg/__init__.py"),
        set(),
    )

    assert sfd.deps == {pm.PythonModule("thm.pkg.impl")}


def test__get_sfd_for_str__name_imported_from_local_module_is_local() -> None:
    sfd = sf._get_sfd_for_str(
        "from thm.pkg.impl import thing\n",
        pathlib.Path("thm/pkg/api.py"),
        {pm.PythonModule("thm.pkg.api"), pm.PythonModule("thm.pkg.impl")},
    )

    assert sfd.deps == set()
