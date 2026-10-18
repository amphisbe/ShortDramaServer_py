import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.auth import router as auth_router
from app.api.video import router as video_router
from app.api.drama import router as drama_router
from app.api.user import router as user_router
from app.api.tags import router as tags_router
from app.api.for_you import router as for_you_router
from app.api.watch import router as watch_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.security import ApiAuthError
from app.db.database import close_database, initialize_runtime

import uvicorn

settings = get_settings()

logger = logging.getLogger(__name__)


def _cleanup_stale_watch_sessions() -> None:
    """启动时删除 30 天未活动的观看会话（docs/watch-time-statistics-design.md 6.3），失败不影响启动。"""
    from app.db.database import initialize_database
    from app.services.watch_service import cleanup_stale_sessions

    try:
        db = initialize_database()
        with db.connection_context():
            removed = cleanup_stale_sessions()
        if removed:
            logger.info("已清理过期观看会话 %d 条", removed)
    except Exception as exc:
        logger.warning("清理过期观看会话失败：%s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 在 lifespan 入口初始化日志，确保应用启动时日志系统就绪
    setup_logging(settings.log_level)
    logger.info("启动 ShortDrama 服务，监听 %s:%d", settings.app_host, settings.app_port)

    # Demo 启动时自动建表；真实生产环境建议改为显式迁移脚本。
    initialize_runtime(create_schema=True, seed=False)
    _cleanup_stale_watch_sessions()
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


@app.exception_handler(ApiAuthError)
async def api_auth_error_handler(request: Request, exc: ApiAuthError) -> JSONResponse:
    # 保持项目统一信封：HTTP 200 + code（401 未登录/令牌无效，403 无权限）
    return JSONResponse(
        status_code=200,
        content={"code": exc.code, "message": exc.message, "data": None},
    )


app.include_router(video_router)
app.include_router(drama_router)
app.include_router(user_router)
app.include_router(auth_router)
app.include_router(tags_router)
app.include_router(for_you_router)
app.include_router(watch_router)


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
