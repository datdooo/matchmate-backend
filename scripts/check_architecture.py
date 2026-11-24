"""Check business layers, private imports and cycles between feature modules."""

import ast
from pathlib import Path

FRAMEWORKS = {"fastapi", "starlette", "pydantic", "sqlalchemy", "sqlite3"}


def imports(tree, module, is_package):
    package = module.split(".") if is_package else module.split(".")[:-1]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            prefix = package[: len(package) - node.level + 1] if node.level else []
            base = ".".join([*prefix, *node.module.split(".")]) if node.module else ".".join(prefix)
            if not (base.startswith("app.features.") and len(base.split(".")) == 3):
                yield base
            for alias in node.names:
                yield f"{base}.{alias.name}"


def feature(module):
    parts = module.split(".")
    return parts[2] if len(parts) >= 3 and parts[:2] == ["app", "features"] else None


def violations(root: Path) -> list[str]:
    errors = []
    graph: dict[str, set[str]] = {}
    for path in sorted((root / "app").rglob("*.py")):
        module = ".".join(path.relative_to(root).with_suffix("").parts)
        is_package = path.name == "__init__.py"
        if is_package:
            module = module.removesuffix(".__init__")
        owner = feature(module)
        if owner:
            graph.setdefault(owner, set())
        business = (
            module.startswith("app.domain.")
            or path.name.endswith(("service.py", "contracts.py", "strategy.py"))
            or (owner is not None and any(p in ("domain", "application") for p in path.parts))
        )
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for target in set(imports(tree, module, is_package)):
            if business and (
                target.split(".")[0] in FRAMEWORKS or target.startswith(("app.db", "app.api"))
            ):
                errors.append(f"{path.relative_to(root)}: business layer imports {target}")
            other = feature(target)
            if other is None:
                continue
            tail = target.split(".")[3:]
            if owner and other != owner:
                graph[owner].add(other)
                if not tail or tail[0] not in {"contracts", "schemas"}:
                    errors.append(
                        f"{path.relative_to(root)}: imports private adapter/module {target}"
                    )
            if (
                business
                and tail
                and (
                    tail[0] in {"infrastructure", "schemas", "router", "routers", "dependencies"}
                    or tail[0].endswith(
                        ("repository", "router", "dependencies", "schemas", "reader", "writer")
                    )
                )
            ):
                errors.append(
                    f"{path.relative_to(root)}: business layer imports implementation {target}"
                )

    visited = set()
    active = []

    def visit(name):
        if name in active:
            errors.append(
                "Feature dependency cycle: " + " -> ".join(active[active.index(name) :] + [name])
            )
            return
        if name in visited:
            return
        active.append(name)
        for dependency in sorted(graph.get(name, ())):
            visit(dependency)
        active.pop()
        visited.add(name)

    for name in sorted(graph):
        visit(name)
    return sorted(set(errors))


if __name__ == "__main__":
    findings = violations(Path.cwd())
    print("\n".join(findings) if findings else "Architecture boundaries and feature graph passed.")
    raise SystemExit(bool(findings))
