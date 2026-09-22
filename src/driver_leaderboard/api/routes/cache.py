from fastapi import APIRouter

from driver_leaderboard.services.cache_service import cache_metrics

router = APIRouter(prefix="/admin/cache", tags=["admin"])


@router.get("/metrics")
def read_cache_metrics() -> dict[str, float | int | bool]:
    return cache_metrics()
