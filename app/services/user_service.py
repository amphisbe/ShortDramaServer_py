"""用户数据的辅助查询服务。"""

from app.models import (
    Drama,
    DramaEpisode,
    DramaEpisodeStat,
    EpisodeShare,
    User,
    UserDramaFavorite,
    UserEpisodeLike,
    UserEpisodeProgress,
    UserFollow,
)

from app.services.drama_service import _build_drama_item


def _format_drama_for_list(drama: Drama) -> dict:
    return _build_drama_item(drama)


def get_user_by_external_id(external_id: str) -> User | None:
    try:
        return User.get(User.external_user_id == external_id)
    except Exception:
        return None


def get_user_profile(external_user_id: str) -> dict | None:
    """用户信息 + 统计数据。"""
    user = get_user_by_external_id(external_user_id)
    if user is None:
        return None

    favorites_count = (
        UserDramaFavorite.select()
        .where(UserDramaFavorite.user == user)
        .count()
    )
    watched_count = (
        UserEpisodeProgress.select()
        .where((UserEpisodeProgress.user == user) & (UserEpisodeProgress.is_finished == True))
        .count()
    )
    following_count = (
        UserFollow.select()
        .where(UserFollow.follower_user == user)
        .count()
    )

    return {
        "userId": user.external_user_id,
        "nickname": user.nickname,
        "avatar": user.avatar_url,
        "favoritesCount": favorites_count,
        "watchedCount": watched_count,
        "followingCount": following_count,
    }


def get_user_favorites(external_user_id: str, page: int = 1, page_size: int = 20) -> dict:
    """用户收藏的短剧列表。"""
    user = get_user_by_external_id(external_user_id)
    if user is None:
        return {"data": [], "total": 0, "page": page}

    query = (
        Drama.select()
        .join(UserDramaFavorite, on=(UserDramaFavorite.drama == Drama.id))
        .where((UserDramaFavorite.user == user) & (Drama.status == 1))
        .order_by(UserDramaFavorite.created_at.desc())
    )

    total = query.count()
    rows = list(query.paginate(page, page_size))
    return {
        "data": [_format_drama_for_list(d) for d in rows],
        "total": total,
        "page": page,
    }


def get_user_history(external_user_id: str, page: int = 1, page_size: int = 20) -> dict:
    """用户观看历史（去重按短剧维度，取最后观看时间）。"""
    user = get_user_by_external_id(external_user_id)
    if user is None:
        return {"data": [], "total": 0, "page": page}

    # 查出用户所有剧集进度，按更新时间倒序，JOIN 预取 DramaEpisode 避免 FK 懒加载
    progresses = list(
        UserEpisodeProgress
        .select(UserEpisodeProgress, DramaEpisode)
        .join(DramaEpisode, on=(UserEpisodeProgress.episode == DramaEpisode.id))
        .where(UserEpisodeProgress.user == user)
        .order_by(UserEpisodeProgress.updated_at.desc())
    )

    seen_drama_ids: set[int] = set()
    drama_order: list[int] = []
    for p in progresses:
        drama_id = p.episode.drama_id
        if drama_id not in seen_drama_ids:
            seen_drama_ids.add(drama_id)
            drama_order.append(drama_id)

    total = len(drama_order)
    start = (page - 1) * page_size
    end = start + page_size
    page_ids = drama_order[start:end]

    dramas = []
    for did in page_ids:
        try:
            drama = Drama.get((Drama.id == did) & (Drama.status == 1))
            dramas.append(_format_drama_for_list(drama))
        except Exception:
            pass

    return {"data": dramas, "total": total, "page": page}


# ============ 观看进度 ============


def save_progress(
    external_user_id: str,
    external_video_id: str,
    position_seconds: int,
    is_finished: bool = False,
) -> bool:
    """保存或更新用户的观看进度。"""
    user = get_user_by_external_id(external_user_id)
    print("user:", user)
    if user is None:
        return False
    try:
        episode = DramaEpisode.get(DramaEpisode.external_video_id == external_video_id)
    except Exception:
        return False

    # print(f"save_progress:::::::: user_id={external_user_id}, video_id={external_video_id}, position_seconds={position_seconds}, is_finished={is_finished}")
    progress, _ = UserEpisodeProgress.get_or_create(
        user=user,
        episode=episode,
        defaults={"position_seconds": position_seconds, "is_finished": is_finished},
    )
    progress.position_seconds = max(progress.position_seconds, position_seconds)
    progress.is_finished = progress.is_finished or is_finished
    progress.save()
    return True


