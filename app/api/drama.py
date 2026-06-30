"""短剧首页/详情页 REST API。"""

from typing import Any

from fastapi import APIRouter, Query

from app.services import drama_service

router = APIRouter(prefix="/api/v1/dramas", tags=["drama"])


# ============ 首页接口 ============


@router.get("", summary="短剧列表（首页）")
def drama_list(
    category: str = Query(default="推荐", description="分类筛选"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=60),
) -> dict[str, Any]:
    """获取短剧列表，支持分类过滤和分页。"""
    result = drama_service.list_dramas(category=category, page=page, page_size=page_size)
    print(f"drama_list: category={category}, page={page}, page_size={page_size}, total={result['total']}")
    print(f"  first item: {result['data'][0] if result['data'] else 'no data'}")
    return {"code": 0, "message": "success", "data": result}


@router.get("/featured", summary="主推短剧")
def featured_drama() -> dict[str, Any]:
    """获取首页主推短剧。"""
    item = drama_service.get_featured_drama()
    return {
        "code": 0,
        "message": "success",
        "data": item,
    }


@router.get("/hot", summary="热门短剧")
def hot_dramas(
    category: str = Query(default="推荐", description="分类筛选"),
    count: int = Query(default=4, ge=1, le=20),
) -> dict[str, Any]:
    """获取热门短剧（按播放量排行）。"""
    items = drama_service.get_hot_dramas(category=category, count=count)
    return {"code": 0, "message": "success", "data": items}


@router.get("/trending", summary="热搜短剧")
def trending_dramas(
    category: str = Query(default="推荐", description="分类筛选"),
    count: int = Query(default=5, ge=1, le=20),
) -> dict[str, Any]:
    """获取热搜短剧（按追剧数排行）。"""
    items = drama_service.get_trending_dramas(category=category, count=count)
    return {"code": 0, "message": "success", "data": items}


@router.get("/recommended", summary="猜你喜欢")
def recommended_dramas(
    exclude_id: str = Query(default="", description="排除的短剧 ID"),
    category: str = Query(default="推荐", description="分类筛选"),
    count: int = Query(default=4, ge=1, le=20),
) -> dict[str, Any]:
    """猜你喜欢 - 随机推荐。"""
    items = drama_service.get_recommended_dramas(
        exclude_drama_id=exclude_id, category=category, count=count
    )
    return {"code": 0, "message": "success", "data": items}


# ============ 详情页接口 ============


@router.get("/{drama_id}", summary="短剧详情")
def drama_detail(drama_id: str) -> dict[str, Any]:
    """根据 external_drama_id 获取短剧详情。"""
    item = drama_service.get_drama_by_id(drama_id)
    if item is None:
        return {"code": 404, "message": "短剧未找到", "data": None}
    return {"code": 0, "message": "success", "data": item}


@router.get("/{drama_id}/related", summary="同类推荐")
def related_dramas(
    drama_id: str,
    category: str = Query(default="", description="分类"),
    count: int = Query(default=4, ge=1, le=20),
) -> dict[str, Any]:
    """获取同类短剧推荐。"""
    items = drama_service.get_related_dramas(
        drama_id=drama_id, category=category, count=count
    )
    return {"code": 0, "message": "success", "data": items}


@router.get("/{drama_id}/episodes", summary="剧集列表")
def drama_episodes(
    drama_id: str,
    viewer_user_id: str | None = Query(default=None, description="当前用户 ID"),
) -> dict[str, Any]:
    """获取短剧的全部剧集（播放页数据）。"""
    result = drama_service.get_drama_episodes(
        drama_id=drama_id, viewer_external_user_id=viewer_user_id
    )
    if not result["found"]:
        return {"code": 404, "message": "短剧或剧集未找到", "data": None}
    return {
        "code": 0,
        "message": "success",
        "data": {
            "list": result["data"],
            "totalEpisodes": result["totalEpisodes"],
        },
    }


# ============ 辅助接口 ============


@router.get("/by-user/{user_id}", summary="通过 userId 查询短剧 ID")
def find_drama_by_user(user_id: str) -> dict[str, Any]:
    """通过剧集作者的 userId 反查短剧 external_drama_id。"""
    drama_id = drama_service.find_drama_id_by_episode_user_id(user_id)
    if not drama_id:
        return {"code": 404, "message": "未找到对应短剧", "data": None}
    return {"code": 0, "message": "success", "data": {"dramaId": drama_id}}
