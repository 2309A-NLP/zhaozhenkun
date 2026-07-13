import os

from fastapi import APIRouter
from fastapi.responses import FileResponse

from config import get_settings

router = APIRouter()


@router.get("/", include_in_schema=False)
async def ui_index():
    settings = get_settings()
    return FileResponse(os.path.join(settings.BASE_STATIC_DIR, "app", "index.html"))
