"""短剧数据服务层。

提供首页/详情页/播放页所需的统一数据查询接口。
后续接入真实搜索/推荐引擎时只需修改此文件中的查询逻辑。
"""

from __future__ import annotations

import base64
import random
import json
import math
from collections import Counter
from typing import Any

from peewee import DoesNotExist, fn

from app.models import (
    Drama,
    DramaEpisode,
    DramaEpisodeStat,
    User,
    UserDramaFavorite,
    UserEpisodeLike,
    UserEpisodeProgress,
    UserFollow,
)


from app.core.config import get_settings
import logging
logger = logging.getLogger(__name__)

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
    cover = f"{static_base}/{drama.external_drama_id}/封面.jpg"
    return {
        "dramaId": drama.external_drama_id or str(drama.id),
        "title": drama.title,
        # "cover": drama.cover_url,
        "cover": cover,
        "banner": drama.banner_url or "",
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
    query = Drama.select().where((Drama.status == 1) & (Drama.lang == 'en'))

    # if category and category != "推荐":
    #     query = query.where(Drama.category == category)

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
    query = Drama.select().where((Drama.status == 1) & (Drama.hot == 1))
    # if category and category != "推荐":
    #     query = query.where(Drama.category == category)
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
    exclude_drama_id: str = "",
    category: str = "",
    count: int = 5,
    viewer_user_id: str | None = None,
    cursor: str | None = None,
) -> dict[str, Any]:
    """猜你喜欢 — 规则引擎 + 游标分页。

    有 viewer_user_id 时走个性化推荐（优先级填充 + 交叉排序）；
    无 viewer_user_id 时走热门兜底（冷启动）。
    游标分页避免 Feed 流翻页时的数据重复/遗漏。
    """
    count = min(max(count, 1), 20)

    if viewer_user_id:
        return _recommend_personalized(
            viewer_user_id=viewer_user_id,
            exclude_drama_id=exclude_drama_id,
            category=category,
            count=count,
            cursor=cursor,
        )
    else:
        return _recommend_hot_fallback(
            exclude_drama_id=exclude_drama_id,
            category=category,
            count=count,
            cursor=cursor,
        )


# ============ 猜你喜欢 — 个性化推荐 ============


def _recommend_personalized(
    viewer_user_id: str,
    exclude_drama_id: str,
    category: str,
    count: int,
    cursor: str | None,
) -> dict[str, Any]:
    user = _get_user_by_external_id(viewer_user_id)
    if user is None:
        return _recommend_hot_fallback(exclude_drama_id, category, count, cursor)

    viewed_ids = _get_user_viewed_drama_ids(user)
    fav_drama_ids = _get_user_fav_drama_ids(user)
    excluded_ids = viewed_ids | fav_drama_ids

    # 提取偏好标签 → 热门池 + 标签池
    pref_tags = _get_user_preference_tags(user)
    hot_pool = _query_hot_pool(pref_tags, excluded_ids, exclude_drama_id, category)
    tag_pool = _query_tag_pool(pref_tags, excluded_ids, exclude_drama_id, category)

    # 合并候选，去重
    hot_ids = {d.id for d in hot_pool}
    tag_pool = [d for d in tag_pool if d.id not in hot_ids]

    # 探索随机池：排除热门池和标签池已覆盖的
    all_selected_ids = hot_ids | {d.id for d in tag_pool}
    explore_pool = _query_explore_pool(all_selected_ids, excluded_ids, exclude_drama_id, category)

    # 按优先级加载足量候选
    all_candidates = _priority_fill(hot_pool, tag_pool, explore_pool)

    # 游标分页
    return _paginate_with_cursor(all_candidates, count, cursor)


def _recommend_hot_fallback(
    exclude_drama_id: str,
    category: str,
    count: int,
    cursor: str | None,
) -> dict[str, Any]:
    """冷启动：全站热门，按 hotness_score 排序，按 category 去重避免全是同一分类。"""
    query = Drama.select().where(Drama.status == 1)
    if exclude_drama_id:
        query = query.where(Drama.external_drama_id != exclude_drama_id)
    if category and category != "推荐":
        query = query.where(Drama.category == category)

    score = (Drama.play_count * 0.6 + Drama.follow_count * 0.4)
    rows = list(query.order_by(score.desc(), Drama.id.desc()))

    # 按 category 去重，保证多样性
    seen_categories: set[str] = set()
    candidates: list[Drama] = []
    for d in rows:
        if d.category not in seen_categories or len(candidates) < count // 2 + 1:
            candidates.append(d)
            seen_categories.add(d.category)

    return _paginate_with_cursor(candidates, count, cursor)


