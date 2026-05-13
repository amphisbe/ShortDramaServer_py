from __future__ import annotations

import json
from typing import Any

from app.models import (
    Drama,
    DramaEpisode,
    DramaEpisodeStat,
    User,
)


SAMPLE_PLAY_ITEMS: list[dict[str, Any]] = [
    {
        "userId": "666dd802f366f40a8b9a4dd4",
        "avatar": "https://env-00jxgwsep3px.normal.cloudstatic.cn/snsPro/image/1744677303367.jpg",
        "nickname": "妈妈不要哭泣妈妈妈不要哭泣妈泣妈妈妈不要哭泣妈",
        "isfollow": False,
        "videoId": "672b6be8e4ca03e4581a0063",
        "playurl": "https://www.example.com.com/mu38_video/1732966630173/compress_video_3193071080.m3u8",
        "poster": "https://www.example.com/mu38_video/1732963247242/compress_video_3189636609.m3u8",
        "vduser": "追风少女💓( ˘ ³˘)💋",
        "vdtitle": "01黄亚男早年丧偶，带着年幼的两个儿子和一个女儿艰难度日，其中一个孩子还遗传了逝父的哮喘",
        "loop": True,
        "duration": 0,
        "playIng": False,
        "muted": False,
        "likeSum": 99,
        "isLiked": False,
        "commemtSum": 0,
        "shareSum": 0,
        "isPlaying": False,
        "position": 0,
        "showTitleArrow": True,
        "showLookAllBtn": True,
        "lookAllBtnText": "观看完整短剧 · 全80集",
        "total": 80,
        "showBottomArea": False,
        "bottomAreaBtnText": "选集 · 全80集 · vip免费",
        "toolInfo": [
            {"icon": "shoucang", "text": "追剧"},
            {"icon": "dianzan", "num": 99, "text": "点赞"},
            {"icon": "share", "text": "分享"},
        ],
    },
    {
        "userId": "666dd802f366f40a8b9a4dd4",
        "avatar": "https://env-00jxgwsep3px.normal.cloudstatic.cn/snsPro/image/1744677303367.jpg",
        "nickname": "妈妈不要哭泣",
        "isfollow": False,
        "videoId": "672c903442a21686318cd4ad",
        "playurl": "https://www.example.com/mu38_video/1732967301524/compress_video_3193742244.m3u8",
        "poster": "https://www.example.com/mu38_video/1730973720501/compress_video_1200159408.m3u8",
        "vduser": "追风少女💓( ˘ ³˘)💋",
        "vdtitle": "02黄亚男早年丧偶，带着年幼的两个儿子和一个女儿艰难度日，其中一个孩子还遗传了逝父的哮喘",
        "loop": True,
        "duration": 0,
        "playIng": False,
        "muted": False,
        "likeSum": 0,
        "isLiked": False,
        "commemtSum": 0,
        "shareSum": 0,
        "isPlaying": False,
        "position": 0,
        "showTitleArrow": True,
        "showLookAllBtn": False,
        "lookAllBtnText": "观看完整短剧 · 全80集",
        "total": 80,
        "showBottomArea": True,
        "bottomAreaBtnText": "选集 · 全80集 · vip免费",
        "toolInfo": [
            {"icon": "shoucang", "text": "追剧"},
            {"icon": "dianzan", "num": 199, "text": "点赞"},
            {"icon": "share", "text": "分享"},
        ],
    },
    {
        "userId": "666dd802f366f40a8b9a4dd4",
        "avatar": "https://env-00jxgwsep3px.normal.cloudstatic.cn/snsPro/image/1744677303367.jpg",
        "nickname": "妈妈不要哭泣",
        "isfollow": False,
        "videoId": "672c911ebaea7915f45e1b09",
        "playurl": "https://www.example.com/mu38_video/1732966615559/compress_video_3193055537.m3u8",
        "poster": "https://www.example.com/mu38_video/1730973966319/compress_video_1200405117.m3u8",
        "vduser": "追风少女💓( ˘ ³˘)💋",
        "vdtitle": "03黄亚男早年丧偶，带着年幼的两个儿子和一个女儿艰难度日，其中一个孩子还遗传了逝父的哮喘",
        "loop": True,
        "duration": 0,
        "playIng": False,
        "muted": False,
        "likeSum": 0,
        "isLiked": False,
        "commemtSum": 0,
        "shareSum": 0,
        "isPlaying": False,
        "position": 0,
        "showTitleArrow": True,
        "showLookAllBtn": True,
        "lookAllBtnText": "观看完整短剧 · 全80集",
        "total": 80,
        "showBottomArea": False,
        "bottomAreaBtnText": "选集 · 全80集 · vip免费",
        "toolInfo": [
            {"icon": "shoucang", "text": "追剧"},
            {"icon": "dianzan", "num": 299, "text": "点赞"},
            {"icon": "share", "text": "分享"},
        ],
    },
    {
        "userId": "666dd802f366f40a8b9a4dd4",
        "avatar": "https://env-00jxgwsep3px.normal.cloudstatic.cn/snsPro/image/1744677303367.jpg",
        "nickname": "妈妈不要哭泣",
        "isfollow": False,
        "videoId": "672ca13b29d183956332a5b2",
        "playurl": "https://www.example.com/mu38_video/1757928118893/compress_video_80807233.m3u8",
        "poster": "https://www.example.com/mu38_video/1730978068419/compress_video_1204507162.m3u8",
        "vduser": "追风少女💓( ˘ ³˘)💋",
        "vdtitle": "04黄亚男早年丧偶，带着年幼的两个儿子",
        "loop": True,
        "duration": 0,
        "playIng": False,
        "muted": False,
        "likeSum": 0,
        "isLiked": False,
        "commemtSum": 0,
        "shareSum": 0,
        "isPlaying": False,
        "position": 0,
        "showTitleArrow": True,
        "showLookAllBtn": False,
        "lookAllBtnText": "观看完整短剧 · 全80集",
        "total": 80,
        "showBottomArea": True,
        "bottomAreaBtnText": "选集 · 全80集 · vip免费",
        "toolInfo": [
            {"icon": "shoucang", "text": "追剧"},
            {"icon": "dianzan", "num": 699, "text": "点赞"},
            {"icon": "share", "text": "分享"},
        ],
    },
]


