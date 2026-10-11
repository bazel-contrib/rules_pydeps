"Rules to build a module index for rules_python pip deps."

load("@rules_python//python:py_info.bzl", "PyInfo")

def _map_dependency_file(item):
    file = item[0]
    module = item[1]

    path = file.short_path
    path = path.split("/site-packages/")[1]
    return "{file}\n{module}".format(file = path, module = module)

def _map_module(item):
    return "{label}\n{module}".format(label = item[0], module = item[1])

def _deps_index_impl(ctx):
    output_file = ctx.actions.declare_file(ctx.attr.name)

    modules = {}
    dependency_files = {}
    for dep, module in ctx.attr.label_to_requirement.items():
        if PyInfo in dep:
            modules[dep.label] = module

            for file in dep.files.to_list():
                dependency_files[file] = module

            # part of the dependency_files map requires discovering associated .so files
            # unfortunately, we have to do the following:
            #  - iterate over actual runfiles, which contain both the dependency and its dependencies
            #  - limit to just .so files
            #  - further limit to just the files in the deps' workspace root
            for file in dep.default_runfiles.files.to_list():
                if file.extension == "so" and file.path.startswith(dep.label.workspace_root + "/"):
                    dependency_files[file] = module

    args = ctx.actions.args()
    args.use_param_file("--args-file=%s", use_always = True)
    args.set_param_file_format("multiline")
    args.add("index")
    args.add_all(modules.items(), before_each = "--module", map_each = _map_module)
    args.add_all(dependency_files.items(), before_each = "--src-file", map_each = _map_dependency_file)
    args.add("--output", output_file)
    ctx.actions.run(
        outputs = [output_file],
        inputs = [],
        arguments = [args],
        executable = ctx.executable._exec,
    )

    return [
        DefaultInfo(
            files = depset(direct = [output_file]),
            runfiles = ctx.runfiles(files = [output_file]),
        ),
    ]

_deps_index = rule(
    implementation = _deps_index_impl,
    attrs = {
        "label_to_requirement": attr.label_keyed_string_dict(mandatory = True),
        "_exec": attr.label(
            default = "//pydeps/private/index",
            executable = True,
            cfg = "exec",
        ),
    },
)

def deps_index(name, pins, requirement, all_requirements):
    label_to_requirement = {
        Label(requirement(req)): req
        for req in pins
        if requirement(req) in all_requirements  # guard a pin appearing before locking
    }
    _deps_index(
        name = name,
        label_to_requirement = label_to_requirement,
        visibility = ["//visibility:public"],
    )
