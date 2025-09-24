from fastapi import APIRouter
import datetime

router = APIRouter()

@router.get("/health")
async def health():
    return {"status": "ok", "time": datetime.datetime.utcnow().isoformat()}