def get_progress(external_user_id: str, drama_id: str) -> dict:
    """查询用户在某短剧下的观看进度。"""
    user = get_user_by_external_id(external_user_id)
    if user is None:
        return {"data": []}

    try:
        drama = Drama.get(Drama.external_drama_id == drama_id)
    except Exception:
        return {"data": []}

    progresses = list(
        UserEpisodeProgress.select()
        .join(DramaEpisode)
        .where(
            (UserEpisodeProgress.user == user)
            & (DramaEpisode.drama == drama)
        )
    )

    result = []
    for p in progresses:
        result.append({
            "videoId": p.episode.external_video_id,
            "episodeNo": p.episode.episode_no,
            "positionSeconds": p.position_seconds,
            "isFinished": p.is_finished,
            "updatedAt": p.updated_at.isoformat() if p.updated_at else None,
        })
    return {"data": result}


# ============ 点赞 ============


def toggle_like(external_user_id: str, external_video_id: str) -> dict:
    """点赞/取消点赞（toggle），返回新状态和赞数。"""
    user = get_user_by_external_id(external_user_id)
    print("toggle_like user:", user)
    if user is None:
        return {"liked": False, "likeCount": 0}

    try:
        episode = DramaEpisode.get(DramaEpisode.external_video_id == external_video_id)
    except Exception:
        return {"liked": False, "likeCount": 0}

    stat, _ = DramaEpisodeStat.get_or_create(
        episode=episode, defaults={"like_count": 0}
    )

    try:
        like = UserEpisodeLike.get(user=user, episode=episode)
        like.delete_instance()
        stat.like_count = max(0, stat.like_count - 1)
        stat.save()
        return {"liked": False, "likeCount": stat.like_count}
    except Exception:
        UserEpisodeLike.create(user=user, episode=episode)
        stat.like_count += 1
        stat.save()
        return {"liked": True, "likeCount": stat.like_count}


def check_liked(external_user_id: str, external_video_id: str) -> dict:
    """查询用户是否已点赞某个剧集。"""
    user = get_user_by_external_id(external_user_id)
    if user is None:
        return {"liked": False, "likeCount": 0}

    try:
        episode = DramaEpisode.get(DramaEpisode.external_video_id == external_video_id)
    except Exception:
        return {"liked": False, "likeCount": 0}

    stat, _ = DramaEpisodeStat.get_or_create(
        episode=episode, defaults={"like_count": 0}
    )
    exists = UserEpisodeLike.select().where(
        (UserEpisodeLike.user == user) & (UserEpisodeLike.episode == episode)
    ).exists()

    return {"liked": exists, "likeCount": stat.like_count}


# ============ 收藏 ============


def toggle_favorite(external_user_id: str, external_video_id: str) -> dict:
    """收藏/取消收藏短剧（toggle），通过剧集 video_id 反查短剧后切换收藏状态。"""
    user = get_user_by_external_id(external_user_id)
    if user is None:
        return {"favorited": False, "followCount": 0}

    try:
        episode = DramaEpisode.get(DramaEpisode.external_video_id == external_video_id)
        drama = episode.drama
    except Exception:
        return {"favorited": False, "followCount": 0}

    try:
        fav = UserDramaFavorite.get(user=user, drama=drama)
        fav.delete_instance()
        drama.follow_count = max(0, drama.follow_count - 1)
        drama.save()
        return {"favorited": False, "followCount": drama.follow_count}
    except Exception:
        UserDramaFavorite.create(user=user, drama=drama)
        drama.follow_count += 1
        drama.save()
        return {"favorited": True, "followCount": drama.follow_count}


# ============ 分享 ============


def record_share(
    external_user_id: str,
    external_video_id: str,
    channel: str,
) -> dict:
    """记录一次分享事件，返回分享状态和分享数。"""
    try:
        episode = DramaEpisode.get(DramaEpisode.external_video_id == external_video_id)
    except Exception:
        return {"shared": False, "shareCount": 0}

    user = get_user_by_external_id(external_user_id)

    EpisodeShare.create(
        episode=episode,
        user=user,
        channel=channel or "unknown",
    )

    stat, _ = DramaEpisodeStat.get_or_create(
        episode=episode, defaults={"share_count": 0}
    )
    stat.share_count += 1
    stat.save()

    return {"shared": True, "shareCount": stat.share_count}
