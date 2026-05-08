from fastapi import APIRouter, HTTPException, Query

from app.services.resolver import resolve_asset, resolve_asset_candidates

router = APIRouter()


@router.get("/resolve")
def resolve_asset_endpoint(
    query: str = Query(..., min_length=1),
    asset_type: str | None = Query(default=None),
):
    text = query.strip()
    if not text:
        raise HTTPException(status_code=400, detail="query is required")
    return resolve_asset(text, asset_type=asset_type)


@router.get("/search")
def search_assets_endpoint(
    query: str = Query(..., min_length=1),
    asset_type: str | None = Query(default=None),
):
    text = query.strip()
    if not text:
        raise HTTPException(status_code=400, detail="query is required")
    return resolve_asset_candidates(text, asset_type=asset_type)

