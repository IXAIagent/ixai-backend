from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_legacy_risk_engine_modules_are_removed():
    assert not (ROOT / "app/services/risk_engine.py").exists()
    assert not (ROOT / "app/services/risk_engine_v2.py").exists()


def test_live_backend_code_imports_canonical_risk_engine_only():
    offenders: list[str] = []

    for path in (ROOT / "app").rglob("*.py"):
        relative_path = path.relative_to(ROOT)
        if relative_path == Path("app/services/risk_engine_v3.py"):
            continue

        source = path.read_text(encoding="utf-8")
        legacy_imports = (
            "app.services.risk_engine import",
            "app.services.risk_engine_v2",
            "from app.services import risk_engine",
            "from app.services import risk_engine_v2",
            "import app.services.risk_engine",
            "import app.services.risk_engine_v2",
        )
        if any(pattern in source for pattern in legacy_imports):
            offenders.append(str(relative_path))

    assert offenders == []