def _save_model(instance, values: dict[str, Any]) -> None:
    for key, value in values.items():
        setattr(instance, key, value)
    instance.save()


def get_or_create_user(external_user_id: str, nickname: str, avatar_url: str) -> User:
    user, _ = User.get_or_create(
        external_user_id=external_user_id,
        defaults={"nickname": nickname, "avatar_url": avatar_url, "status": 1},
    )
    _save_model(user, {"nickname": nickname, "avatar_url": avatar_url, "status": 1})
    return user


def seed_demo_data() -> None:
    """初始化用于播放接口验证的 Demo 数据。

    本函数以用户上传的 data.json 为唯一对齐标准，写入 4 条固定短剧分集数据；重复执行时会
    更新已有记录，并将同一 Demo 短剧下非样例分集置为禁用，保证 raw 接口默认只返回样例 4 条。
    """

    author_sample = SAMPLE_PLAY_ITEMS[0]
    author = get_or_create_user(
        external_user_id=author_sample["userId"],
        nickname="妈妈不要哭泣",
        avatar_url=author_sample["avatar"],
    )

    drama, _ = Drama.get_or_create(
        external_drama_id="672b6be8e4ca03e4581a0000",
        defaults={
            "title": "妈妈不要哭泣",
            "display_author_name": author_sample["vduser"],
            "author_user": author,
            "total_episodes": author_sample["total"],
            "cover_url": author_sample["poster"],
            "vip_free": True,
            "status": 1,
        },
    )
    _save_model(
        drama,
        {
            "title": "妈妈不要哭泣",
            "display_author_name": author_sample["vduser"],
            "author_user": author,
            "total_episodes": author_sample["total"],
            "cover_url": author_sample["poster"],
            "vip_free": True,
            "status": 1,
        },
    )

    sample_video_ids = [item["videoId"] for item in SAMPLE_PLAY_ITEMS]
    DramaEpisode.update(status=0).where(
        (DramaEpisode.drama == drama) & ~(DramaEpisode.external_video_id.in_(sample_video_ids))
    ).execute()

    for index, item in enumerate(SAMPLE_PLAY_ITEMS, start=1):
        episode_values = {
            "drama": drama,
            "episode_no": index,
            "title": item["vdtitle"],
            "play_url": item["playurl"],
            "poster_url": item["poster"],
            "duration_seconds": item["duration"],
            "sort_order": index,
            "status": 1,
            "display_nickname": item["nickname"],
            "loop": item["loop"],
            "play_ing": item["playIng"],
            "muted": item["muted"],
            "is_playing": item["isPlaying"],
            "show_title_arrow": item["showTitleArrow"],
            "show_look_all_btn": item["showLookAllBtn"],
            "look_all_btn_text": item["lookAllBtnText"],
            "show_bottom_area": item["showBottomArea"],
            "bottom_area_btn_text": item["bottomAreaBtnText"],
            "tool_info_json": json.dumps(item["toolInfo"], ensure_ascii=False, separators=(",", ":")),
        }
        episode, _ = DramaEpisode.get_or_create(
            external_video_id=item["videoId"],
            defaults=episode_values,
        )
        _save_model(episode, episode_values)

        stat, _ = DramaEpisodeStat.get_or_create(
            episode=episode,
            defaults={
                "like_count": item["likeSum"],
                "comment_count": item["commemtSum"],
                "share_count": item["shareSum"],
                "play_count": 0,
                "favorite_count": 0,
            },
        )
        _save_model(
            stat,
            {
                "like_count": item["likeSum"],
                "comment_count": item["commemtSum"],
                "share_count": item["shareSum"],
                "play_count": 0,
                "favorite_count": 0,
            },
        )
