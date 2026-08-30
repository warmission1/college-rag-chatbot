import time
from fastapi import APIRouter, Depends
from pymongo.database import Database
from backend.app.core.database import get_db
from backend.app.core.config import settings

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check(db: Database = Depends(get_db)):
    db_status = "healthy"
    try:
        db.command("ping")
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    return {
        "status": "ok" if db_status == "healthy" else "degraded",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "database_type": settings.DATABASE_TYPE,
        "database": db_status,
        "llm_provider": settings.LLM_PROVIDER,
        "embedding_provider": settings.EMBEDDING_PROVIDER,
        "timestamp": time.time(),
    }
