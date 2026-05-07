from typing import Any

from fastapi import APIRouter, Query

from app.services.play_service import list_dramas, list_play_items

router = APIRouter(prefix="/api/v1", tags=["video"])


@router.get("/video/play-list/raw", summary="播放列表原始兼容格式")
def play_list_raw(
    viewer_user_id: str | None = Query(default=None, description="当前登录用户的 external_user_id，用于计算点赞、关注和播放进度"),
    drama_id: int | None = Query(default=None, description="短剧内部 ID，可选"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> list[dict[str, Any]]:
    """返回与用户上传 data.json 兼容的顶层数组结构。"""

    items, _ = list_play_items(
        viewer_external_user_id=viewer_user_id,
        drama_id=drama_id,
        page=page,
        page_size=page_size,
    )
    return items


@router.get("/video/play-list", summary="播放列表统一响应格式")
def play_list(
    viewer_user_id: str | None = Query(default=None, description="当前登录用户的 external_user_id，用于计算点赞、关注和播放进度"),
    drama_id: int | None = Query(default=None, description="短剧内部 ID，可选"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    """返回推荐的 code/message/data 包装格式。"""

    items, has_more = list_play_items(
        viewer_external_user_id=viewer_user_id,
        drama_id=drama_id,
        page=page,
        page_size=page_size,
    )
    return {
        "code": 0,
        "message": "success",
        "data": {
            "list": items,
            "page": page,
            "pageSize": page_size,
            "hasMore": has_more,
        },
    }


@router.get("/admin/dramas", summary="Demo 短剧管理列表")
def admin_dramas() -> dict[str, Any]:
    """Demo 管理接口：列出短剧主数据。

    真实项目应补充管理员登录、RBAC 权限、审计日志和分页筛选；当前接口用于验证数据模型。
    """

    return {"code": 0, "message": "success", "data": {"list": list_dramas()}}
