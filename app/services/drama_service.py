"""短剧数据服务层。

提供首页/详情页/播放页所需的统一数据查询接口。
后续接入真实搜索/推荐引擎时只需修改此文件中的查询逻辑。
"""

from __future__ import annotations

import random
import json
import math
from typing import Any

from peewee import DoesNotExist, fn

from app.models import (
    Drama,
    DramaEpisode,
    DramaEpisodeStat,
    User,
    UserEpisodeLike,
    UserFollow,
    UserEpisodeProgress,
)


from app.core.config import get_settings

settings = get_settings()

def _load_tags(tags_json: str) -> list[str]:
    if not tags_json:
        return []
    try:
        val = json.loads(tags_json)
        if isinstance(val, list):
            return val
    except (json.JSONDecodeError, TypeError):
        pass
    return []


def _build_drama_item(drama: Drama) -> dict[str, Any]:
    """将 Drama 模型组装为前端需要的 JSON 格式。"""
    static_base = settings.static_img.rstrip("/")
    cover = f"{static_base}/{drama.external_drama_id}.jpg"
    return {
        "dramaId": drama.external_drama_id or str(drama.id),
        "title": drama.title,
        # "cover": drama.cover_url,
        "cover": cover,
        "description": drama.description,
        "category": drama.category,
        "tags": _load_tags(drama.tags),
        "totalEpisodes": drama.total_episodes,
        "updatedEpisodes": drama.total_episodes,
        "playCount": _format_count(drama.play_count),
        "followCount": _format_count(drama.follow_count),
        "isFinished": drama.status == 2,
    }


def _format_count(count: int) -> str:
    """将数值格式化为 '12.3w' 形式。"""
    if count >= 10000:
        val = count / 10000
        return f"{val:.1f}w"
    return str(count)


# ============ 首页接口 ============