# ============ 游标分页 ============


def _encode_cursor(hotness_score: float, drama_id: int) -> str:
    raw = f"{hotness_score}:{drama_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[float, int]:
    raw = base64.urlsafe_b64decode(cursor.encode()).decode()
    score_str, id_str = raw.split(":")
    return float(score_str), int(id_str)


def _hotness_score(drama: Drama) -> float:
    return drama.play_count * 0.6 + drama.follow_count * 0.4


def _paginate_with_cursor(
    candidates: list[Drama],
    count: int,
    cursor: str | None,
) -> dict[str, Any]:
    """对候选列表应用游标分页，返回当前页数据和下一页 cursor。"""
    # 游标定位
    start_idx = 0
    if cursor:
        cursor_decoded = False
        try:
            cursor_score, cursor_id = _decode_cursor(cursor)
            cursor_decoded = True
        except Exception:
            pass
        if cursor_decoded:
            for i, d in enumerate(candidates):
                s = _hotness_score(d)
                if s < cursor_score or (s == cursor_score and d.id < cursor_id):
                    start_idx = i
                    break
            else:
                # 游标已越过所有候选项，返回空页
                start_idx = len(candidates)

    page = candidates[start_idx : start_idx + count]
    has_more = (start_idx + count) < len(candidates)

    next_cursor = ""
    if has_more and page:
        last = page[-1]
        next_cursor = _encode_cursor(_hotness_score(last), last.id)

    return {
        "data": [_build_drama_item(d) for d in page],
        "cursor": next_cursor,
        "hasMore": has_more,
    }


# ============ 优先级填充 + 交叉排序 ============


def _priority_fill(
    hot_pool: list[Drama],
    tag_pool: list[Drama],
    explore_pool: list[Drama],
) -> list[Drama]:
    """优先级填充：热门最多 3 条 → 标签最多 2 条 → 随机补齐。
    结果按交叉顺序排列，打散同类型，避免前 N 条全是热门。
    """
    hot = list(hot_pool[:3])
    tag = list(tag_pool[:2])
    explore = list(explore_pool)

    # 热门不足时标签多取
    needed = 3 - len(hot)
    if needed > 0 and tag_pool:
        tag.extend(tag_pool[len(tag) : len(tag) + needed])
        tag = tag[:3]  # 标签最多也不超过 3

    # 交叉排序：[H, T, H, E, H, T, E, ...]
    result: list[Drama] = []
    while len(result) < 8:  # 取足够多供游标分页消耗
        added = False
        if hot:
            result.append(hot.pop(0))
            added = True
        if tag:
            result.append(tag.pop(0))
            added = True
        if explore:
            result.append(explore.pop(0))
            added = True
        if not added:
            break

    return result


# ============ 用户行为分析 ============


def _get_user_by_external_id(external_id: str) -> User | None:
    try:
        return User.get(User.external_user_id == external_id)
    except DoesNotExist:
        return None


def _get_user_viewed_drama_ids(user: User) -> set[int]:
    """从观看历史中提取已看过的短剧 ID 集合。"""
    progresses = (
        UserEpisodeProgress
        .select(UserEpisodeProgress, DramaEpisode)
        .join(DramaEpisode, on=(UserEpisodeProgress.episode == DramaEpisode.id))
        .where(UserEpisodeProgress.user == user)
    )
    return {p.episode.drama_id for p in progresses}


def _get_user_fav_drama_ids(user: User) -> set[int]:
    """提取用户已收藏的短剧 ID 集合。"""
    rows = UserDramaFavorite.select().where(UserDramaFavorite.user == user)
    return {r.drama_id for r in rows}


def _get_user_preference_tags(user: User) -> list[str]:
    """从用户收藏 + 观看历史统计偏好标签，按频次降序返回。"""
    fav_dramas = (
        Drama.select()
        .join(UserDramaFavorite, on=(UserDramaFavorite.drama == Drama.id))
        .where(UserDramaFavorite.user == user)
    )
    viewed_drama_ids = _get_user_viewed_drama_ids(user)
    viewed_dramas = []
    if viewed_drama_ids:
        viewed_dramas = list(Drama.select().where(Drama.id.in_(viewed_drama_ids)))

    tag_counter: Counter = Counter()
    for d in list(fav_dramas) + viewed_dramas:
        tag_counter[d.category] += 2  # category 权重更高
        for tag in _load_tags(d.tags):
            tag_counter[tag] += 1

    return [tag for tag, _ in tag_counter.most_common(10)]


