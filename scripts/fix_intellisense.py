"""
Post-build script: remove non-existent include paths from .vscode/c_cpp_properties.json.

PlatformIO faithfully copies every -I flag the compiler receives, including paths
declared in framework CMakeLists files that were never created on disk. This script
runs after every build and silently drops those phantom entries so VS Code stops
reporting "Cannot find" warnings.
"""

import json
import os
import re

Import("env")  # type: ignore[name-defined]  # noqa: F821 — SCons global, injected by PlatformIO


def fix_intellisense(source, target, env):  # noqa: ARG001
    props_path = os.path.join(
        env.subst("$PROJECT_DIR"), ".vscode", "c_cpp_properties.json"
    )

    if not os.path.isfile(props_path):
        return

    with open(props_path, "r", encoding="utf-8") as f:
        raw = f.read()

    # Strip single-line // comments so json.loads() accepts the file
    stripped = re.sub(r"//[^\n]*", "", raw)

    try:
        data = json.loads(stripped)
    except json.JSONDecodeError as exc:
        print(f"fix_intellisense: could not parse {props_path}: {exc}")
        return

    changed = False

    for cfg in data.get("configurations", []):
        for key in ("includePath", "path"):  # path lives inside browse{}
            if key == "path":
                container = cfg.get("browse", {})
            else:
                container = cfg

            paths = container.get(key, [])
            filtered = [
                p
                for p in paths
                if p.startswith("${") or not p or os.path.isdir(p)
            ]
            if len(filtered) != len(paths):
                removed = set(paths) - set(filtered)
                for r in sorted(removed):
                    print(f"fix_intellisense: removed missing path: {r}")
                container[key] = filtered
                changed = True

    if changed:
        # Preserve the leading warning comment PlatformIO writes at the top
        header_match = re.match(r"((?://[^\n]*\n)+)", raw)
        header = header_match.group(1) if header_match else ""
        with open(props_path, "w", encoding="utf-8") as f:
            f.write(header)
            json.dump(data, f, indent=4)
            f.write("\n")
        print("fix_intellisense: c_cpp_properties.json updated")


env.AddPostAction("$BUILD_DIR/${PROGNAME}.elf", fix_intellisense)  # type: ignore[name-defined]
