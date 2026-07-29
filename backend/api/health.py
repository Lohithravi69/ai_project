from fastapi import APIRouter

from backend.config import get_settings
from backend.database.session import engine
from backend.services.runtime_guard import RuntimeGuard

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, object]:
    settings = get_settings()
    guard = RuntimeGuard(settings)
    dependencies = await guard.snapshot(engine)
    overall = "ok" if all(dep.status == "ok" for dep in dependencies) else "degraded"
    return {"status": overall, "dependencies": RuntimeGuard.as_dicts(dependencies)}
