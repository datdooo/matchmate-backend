"""Giữ Service/domain/contracts thuần Python theo đặc tả, không quét đồ thị phụ thuộc."""

import ast
from pathlib import Path


def test_business_modules_do_not_import_web_or_database():
    forbidden = {"fastapi", "starlette", "pydantic", "sqlalchemy", "sqlite3"}
    paths = [
        *Path("app/domain").glob("*.py"),
        *Path("app/features").rglob("*service.py"),
        *Path("app/features").rglob("*contracts.py"),
    ]
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text())):
            names = (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else []
            )
            for name in names:
                assert name.split(".")[0] not in forbidden, (str(path), name)
                assert not name.startswith("app.db"), (str(path), name)
