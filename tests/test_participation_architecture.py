"""Keep the business service independent from web and persistence frameworks."""

from __future__ import annotations

import ast
from pathlib import Path


def test_participation_service_has_no_web_or_db_imports() -> None:
    path = Path("app/features/sessions/participation_service.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden = ("fastapi", "starlette", "sqlalchemy", "sqlite3", "pydantic", "app.db")
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert not [name for name in imported if name.startswith(forbidden)]
