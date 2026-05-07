from __future__ import annotations

from peewee import IntegrityError

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


def get_or_create_user(external_user_id: str, nickname: str, avatar_url: str) -> User:
    user, _ = User.get_or_create(
        external_user_id=external_user_id,
        defaults={"nickname": nickname, "avatar_url": avatar_url, "status": 1},
    )
    return user


def seed_demo_data() -> None:
    """初始化用于播放接口验证的 Demo 数据。

    数据字段尽量贴近用户上传的 data.json 样例，确保 `/api/v1/video/play-list/raw`
    能返回兼容当前前端的顶层数组结构。
    """

    viewer = get_or_create_user(
        external_user_id="666dd802f366f40a8b9a4aa1",
        nickname="测试观众",
        avatar_url="https://www.example.com/avatar/viewer.jpg",
    )
    author = get_or_create_user(
        external_user_id="666dd802f366f40a8b9a4dd4",
        nickname="妈妈不要哭泣",
        avatar_url="https://env-00jxgwsep3px.normal.cloudstatic.cn/snsPro/image/1744677303367.jpg",
    )

    drama, _ = Drama.get_or_create(
        external_drama_id="672b6be8e4ca03e4581a0000",
        defaults={
            "title": "妈妈不要哭泣",
            "display_author_name": "追风少女💓( ˘ ³˘)💋",
            "author_user": author,
            "total_episodes": 80,
            "cover_url": "https://www.example.com/mu38_video/cover/demo.jpg",
            "vip_free": True,
            "status": 1,
        },
    )

    sample_titles = [
        "01黄亚男早年丧偶，带着年幼的两个儿子和一个女儿艰难度日，其中一个孩子还遗传了逝父的哮喘",
        "02黄亚男为了孩子四处奔波，意外发现旧友隐藏多年的秘密",
        "03一家人遭遇新的生活考验，亲情与命运再次交织",
    ]

    episodes: list[DramaEpisode] = []
    for index, title in enumerate(sample_titles, start=1):
        episode, _ = DramaEpisode.get_or_create(
            external_video_id=f"672b6be8e4ca03e4581a00{60 + index}",
            defaults={
                "drama": drama,
                "episode_no": index,
                "title": title,
                "play_url": f"https://www.example.com/mu38_video/1732966630173/compress_video_31930710{index}.m3u8",
                "poster_url": f"https://www.example.com/mu38_video/1732963247242/poster_31896366{index}.jpg",
                "duration_seconds": 0,
                "sort_order": index,
                "status": 1,
            },
        )
        episodes.append(episode)
        DramaEpisodeStat.get_or_create(
            episode=episode,
            defaults={
                "like_count": 99 if index == 1 else 20 + index,
                "comment_count": 0,
                "share_count": index - 1,
                "play_count": 1000 * index,
                "favorite_count": 10 * index,
            },
        )

    try:
        UserFollow.get_or_create(follower_user=viewer, followed_user=author)
        UserEpisodeLike.get_or_create(user=viewer, episode=episodes[0])
        UserDramaFavorite.get_or_create(user=viewer, drama=drama)
        UserEpisodeProgress.get_or_create(
            user=viewer,
            episode=episodes[0],
            defaults={"position_seconds": 0, "is_finished": False},
        )
    except IntegrityError:
        pass
