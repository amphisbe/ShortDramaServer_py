"""用户个人中心 REST API。"""

from typing import Any

from fastapi import APIRouter, Body, Depends, Query

from app.core.security import require_path_user
from app.db.dependencies import with_db_connection
from app.services import user_service

# 所有 /user/{user_id}/* 接口均需 Bearer JWT，且路径 user_id 必须等于令牌用户
router = APIRouter(
    prefix="/api/v1",
    tags=["user"],
    dependencies=[Depends(require_path_user)],
)


@router.get("/user/{user_id}/profile", summary="用户信息")
@with_db_connection
def user_profile(user_id: str) -> dict[str, Any]:
    profile = user_service.get_user_profile(user_id)
    if profile is None:
        return {"code": 404, "message": "用户不存在", "data": None}
    return {"code": 0, "message": "success", "data": profile}


@router.get("/user/{user_id}/favorites", summary="用户收藏")
@with_db_connection
def user_favorites(
    user_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
) -> dict[str, Any]:
    result = user_service.get_user_favorites(user_id, page=page, page_size=page_size)
    return {"code": 0, "message": "success", "data": result}


@router.get("/user/{user_id}/history", summary="观看历史")
@with_db_connection
def user_history(
    user_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
) -> dict[str, Any]:
    result = user_service.get_user_history(user_id, page=page, page_size=page_size)
    return {"code": 0, "message": "success", "data": result}


# ============ 观看进度 ============


@router.post("/user/{user_id}/progress", summary="保存观看进度")
@with_db_connection
def save_progress(
    user_id: str,
    video_id: str = Body(...),
    position: int = Body(default=0),
    is_finished: bool = Body(default=False),
) -> dict[str, Any]:
    # print(f"save_progress: user_id={user_id}, video_id={video_id}, position={position}, is_finished={is_finished}")
    ok = user_service.save_progress(user_id, video_id, position, is_finished)
    return {"code": 0 if ok else 404, "message": "ok" if ok else "用户或剧集不存在"}


@router.get("/user/{user_id}/progress/{drama_id}", summary="查询观看进度")
@with_db_connection
def get_progress(user_id: str, drama_id: str) -> dict[str, Any]:
    result = user_service.get_progress(user_id, drama_id)
    return {"code": 0, "message": "success", "data": result}


# ============ 点赞 ============


@router.post("/user/{user_id}/like", summary="点赞/取消点赞")
@with_db_connection
def toggle_like(
    user_id: str,
    video_id: int = Body(...),
    is_like: bool | None = Body(default=None, description="目标状态；不传则 toggle"),
) -> dict[str, Any]:
    result = user_service.toggle_like(user_id, video_id, is_like)
    return {"code": 0, "message": "success", "data": result}


@router.get("/user/{user_id}/likes/{video_id}", summary="查询点赞状态")
@with_db_connection
def check_liked(user_id: str, video_id: str) -> dict[str, Any]:
    result = user_service.check_liked(user_id, video_id)
    return {"code": 0, "message": "success", "data": result}


# ============ 收藏 ============


@router.post("/user/{user_id}/favorite", summary="收藏/取消收藏短剧")
@with_db_connection
def toggle_favorite(
    user_id: str,
    video_id: int = Body(...),
    is_favorite: bool | None = Body(default=None, description="目标状态；不传则 toggle"),
) -> dict[str, Any]:
    """收藏或取消收藏短剧（传 is_favorite 时幂等设置，否则 toggle），返回最新状态和追剧数。"""
    result = user_service.toggle_favorite(user_id, video_id, is_favorite)
    return {"code": 0, "message": "success", "data": result}


# ============ 分享 ============


@router.post("/user/{user_id}/share", summary="记录分享")
@with_db_connection
def share_episode(
    user_id: str,
    video_id: int = Body(...),
    channel: str = Body(default="unknown"),
) -> dict[str, Any]:
    """记录一次剧集分享事件，返回分享状态和最新分享数。"""
    result = user_service.record_share(user_id, video_id, channel)
    if not result.get("shared"):
        return {"code": 404, "message": "剧集不存在", "data": None}
    return {"code": 0, "message": "success", "data": result}
