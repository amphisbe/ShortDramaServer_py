from __future__ import annotations

import json
from typing import Any

from peewee import DoesNotExist

from app.models import (
    Drama,
    DramaEpisode,
    DramaEpisodeStat,
    User,
    UserEpisodeLike,
    UserEpisodeProgress,
    UserFollow,
)


def get_viewer_by_external_id(external_user_id: str | None) -> User | None:
    if not external_user_id:
        return None
    try:
        return User.get(User.external_user_id == external_user_id)
    except DoesNotExist:
        return None


def _build_default_tool_info(like_count: int) -> list[dict[str, Any]]:
    return [
        {"icon": "shoucang", "text": "Favorite"},
        {"icon": "dianzan", "num": like_count, "text": "Like"},
        {"icon": "share", "text": "Share"},
    ]


def _load_tool_info(raw_json: str | None, like_count: int) -> list[dict[str, Any]]:
    if not raw_json:
        return _build_default_tool_info(like_count)

    try:
        value = json.loads(raw_json)
    except json.JSONDecodeError:
        return _build_default_tool_info(like_count)

    if isinstance(value, list):
        return value
    return _build_default_tool_info(like_count)


def _preload_stats(
    episodes: list[DramaEpisode],
) -> dict[int, DramaEpisodeStat]:
    """批量预取剧集统计数据，返回 {episode_id: stat} 字典。"""
    episode_ids = [ep.id for ep in episodes]
    stats = DramaEpisodeStat.select().where(DramaEpisodeStat.episode.in_(episode_ids))
    stat_map: dict[int, DramaEpisodeStat] = {s.episode_id: s for s in stats}
    # 为没有统计数据的剧集创建空记录
    for ep in episodes:
        if ep.id not in stat_map:
            stat_map[ep.id] = DramaEpisodeStat.create(episode=ep)
    return stat_map


def _preload_viewer_state(
    viewer: User,
    episodes: list[DramaEpisode],
    author: User,
) -> tuple[set[int], set[int], dict[int, int]]:
    """批量预取 viewer 的点赞、关注和播放进度。

    返回 (liked_episode_ids_set, is_follow, progress_map).
    """
    episode_ids = [ep.id for ep in episodes]

    # 关注状态（作者级别，只需查一次）
    is_follow = UserFollow.select().where(
        (UserFollow.follower_user == viewer) & (UserFollow.followed_user == author)
    ).exists()

    # 点赞状态（批量查）
    liked_rows = UserEpisodeLike.select().where(
        (UserEpisodeLike.user == viewer) & (UserEpisodeLike.episode.in_(episode_ids))
    )
    liked_ids = {row.episode_id for row in liked_rows}

    # 播放进度（批量查）
    progress_rows = UserEpisodeProgress.select().where(
        (UserEpisodeProgress.user == viewer) & (UserEpisodeProgress.episode.in_(episode_ids))
    )
    progress_map: dict[int, int] = {p.episode_id: p.position_seconds for p in progress_rows}

    return liked_ids, is_follow, progress_map


def build_play_item(
    episode: DramaEpisode,
    viewer: User | None = None,
    *,
    preloaded_stat: DramaEpisodeStat | None = None,
    is_liked: bool = False,
    is_follow: bool = False,
    position: int = 0,
) -> dict[str, Any]:
    drama: Drama = episode.drama
    author: User = drama.author_user

    if preloaded_stat is not None:
        stat = preloaded_stat
    else:
        try:
            stat = DramaEpisodeStat.get(DramaEpisodeStat.episode == episode)
        except DoesNotExist:
            stat = DramaEpisodeStat.create(episode=episode)

    # viewer 状态已通过参数传入（由调用方批量预取）
    if viewer and preloaded_stat is None:
        # 降级：没有预取数据时逐个查询（不应发生）
        is_follow = UserFollow.select().where(
            (UserFollow.follower_user == viewer) & (UserFollow.followed_user == author)
        ).exists()
        is_liked = UserEpisodeLike.select().where(
            (UserEpisodeLike.user == viewer) & (UserEpisodeLike.episode == episode)
        ).exists()
        try:
            progress = UserEpisodeProgress.get(
                (UserEpisodeProgress.user == viewer) & (UserEpisodeProgress.episode == episode)
            )
            position = progress.position_seconds
        except DoesNotExist:
            position = 0

    vip_text = "VIP免费" if drama.vip_free else "付费观看"
    total_text = f"全{drama.total_episodes}集" if drama.total_episodes else ""
    look_all_btn_text = episode.look_all_btn_text or (
        f"观看完整短剧2 · {total_text}" if total_text else ""
    )
    bottom_area_btn_text = episode.bottom_area_btn_text or (
        f"{total_text} · {vip_text}" if total_text else ""
    )

    return {
        "userId": author.external_user_id,
        "avatar": author.avatar_url,
        "nickname": episode.display_nickname or author.nickname,
        "isfollow": is_follow,
        "videoId": episode.external_video_id,
        "playurl": episode.play_url,
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


def list_play_items(
    viewer_external_user_id: str | None = None,
    drama_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict[str, Any]], bool]:
    viewer = get_viewer_by_external_id(viewer_external_user_id)

    query = (
        DramaEpisode.select(DramaEpisode, Drama, User)
        .join(Drama)
        .join(User, on=(Drama.author_user == User.id))
        .where((DramaEpisode.status == 1) & (Drama.status == 1))
        .order_by(DramaEpisode.sort_order.asc(), DramaEpisode.episode_no.asc())
    )

    if drama_id is not None:
        query = query.where(DramaEpisode.drama == drama_id)

    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    total = query.count()
    episodes = list(query.paginate(page, page_size))
    has_more = page * page_size < total

    if not episodes:
        return [], has_more

    # 批量预取统计数据
    stat_map = _preload_stats(episodes)

    # 批量预取 viewer 状态
    liked_ids: set[int] = set()
    is_follow = False
    progress_map: dict[int, int] = {}
    if viewer:
        first_episode = episodes[0]
        author: User = first_episode.drama.author_user
        liked_ids, is_follow, progress_map = _preload_viewer_state(viewer, episodes, author)

    # 使用预取数据组装响应
    result = []
    for episode in episodes:
        result.append(
            build_play_item(
                episode,
                viewer,
                preloaded_stat=stat_map.get(episode.id),
                is_liked=episode.id in liked_ids,
                is_follow=is_follow,
                position=progress_map.get(episode.id, 0),
            )
        )

    return result, has_more


def list_dramas() -> list[dict[str, Any]]:
    rows = Drama.select(Drama, User).join(User, on=(Drama.author_user == User.id)).order_by(Drama.id.desc())
    return [
        {
            "id": drama.id,
            "externalDramaId": drama.external_drama_id,
            "title": drama.title,
            "displayAuthorName": drama.display_author_name,
            "authorUserId": drama.author_user.external_user_id,
            "totalEpisodes": drama.total_episodes,
            "coverUrl": drama.cover_url,
            "vipFree": drama.vip_free,
            "status": drama.status,
        }
        for drama in rows
    ]
