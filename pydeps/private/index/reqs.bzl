"Read requirements.txt and produce a repository with a variable that contains just the input requirements."

def _format_pins(pins):
    return "\n".join(["    \"{pin}\",".format(pin = pin) for pin in pins])

def _in_impl(rctx):
    pins = []
    types = []

    for file in rctx.attr.files:
        contents = rctx.read(file)
        for line in contents.split("\n"):
            if line.startswith("#") or line == "":
                continue

            if ";" in line:
                line, _ = line.split(";")

            if "~=" in line:
                req, _ = line.split("~=")
            elif "==" in line:
                req, _ = line.split("==")
            elif "<=" in line:
                req, _ = line.split("<=")
            else:
                continue

            pin = req.split("[")[0]

            if pin.startswith("types-") or pin.endswith("-stubs"):
                types.append(pin)
            else:
                pins.append(pin)

    rctx.template("BUILD.bazel", rctx.attr._build_template, {
        "{{pip_requirements}}": str(rctx.attr.pip_requirements),
    })
    rctx.template("pins.bzl", rctx.attr._pins_template, {
        "{{pins}}": _format_pins(pins),
        "{{types}}": _format_pins(types),
    })

requirements_txt = repository_rule(
    attrs = {
        "files": attr.label_list(mandatory = True, allow_files = True),
        "pip_requirements": attr.label(mandatory = True),
        "_build_template": attr.label(default = "//pydeps/private/index:templates/BUILD.bazel.template", allow_single_file = True),
        "_pins_template": attr.label(default = "//pydeps/private/index:templates/pins.bzl.template", allow_single_file = True),
    },
    implementation = _in_impl,
)
