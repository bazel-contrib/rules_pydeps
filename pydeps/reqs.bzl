"Module extension to read requirements.txt and produce a repository that contains Starlark variables with requirements."

load("//pydeps/private/index:reqs.bzl", "requirements_txt")

requirements = tag_class(
    attrs = {
        "requirements_txt": attr.label(mandatory = True, allow_single_file = True),
        "pip_requirements": attr.label(mandatory = True),
    },
)

def _extension(module_ctx):
    files = []
    pip_reqs = {}
    for mod in module_ctx.modules:
        for tag in mod.tags.requirements:
            files.append(tag.requirements_txt)
            pip_reqs[tag.pip_requirements] = 1

    if len(pip_reqs) > 1:
        fail("pydeps requires all `pip_requirements` values to be the same.")

    requirements_txt(
        name = "reqs",
        files = files,
        pip_requirements = pip_reqs.keys()[0],
    )

    return module_ctx.extension_metadata(
        root_module_direct_deps = ["reqs"],
        root_module_direct_dev_deps = [],
        reproducible = True,  # repo state is only a function of the input files
    )

reqs = module_extension(
    implementation = _extension,
    tag_classes = {
        "requirements": requirements,
    },
)
