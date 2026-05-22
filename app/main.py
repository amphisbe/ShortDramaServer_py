import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.video import router as video_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.database import close_database, initialize_runtime

import uvicorn

settings = get_settings()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 在 lifespan 入口初始化日志，确保应用启动时日志系统就绪
    setup_logging(settings.log_level)
    logger.info("启动 ShortDrama 服务，监听 %s:%d", settings.app_host, settings.app_port)

    # Demo 启动时自动建表；真实生产环境建议改为显式迁移脚本。
    initialize_runtime(create_schema=True, seed=False)
    try:
        yield
    finally:
        close_database()



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


# ---------------------------------------------------------------------------
# 启动函数（供 run.py 和 python -m app.main 复用）
# ---------------------------------------------------------------------------
def start() -> None:
    """从 settings（.env 文件或环境变量）读取 host/port 并启动 uvicorn。"""
    logger.info(
        "启动 ShortDrama 服务，监听 %s:%d（来源：.env / 环境变量）",
        settings.app_host,
        settings.app_port,
    )
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )


# ---------------------------------------------------------------------------
# 直接运行入口：python -m app.main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    start()