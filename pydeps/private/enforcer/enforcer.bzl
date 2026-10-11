"Implement a deps/bazel consistency checking aspect."

load("@rules_python//python:py_info.bzl", "PyInfo")

_EMPTY_DEPSET = depset()

def is_depset_empty(a_depset):
    "Returns true if the provided depset is empty."
    return a_depset == _EMPTY_DEPSET

def is_external(label):
    """Returns true if the label corresponds to an external dependency."""
    return label.workspace_root.startswith("external/")

def is_eligible(ctx, target, disable_tags):
    """
    Returns true if this aspect is eligible to run on this target.

    Args:
        ctx: aspect context
        target: bazel target
        disable_tags: a list of tags that disable this aspect

    Returns:
    true iff this aspect is eligible to run.
    """
    disable_tags = disable_tags or []

    if ctx.rule.kind not in ["py_binary", "py_library", "py_test"]:
        return False

    if is_external(target.label):
        return False

    for tag in disable_tags:
        if tag in ctx.rule.attr.tags:
            return False

    return True

def _rewrite_filepath(file):
    """
    Returns a Python-path localized version of file.

    Normalizes:
    - external dependency files from `external/prod_<name>/site-packages/<file>` to `<file>`
    - generated code files from `bazel-out/.../bin/<file>` to `<file>`
    """
    filepath = file.path
    if filepath.startswith("external/"):
        # external paths are of the form:
        #   external/prod_<pkg>/site-packages/<src>
        # so we extract just the src portion
        return filepath[filepath.find("/site-packages/") + 15:]
    elif filepath.startswith("bazel-out/"):
        # generated sources are of the form:
        #   bazel-out/darwin-fastbuild/bin/proto/generic_clip_api_log_record_pb2.pyi
        # so we extract just the src portion
        return filepath[filepath.find("/bin/") + 5:]
    else:
        return filepath

def _deps_aspect_impl(target, ctx):
    """
    Invoke the `ctx.executable._deps` target on py_binary, py_library and py_test.

    This aspect implementation constructs maps the source file inputs to command arguments
    to `deps_cli`, maps the Bazel-required output file, and passes the tags attached
    to the target the aspect is run against.

    Additionally, this implementation will skip all targets tagged with "no-lint" or "no-deps"

    The executable is passed the following arguments:
        --target <target>                 : the fully qualified bazel path of the target being evaluated
        --source <src file>               : repeated for each source file
        --dependency <dependency>         : repeated for each declared dependency
        --runtime-dependency <dependency> : repeated for each not_imported_dep entry
        --dep-file <dependency>=<file>    : repeated for each <file> in <dependency>
        --output-file <output>            : the bazel required output for an aspect
        --tag                             : repeated for each tag on the target
    """
    if not is_eligible(ctx, target, ctx.attr._suppression_tags):
        return []

    source_files = depset(transitive = [src.files for src in ctx.rule.attr.srcs])

    if is_depset_empty(source_files):
        return []

    referenced_deps = []
    dependency_files = []

    for dep in ctx.rule.attr.deps:
        if dep.label.name in ctx.attr._ignored_names:
            continue

        if PyInfo in dep:
            dep_str = str(dep.label)
            referenced_deps.append(dep_str)

            if not is_external(dep.label):
                for file in dep.files.to_list():
                    dependency_files.append((dep_str, _rewrite_filepath(file)))

    runtime_deps = []
    tags = []

    for tag in ctx.rule.attr.tags:
        if tag.startswith("runtime:"):
            runtime_deps.append(tag.replace("runtime:", ""))
        else:
            tags.append(tag)

    output_file = ctx.actions.declare_file("{name}.deps".format(name = target.label.name))
    args = ctx.actions.args()
    args.use_param_file("--args-file=%s")
    args.set_param_file_format("multiline")
    args.add("aspect")
    args.add("-g", str(target.label))
    args.add("-k", ctx.rule.kind)
    args.add_all(ctx.files._index, before_each = "-i")
    args.add_all(source_files, before_each = "-s")
    args.add_all(referenced_deps, before_each = "-d")
    args.add_all(runtime_deps, before_each = "-r")

    # used to teach the dependency checker about the content of dependencies
    for (dep, dep_file) in dependency_files:
        args.add("-f", dep.removeprefix("@@") + "=" + dep_file)

    args.add("-o", output_file)
    args.add_all(tags, before_each = "-t")

    ctx.actions.run(
        outputs = [output_file],
        inputs = depset(direct = ctx.files._index, transitive = [source_files]),
        executable = ctx.executable._deps,
        arguments = [args],
        mnemonic = "CheckDeps",
    )

    output_depset = depset(direct = [output_file])

    output_group_info_dict = {"pydeps": output_depset}
    for custom_output_name in ctx.attr._output_groups:
        output_group_info_dict[custom_output_name] = output_depset

    return [OutputGroupInfo(**output_group_info_dict)]

def deps_enforcer_aspect_factory(
        pip_deps_index,
        suppression_tags = None,
        output_groups = None,
        ignored_target_names = None):
    return aspect(
        implementation = _deps_aspect_impl,
        attr_aspects = ["deps"],
        attrs = dict(
            _deps = attr.label(cfg = "exec", default = "//pydeps/private/enforcer:deps_cli", executable = True),
            _index = attr.label(default = pip_deps_index),
            _output_groups = attr.string_list(default = output_groups or []),
            _suppression_tags = attr.string_list(default = suppression_tags or ["no-deps-enforcer"]),
            _ignored_names = attr.string_list(default = ignored_target_names or []),
        ),
    )
