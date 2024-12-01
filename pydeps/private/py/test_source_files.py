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
