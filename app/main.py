from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.video import router as video_router
from app.core.config import get_settings
from app.db.database import close_database, initialize_runtime


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Demo 启动时自动建表；真实生产环境建议改为显式迁移脚本。
    initialize_runtime(create_schema=True, seed=False)
    try:
        yield
    finally:
        close_database()


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    debug=settings.app_debug,
    version="0.1.0",
    description="基于 FastAPI + Peewee 的短剧服务端 Demo，播放接口兼容既定 data.json 字段标准。",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(video_router)


@app.get("/health", tags=["system"], summary="健康检查")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}
