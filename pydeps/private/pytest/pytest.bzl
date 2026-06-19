"pytest macro"

load("@python_versions//3.13:defs.bzl", "py_test")

_TEST_RUNNER_ENTRYPOINT = "//pydeps/private/pytest:runner.py"

def _create_args(srcs):
    # If `srcs` references in a file in another package, try to convert the label to a filename.
    src_files = []
    for src in srcs or []:
        if src.startswith("//"):
            src_files.append(src[2:].replace(":", "/"))
        else:
            src_files.append(native.package_name() + "/" + src)
    return src_files

def pytest_test(name, srcs, deps = None, data = None, args = None, env = None, tags = None):
    args = (
        (args if args != None else []) +
        ["-s", "--color=yes", "--junitxml=$$XML_OUTPUT_FILE"] +
        [arg for arg in _create_args(srcs) if arg.endswith(".py")]
    )

    py_test(
        name = name,
        srcs = srcs + [_TEST_RUNNER_ENTRYPOINT],
        main = _TEST_RUNNER_ENTRYPOINT,
        args = args,
        data = data,
        deps = deps,
        env = env,
        tags = tags,
    )
