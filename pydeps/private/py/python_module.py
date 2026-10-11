import pathlib
from typing import Any, override


class PythonModule:
    def __init__(self, module: str) -> None:
        self._module = module

    @classmethod
    def from_path(cls, path: pathlib.Path) -> "PythonModule":
        """
        Convert a path to a particular file to the corresponding Python module name.
        """
        if path.is_absolute():
            raise ValueError(f"Source file paths must be relative paths, found {path}")

        module = list(path.parts)
        if module[-1] == "__init__.py":
            module = module[:-1]
        elif module[-1].endswith(".py"):
            module[-1] = module[-1].removesuffix(".py")
        elif module[-1].endswith(".pyd"):
            module[-1] = module[-1].removesuffix(".pyd")
        elif module[-1].endswith(".pyi"):
            module[-1] = module[-1].removesuffix(".pyi")
        elif module[-1].endswith(".pyx"):
            module[-1] = module[-1].removesuffix(".pyx")
        elif module[-1].endswith(".so"):
            # these are files of the form:
            #   lxml/etree.cpython-310-darwin.so
            # and these capture the module
            #   lxml.etree
            # so we extract the `etree` component of the shared lib filename
            root, _ = module[-1].split(".", maxsplit=1)
            module[-1] = root
        elif "." not in module[-1]:
            # no suffix
            pass
        else:
            raise ValueError(f"Unsupported module path: {path}")

        return cls(".".join(module))

    def ancestors(self) -> list["PythonModule"]:
        "Return this module and each enclosing package, most specific first."
        parts = self._module.split(".")
        return [PythonModule(".".join(parts[:i])) for i in range(len(parts), 0, -1)]

    @override
    def __eq__(self, other: Any) -> bool:
        return isinstance(other, PythonModule) and self._module == other._module

    @override
    def __hash__(self) -> int:
        return hash(self._module)

    @override
    def __repr__(self) -> str:
        return f"PythonModule({self._module})"

    @override
    def __str__(self) -> str:
        return self._module