# ============ 候选池查询 ============


def _query_hot_pool(
    pref_tags: list[str],
    excluded_ids: set[int],
    exclude_drama_id: str,
    category: str,
) -> list[Drama]:
    """同类热门池：category 命中偏好标签，按 play_count 降序。"""
    query = Drama.select().where(Drama.status == 1)
    if excluded_ids:
        query = query.where(Drama.id.not_in(excluded_ids))
    if exclude_drama_id:
        query = query.where(Drama.external_drama_id != exclude_drama_id)
    if category and category != "推荐":
        query = query.where(Drama.category == category)

    if pref_tags:
        query = query.where(Drama.category.in_(pref_tags))

    return list(query.order_by(Drama.play_count.desc()).limit(30))


def _query_tag_pool(
    pref_tags: list[str],
    excluded_ids: set[int],
    exclude_drama_id: str,
    category: str,
) -> list[Drama]:
    """标签匹配池：tags JSON 中包含偏好标签，按 follow_count 降序。"""
    if not pref_tags:
        return []

    query = Drama.select().where(Drama.status == 1)
    if excluded_ids:
        query = query.where(Drama.id.not_in(excluded_ids))
    if exclude_drama_id:
        query = query.where(Drama.external_drama_id != exclude_drama_id)
    if category and category != "推荐":
        query = query.where(Drama.category == category)

    # Peewee 不支持 JSON 内 LIKE，先用 Python 侧过滤
    rows = list(query.order_by(Drama.follow_count.desc()).limit(50))
    return [d for d in rows if any(tag in _load_tags(d.tags) for tag in pref_tags)]


