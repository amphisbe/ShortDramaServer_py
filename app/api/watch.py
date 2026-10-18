"""真实观看时长统计接口（docs/watch-time-statistics-design.md 5）。

用户只取自 JWT（get_current_user），不接受路径/Body 用户 ID；错误沿用 HTTP 200 + 信封业务码：
400 参数错误、401 未登录、403 会话签名/归属不符、404 分集不存在、410 会话过期、429 限流。
"""

from typing import Any

from fastapi import APIRouter, Body, Depends
from pydantic import ValidationError

from app.core.security import get_current_user
from app.db.dependencies import with_db_connection
from app.schemas.watch import WatchEventIn, WatchSessionIn
from app.services import watch_service

router = APIRouter(prefix="/api/v1/me", tags=["watch"], dependencies=[])


def _error(code: int, message: str) -> dict[str, Any]:
    return {"code": code, "message": message, "data": None}


@router.post("/watch-sessions", summary="创建观看会话")
@with_db_connection
def create_watch_session(
    payload: Any = Body(default=None),
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        body = WatchSessionIn.model_validate(payload if isinstance(payload, dict) else {})
    except ValidationError:
        return _error(400, "参数错误")
    try:
        data = watch_service.create_session(user_id, body.video_id)
    except watch_service.WatchError as exc:
        return _error(exc.code, exc.message)
    return {"code": 0, "message": "success", "data": data}


@router.post("/watch-events", summary="上报观看进度（累计值）")
@with_db_connection
def report_watch_event(
    payload: Any = Body(default=None),
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        event = WatchEventIn.model_validate(payload if isinstance(payload, dict) else {})
    except ValidationError:
        return _error(400, "参数错误")
    try:
        data = watch_service.report_event(user_id, event)
    except watch_service.WatchError as exc:
        return _error(exc.code, exc.message)
    return {"code": 0, "message": "success", "data": data}