from fastapi import FastAPI

from driver_leaderboard.api.routes.admin import router as admin_router
from driver_leaderboard.api.routes.cache import router as cache_router
from driver_leaderboard.api.routes.expirations import router as expirations_router
from driver_leaderboard.api.routes.health import router as health_router
from driver_leaderboard.api.routes.leaderboards import router as leaderboards_router
from driver_leaderboard.api.routes.moderation import router as moderation_router
from driver_leaderboard.api.routes.outbox import router as outbox_router
from driver_leaderboard.api.routes.reviews import router as reviews_router
from driver_leaderboard.api.routes.scores import router as scores_router
from driver_leaderboard.observability import configure_observability

app = FastAPI(title="Driver Review Leaderboard", version="0.1.0")
configure_observability(app)
app.include_router(admin_router)
app.include_router(cache_router)
app.include_router(expirations_router)
app.include_router(health_router)
app.include_router(leaderboards_router)
app.include_router(moderation_router)
app.include_router(outbox_router)
app.include_router(reviews_router)
app.include_router(scores_router)
