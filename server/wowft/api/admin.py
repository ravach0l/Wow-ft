from fastapi import APIRouter

from ..auth import AdminUser, DbSession
from ..features import FEATURES, get_features, set_features

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/features")
def list_features(_: AdminUser, session: DbSession):
    current = get_features(session)
    return [{"key": k, "label": label, "enabled": current[k]} for k, (_, label) in FEATURES.items()]


@router.patch("/features")
def update_features(body: dict[str, bool], _: AdminUser, session: DbSession):
    set_features(session, body)
    return list_features(_, session)
