"""Module, die ein Admin für die ganze Seite ein- und ausschalten kann."""

from __future__ import annotations

from sqlalchemy.orm import Session

from .models import AppSetting

# Schlüssel -> (Standard, Bezeichnung)
FEATURES: dict[str, tuple[bool, str]] = {
    "race": (False, "Level-Rennen"),
}

_KEY = "features"


def get_features(session: Session) -> dict[str, bool]:
    row = session.get(AppSetting, _KEY)
    stored = row.value if row and isinstance(row.value, dict) else {}
    return {k: bool(stored.get(k, default)) for k, (default, _) in FEATURES.items()}


def set_features(session: Session, changes: dict[str, bool]) -> dict[str, bool]:
    current = get_features(session)
    current.update({k: bool(v) for k, v in changes.items() if k in FEATURES})
    row = session.get(AppSetting, _KEY)
    if row is None:
        session.add(AppSetting(key=_KEY, value=current))
    else:
        row.value = current
    session.commit()
    return current


def enabled(session: Session, key: str) -> bool:
    return get_features(session).get(key, False)
