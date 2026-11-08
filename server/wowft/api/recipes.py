"""Rezepte („Wer kann was?“) mit Abgleich gegen die Materialien der Gruppe."""

from __future__ import annotations

from fastapi import APIRouter

from .. import privacy
from ..auth import CurrentUser, DbSession
from .groups import _membership, _visible_characters, group_materials

router = APIRouter(prefix="/api", tags=["recipes"])

MAX_RESULTS = 40


def _norm(s: str | None) -> str:
    return " ".join((s or "").lower().split())


@router.get("/groups/{group_id}/recipes")
def search_recipes(group_id: int, user: CurrentUser, session: DbSession, q: str = ""):
    """Rezepte der Gruppe, die zur Suche passen: wer kann es herstellen, wer hat die Reagenzien.

    Berufe (und damit Rezepte) sind Teil der Freigabe „Berufe“, die Bestände Teil von
    „Handwerksmaterialien“.
    """
    _membership(session, group_id, user)
    needle = _norm(q)
    recipes: dict[str, dict] = {}
    known = 0
    for c in _visible_characters(session, group_id):
        if "skills" in privacy.hidden_for(c, user.id):
            continue
        for prof in (c.state or {}).get("recipes") or []:
            for r in prof.get("list") or []:
                known += 1
                name = r.get("name") or ""
                if len(needle) < 2 or needle not in _norm(name):
                    continue
                entry = recipes.setdefault(
                    _norm(name),
                    {
                        "name": name,
                        "item": r.get("item"),
                        "profession": prof.get("profession"),
                        "reagents": r.get("reagents") or [],
                        "crafters": [],
                    },
                )
                entry["crafters"].append(
                    {"characterId": c.id, "name": c.name, "class": c.class_, "ownerName": c.user.name}
                )

    materials = group_materials(session, group_id, user.id)
    by_id = {m["id"]: m for m in materials}
    by_name = {_norm(m["name"]): m for m in materials if m["name"]}
    results = []
    for entry in sorted(recipes.values(), key=lambda e: (_norm(e["name"]) != needle, e["name"]))[
        :MAX_RESULTS
    ]:
        reagents = []
        for rg in entry["reagents"]:
            m = by_id.get(rg.get("id")) or by_name.get(_norm(rg.get("name")))
            holders = [
                {
                    "characterId": h["characterId"],
                    "name": h["name"],
                    "class": h["class"],
                    "ownerName": h["ownerName"],
                    "count": h["bags"] + h["bank"],
                }
                for h in (m["holders"] if m else [])
            ]
            reagents.append(
                {
                    "id": rg.get("id"),
                    "name": rg.get("name") or (m["name"] if m else None),
                    "count": rg.get("count") or 1,
                    "total": sum(h["count"] for h in holders),
                    "holders": holders,
                }
            )
        results.append({**entry, "reagents": reagents})
    return {"known": known, "results": results}