def list_dramas(
    category: str = "",
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """获取短剧列表（支持分类过滤）。"""
    query = Drama.select().where(Drama.status == 1)

    if category and category != "推荐":
        query = query.where(Drama.category == category)

    total = query.count()
    page = max(page, 1)
    page_size = min(max(page_size, 1), 50)
    rows = list(query.order_by(Drama.play_count.desc()).paginate(page, page_size))

    return {
        "data": [_build_drama_item(d) for d in rows],
        "hasMore": page * page_size < total,
        "page": page,
        "total": total,
    }


def get_featured_drama() -> dict[str, Any] | None:
    """获取主推短剧（播放量最高的或指定 ID）。"""
    try:
        drama = (
            Drama.select()
            .where(Drama.status == 1)
            .order_by(Drama.play_count.desc())
            .first()
        )
        if drama is None:
            return None
        return _build_drama_item(drama)
    except DoesNotExist:
        return None


def get_hot_dramas(category: str = "", count: int = 4) -> list[dict[str, Any]]:
    """获取热门短剧（按播放量排序）。"""
    query = Drama.select().where(Drama.status == 1)
    if category and category != "推荐":
        query = query.where(Drama.category == category)
    rows = list(query.order_by(Drama.play_count.desc()).limit(count))
    return [_build_drama_item(d) for d in rows]


def get_trending_dramas(
    category: str = "", count: int = 5
) -> list[dict[str, Any]]:
    """获取热搜短剧（按追剧数排序）。"""
    query = Drama.select().where(Drama.status == 1)
    if category and category != "推荐":
        query = query.where(Drama.category == category)
    rows = list(query.order_by(Drama.follow_count.desc()).limit(count))
    return [_build_drama_item(d) for d in rows]


def get_recommended_dramas(
    exclude_drama_id: str = "", category: str = "", count: int = 4
) -> list[dict[str, Any]]:
    """猜你喜欢（随机推荐）。"""
    query = Drama.select().where(Drama.status == 1)
    if exclude_drama_id:
        query = query.where(Drama.external_drama_id != exclude_drama_id)
    if category and category != "推荐":
        query = query.where(Drama.category == category)
    rows = list(query.order_by(fn.Random()).limit(count))
    return [_build_drama_item(d) for d in rows]


# ============ 详情页接口 ============


def get_drama_by_id(drama_id: str) -> dict[str, Any] | None:
    """根据 external_drama_id 获取短剧详情。"""
    try:
        drama = Drama.get(
            (Drama.external_drama_id == drama_id) & (Drama.status == 1)
        )
        return _build_drama_item(drama)
    except DoesNotExist:
        return None


def get_drama_by_internal_id(internal_id: int) -> dict[str, Any] | None:
    """根据内部 ID 获取短剧详情。"""
    try:
        drama = Drama.get((Drama.id == internal_id) & (Drama.status == 1))
        return _build_drama_item(drama)
    except DoesNotExist:
        return None


def get_related_dramas(
    drama_id: str, category: str = "", count: int = 4
) -> list[dict[str, Any]]:
    """获取同类短剧推荐。"""
    query = Drama.select().where(Drama.status == 1)
    if drama_id:
        query = query.where(Drama.external_drama_id != drama_id)
    if category:
        query = query.where(Drama.category == category)
    rows = list(query.order_by(Drama.play_count.desc()).limit(count))
    return [_build_drama_item(d) for d in rows]


# ============ 播放页接口 ============


def get_drama_episodes(
    drama_id: str,
    viewer_external_user_id: str | None = None,
) -> dict[str, Any]:
    """获取短剧的剧集列表（含播放项完整数据）。"""
    try:
        drama = Drama.get(
            (Drama.external_drama_id == drama_id) & (Drama.status == 1)
        )
    except DoesNotExist:
        return {"data": [], "found": False, "totalEpisodes": 0}

    episodes = list(
        DramaEpisode.select()
        .where(
            (DramaEpisode.drama == drama) & (DramaEpisode.status == 1)
        )
        .order_by(DramaEpisode.sort_order.asc(), DramaEpisode.episode_no.asc())
    )

    if not episodes:
        return {"data": [], "found": True, "totalEpisodes": drama.total_episodes}

    # 批量预取统计数据
    stat_map = _preload_stats(episodes)

    # 预取 viewer 状态
    liked_ids: set[int] = set()
    progress_map: dict[int, int] = {}
    author: User = drama.author_user
    is_follow = False
    if viewer_external_user_id:
        viewer = _get_viewer(viewer_external_user_id)
        if viewer is not None:
            liked_ids, is_follow, progress_map = _preload_viewer_state(
                viewer, episodes, author
            )

    result = []
    for ep in episodes:
        result.append(
            _build_episode_item(
                ep,
                drama,
                author,
                stat_map.get(ep.id),
                ep.id in liked_ids,
                is_follow,
                progress_map.get(ep.id, 0),
            )
        )

    return {"data": result, "found": True, "totalEpisodes": drama.total_episodes}


def find_drama_id_by_episode_user_id(user_id: str) -> str:
    """通过剧集中某一集的 userId 反查短剧 external_drama_id。"""
    try:
        user = User.get(User.external_user_id == user_id)
        drama = (
            Drama.select()
            .where((Drama.author_user == user) & (Drama.status == 1))
            .first()
        )
        if drama is not None:
            return drama.external_drama_id or str(drama.id)
    except DoesNotExist:
        pass
    return ""


# ============ 内部辅助 ============


def _get_viewer(external_user_id: str) -> User | None:
    try:
        return User.get(User.external_user_id == external_user_id)
    except DoesNotExist:
        return None


def _preload_stats(
    episodes: list[DramaEpisode],
) -> dict[int, DramaEpisodeStat]:
    episode_ids = [ep.id for ep in episodes]
    stats = DramaEpisodeStat.select().where(
        DramaEpisodeStat.episode.in_(episode_ids)
    )
    stat_map: dict[int, DramaEpisodeStat] = {s.episode_id: s for s in stats}
    for ep in episodes:
        if ep.id not in stat_map:
            stat_map[ep.id] = DramaEpisodeStat.create(episode=ep)
    return stat_map


def _preload_viewer_state(
    viewer: User,
    episodes: list[DramaEpisode],
    author: User,
) -> tuple[set[int], bool, dict[int, int]]:
    episode_ids = [ep.id for ep in episodes]

    is_follow = (
        UserFollow.select()
        .where(
            (UserFollow.follower_user == viewer)
            & (UserFollow.followed_user == author)
        )
        .exists()
    )

    liked_rows = UserEpisodeLike.select().where(
        (UserEpisodeLike.user == viewer)
        & (UserEpisodeLike.episode.in_(episode_ids))
    )
    liked_ids = {row.episode_id for row in liked_rows}

    progress_rows = UserEpisodeProgress.select().where(
        (UserEpisodeProgress.user == viewer)
        & (UserEpisodeProgress.episode.in_(episode_ids))
    )
    progress_map: dict[int, int] = {
        p.episode_id: p.position_seconds for p in progress_rows
    }

    return liked_ids, is_follow, progress_map


def _resolve_play_url(db_play_url: str) -> str:
    """根据 VIDEO_MODE 决定播放地址。
    
    demo 模式下从 VIDEO_LIST 随机选取一个地址；
    其他模式直接返回数据库中的 play_url。
    """
    settings = get_settings()
    if settings.video_mode != "demo":
        return db_play_url
    
    raw = settings.video_list
    if not raw:
        return db_play_url
    
    urls = [u.strip() for u in raw.split(",") if u.strip()]
    if not urls:
        return db_play_url
    
    return random.choice(urls)


def _build_episode_item(
    episode: DramaEpisode,
    drama: Drama,
    author: User,
    stat: DramaEpisodeStat | None,
    is_liked: bool,
    is_follow: bool,
    position: int,
) -> dict[str, Any]:
    """构建与前端 VideoType 兼容的单集播放项。"""
    if stat is None:
        stat = DramaEpisodeStat.get_or_create(episode=episode)[0]

    vip_text = "vip免费" if drama.vip_free else "付费观看"
    total_text = f"全{drama.total_episodes}集" if drama.total_episodes else ""
    look_all_btn_text = episode.look_all_btn_text or (
        f"观看完整短剧 · {total_text}" if total_text else ""
    )
    bottom_area_btn_text = episode.bottom_area_btn_text or (
        f"选集 · {total_text} · {vip_text}" if total_text else ""
    )



    return {
        "userId": author.external_user_id,
        "avatar": author.avatar_url,
        "nickname": episode.display_nickname or author.nickname,
        "isfollow": is_follow,
        "videoId": episode.external_video_id,
        "playurl": _resolve_play_url(episode.play_url),
        "poster": episode.poster_url,
        "vduser": drama.display_author_name or author.nickname,
        "vdtitle": episode.title,
        "loop": episode.loop,
        "duration": episode.duration_seconds,
        "playIng": episode.play_ing,
        "muted": episode.muted,
        "likeSum": stat.like_count,
        "isLiked": is_liked,
        "commemtSum": stat.comment_count,
        "shareSum": stat.share_count,
        "isPlaying": episode.is_playing,
        "position": position,
        "showTitleArrow": episode.show_title_arrow,
        "showLookAllBtn": episode.show_look_all_btn,
        "lookAllBtnText": look_all_btn_text,
        "total": drama.total_episodes,
        "showBottomArea": episode.show_bottom_area,
        "bottomAreaBtnText": bottom_area_btn_text,
        "toolInfo": _load_tool_info(episode.tool_info_json, stat.like_count),
    }


def _load_tool_info(
    raw_json: str | None, like_count: int
) -> list[dict[str, Any]]:
    if not raw_json:
        return [
            {"icon": "shoucang", "text": "追剧"},
            {"icon": "dianzan", "num": like_count, "text": "点赞"},
            {"icon": "share", "text": "分享"},
        ]
    try:
        value = json.loads(raw_json)
        if isinstance(value, list):
            return value
    except (json.JSONDecodeError, TypeError):
        pass
    return [
        {"icon": "shoucang", "text": "追剧"},
        {"icon": "dianzan", "num": like_count, "text": "点赞"},
        {"icon": "share", "text": "分享"},
    ]
