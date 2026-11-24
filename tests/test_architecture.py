from pathlib import Path

import pytest

from scripts.check_architecture import violations


def test_application_respects_architecture():
    assert violations(Path.cwd()) == []


@pytest.mark.parametrize(
    ("files", "expected"),
    [
        ({"app/features/a/service.py": "import sqlalchemy"}, "business layer imports"),
        ({"app/features/a/service.py": "from app.api.schemas import Reply"}, "business layer"),
        ({"app/features/a/domain/strategy.py": "from fastapi import Request"}, "business layer"),
        ({"app/features/a/strategy.py": "from sqlalchemy import select"}, "business layer"),
        (
            {"app/features/a/service.py": "from .venue_reader import Reader"},
            "imports implementation",
        ),
        (
            {"app/features/a/service.py": "from .matching_request_writer import Writer"},
            "imports implementation",
        ),
        (
            {"app/features/a/service.py": "from .routers.sessions import create_sessions_router"},
            "imports implementation",
        ),
        (
            {"app/features/a/service.py": "from .infrastructure.repo import Repository"},
            "imports implementation",
        ),
        (
            {"app/features/a/repository.py": "from app.features.b.repository import Repository"},
            "private adapter",
        ),
        (
            {"app/features/a/repository.py": "from ..b.infrastructure.repo import Repository"},
            "private adapter",
        ),
        (
            {
                "app/features/a/contracts.py": "from ..b.contracts import Item",
                "app/features/b/contracts.py": "from ..a.contracts import Item",
            },
            "dependency cycle",
        ),
    ],
    ids=[
        "sql-in-service",
        "http-schema",
        "http-in-domain",
        "sql-in-flat-strategy",
        "own-flat-reader",
        "own-flat-writer",
        "own-routers-package",
        "own-adapter",
        "cross-adapter",
        "relative",
        "cycle",
    ],
)
def test_checker_detects_forbidden_imports_and_cycles(tmp_path, files, expected):
    for name, content in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    assert any(expected in finding for finding in violations(tmp_path))


def test_checker_accepts_composition_and_public_read_contracts(tmp_path):
    files = {
        "app/composition.py": "from app.features.b.infrastructure.repo import Repository",
        "app/features/a/service.py": "from ..b.contracts import Reader",
        "app/features/a/router.py": "from ..b import schemas",
        "app/features/b/contracts.py": "from typing import Protocol",
        "app/features/a/infrastructure/read.py": "from app.db.models import VenueModel",
    }
    for name, content in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    assert violations(tmp_path) == []