def _query_explore_pool(
    all_selected_ids: set[int],
    excluded_ids: set[int],
    exclude_drama_id: str,
    category: str,
) -> list[Drama]:
    """探索随机池：排除已入选的，随机排序。"""
    query = Drama.select().where(Drama.status == 1)
    combined = all_selected_ids | excluded_ids
    if combined:
        query = query.where(Drama.id.not_in(combined))
    if exclude_drama_id:
        query = query.where(Drama.external_drama_id != exclude_drama_id)
    if category and category != "推荐":
        query = query.where(Drama.category == category)

    return list(query.order_by(fn.Random()).limit(20))


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

    logger.info(
        "短剧：%s, 集数：%d, 用户：%s",
        drama_id, len(episodes), viewer_external_user_id
    )
    drama.total_episodes = len(episodes)

    if not episodes:
        return {"data": [], "found": True, "totalEpisodes": drama.total_episodes}

    # 批量预取统计数据
    stat_map = _preload_stats(episodes)

    # 预取 viewer 状态
    liked_ids: set[int] = set()
    progress_map: dict[int, int] = {}
    is_favorite = False
    logger
    # author: User = drama.author_user
    author = None
    is_follow = False
    if viewer_external_user_id:
        viewer = _get_viewer(viewer_external_user_id)
        if viewer is not None:
            liked_ids, is_follow, progress_map = _preload_viewer_state(
                viewer, episodes, author
            )
            is_favorite = (
                UserDramaFavorite.select()
                .where(
                    (UserDramaFavorite.user == viewer)
                    & (UserDramaFavorite.drama == drama)
                )
                .exists()
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
                is_favorite,
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
    missing_ids = [ep.id for ep in episodes if ep.id not in stat_map]
    if missing_ids:
        # 并发请求可能同时补同一集的统计行（主键 episode_id），
        # 用 INSERT IGNORE / INSERT OR IGNORE 忽略已存在的行，再统一读回，避免 1062 Duplicate entry
        DramaEpisodeStat.insert_many(
            [{"episode": ep_id} for ep_id in missing_ids]
        ).on_conflict_ignore().execute()
        for s in DramaEpisodeStat.select().where(
            DramaEpisodeStat.episode.in_(missing_ids)
        ):
            stat_map[s.episode_id] = s
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
            # & (UserFollow.followed_user == author)
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
        return f"{settings.static_host}/{db_play_url}"
    
    raw = settings.video_list
    if not raw:
        return f"{settings.static_host}/{db_play_url}"
    
    urls = [u.strip() for u in raw.split(",") if u.strip()]
    if not urls:
        return f"{settings.static_host}/{db_play_url}"
    
    return random.choice(urls)


def _resolve_subtitle_url(db_subtitle_url: str | None) -> str:
    """字幕地址：不受 VIDEO_MODE/VIDEO_LIST 影响。

    为空返回 ""；已是绝对地址（http/https 或 //）原样返回；
    相对路径拼接 STATIC_HOST。
    """
    url = (db_subtitle_url or "").strip()
    if not url:
        return ""
    if url.startswith(("http://", "https://", "//")):
        return url
    return f"{get_settings().static_host.rstrip('/')}/{url.lstrip('/')}"


def _build_episode_item(
    episode: DramaEpisode,
    drama: Drama,
    author: User,
    stat: DramaEpisodeStat | None,
    is_liked: bool,
    is_follow: bool,
    position: int,
    is_favorite: bool = False,
) -> dict[str, Any]:
    """构建与前端 VideoType 兼容的单集播放项。"""
    if stat is None:
        stat = DramaEpisodeStat.get_or_create(episode=episode)[0]

    vip_text = "VIP Free" if drama.vip_free else "付费观看"
    total_text = f"All {drama.total_episodes} Episodes" if drama.total_episodes else ""
    look_all_btn_text = episode.look_all_btn_text or (
        f"观看完整短剧 · {total_text}" if total_text else ""
    )
    bottom_area_btn_text = episode.bottom_area_btn_text or (
        f"{total_text} · {vip_text}" if total_text else ""
    )

    # look_all_btn_text = ''

    return {
        # "userId": author.external_user_id,
        # "avatar": author.avatar_url,
        "userId": -1,
        "avatar": '',
        # "nickname": episode.display_nickname or author.nickname,
        "nickname": drama.title,
        "isfollow": is_follow,
        "episodeId": episode.id,
        "videoId": episode.external_video_id,
        "playurl": _resolve_play_url(episode.play_url),
        "duration": episode.duration_seconds,
        "poster": episode.poster_url,
        # "vduser": drama.display_author_name or author.nickname,
        "vduser": "Author",
        # "vdtitle": episode.title,
        # "vdtitle": f"第 {episode.episode_no} 集",
        "vdtitle": "",
        "subtitleUrl": _resolve_subtitle_url(episode.subtitle_url),
        "subtitleFormat": "srt",
        "subtitleLang": "en",
        "subtitleEnabled": bool((episode.subtitle_url or "").strip()),
        "loop": episode.loop,
        "duration": episode.duration_seconds,
        "playIng": episode.play_ing,
        "muted": episode.muted,
        "likeSum": stat.like_count,
        "isLiked": is_liked,
        "isFavorite": is_favorite,
        "commemtSum": stat.comment_count,
        "shareSum": stat.share_count,
        "isPlaying": episode.is_playing,
        "position": position,
        "showTitleArrow": episode.show_title_arrow,
        # "showLookAllBtn": episode.show_look_all_btn,
        "showLookAllBtn": False,
        "lookAllBtnText": look_all_btn_text,
        "total": drama.total_episodes,
        "showBottomArea": episode.show_bottom_area,
        "bottomAreaBtnText": bottom_area_btn_text,
        "toolInfo": _apply_tool_state(
            _load_tool_info(episode.tool_info_json, stat.like_count),
            is_liked,
            is_favorite,
        ),
    }


def _apply_tool_state(
    tool_info: list[dict[str, Any]], is_liked: bool, is_favorite: bool
) -> list[dict[str, Any]]:
    """按当前用户状态设置工具栏图标：已点赞 dianzan_h，已收藏 shoucang_h（播放器以 _h 表示选中）。"""
    result = []
    for tool in tool_info:
        if not isinstance(tool, dict):
            result.append(tool)
            continue
        tool = dict(tool)
        icon = str(tool.get("icon") or "")
        if icon in ("dianzan", "dianzan_h"):
            tool["icon"] = "dianzan_h" if is_liked else "dianzan"
        elif icon in ("shoucang", "shoucang_h"):
            tool["icon"] = "shoucang_h" if is_favorite else "shoucang"
        result.append(tool)
    return result


def _load_tool_info(
    raw_json: str | None, like_count: int
) -> list[dict[str, Any]]:
    if not raw_json:
        return [
            {"icon": "shoucang", "text": "Favorite"},
            {"icon": "dianzan", "num": like_count, "text": "Like"},
            {"icon": "share", "text": "Share"},
        ]
    try:
        value = json.loads(raw_json)
        if isinstance(value, list):
            return value
    except (json.JSONDecodeError, TypeError):
        pass
    return [
        {"icon": "shoucang", "text": "Favorite"},
        {"icon": "dianzan", "num": like_count, "text": "Like"},
        {"icon": "share", "text": "Share"},
    ]
