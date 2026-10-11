import pathlib

import pytest

from pydeps.private.py import python_module as pm


def _assert_path_eq_module(path: str, module: str) -> None:
    assert pm.PythonModule.from_path(pathlib.Path(path)) == pm.PythonModule(module)


def test__init__non_mutating() -> None:
    assert str(pm.PythonModule("foo.bar.baz")) == "foo.bar.baz"


def test__from_path__init() -> None:
    _assert_path_eq_module("foo/bar/__init__.py", "foo.bar")


def test__from_path__py_extension() -> None:
    _assert_path_eq_module("foo/bar/baz.py", "foo.bar.baz")


def test__from_path__pyi_extension() -> None:
    _assert_path_eq_module("foo/bar/baz.pyi", "foo.bar.baz")


def test__from_path__so_extension() -> None:
    _assert_path_eq_module("lxml/etree.cpython-310-darwin.so", "lxml.etree")
    _assert_path_eq_module("ujson.cpython-310-darwin.so", "ujson")


def test__from_path__no_extension() -> None:
    _assert_path_eq_module("foo/bar", "foo.bar")


def test__from_path__raise_unknown() -> None:
    with pytest.raises(ValueError):
        pm.PythonModule.from_path(pathlib.Path("foo/bar/baz.tgz"))


def test__str__is_module() -> None:
    assert (
        str(pm.PythonModule.from_path(pathlib.Path("foo/bar/baz.py"))) == "foo.bar.baz"
    )


def test__ancestors__most_specific_first() -> None:
    assert pm.PythonModule("a.b.c").ancestors() == [
        pm.PythonModule("a.b.c"),
        pm.PythonModule("a.b"),
        pm.PythonModule("a"),
    ]
    assert pm.PythonModule("a").ancestors() == [pm.PythonModule("a")]
