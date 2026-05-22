from __future__ import annotations

import json
from typing import Any

from app.db.helpers import save_model
from app.models import Drama, DramaEpisode, DramaEpisodeStat, User


TEMP_TEST_PLAY_ITEMS: list[dict[str, Any]] = [
    {
        "userId": "test_user_0000000001",
        "avatar": "https://www.example.com/static/avatar/test_user_01.jpg",
        "nickname": "临时测试账号",
        "videoId": "test_video_000000001",
        "playurl": "https://www.example.com/test_video/001/index.m3u8",
        "poster": "https://www.example.com/test_video/001/poster.jpg",
        "vduser": "临时测试短剧作者",
        "vdtitle": "01临时测试短剧第一集：用于验证数据库写入和播放列表接口",
        "duration": 68,
        "likeSum": 101,
        "commemtSum": 11,
        "shareSum": 7,
        "showLookAllBtn": True,
        "showBottomArea": False,
        "toolInfo": [
            {"icon": "shoucang", "text": "追剧"},
            {"icon": "dianzan", "num": 101, "text": "点赞"},
            {"icon": "share", "text": "分享"},
        ],
    },
    {
        "userId": "test_user_0000000001",
        "avatar": "https://www.example.com/static/avatar/test_user_01.jpg",
        "nickname": "临时测试账号",
        "videoId": "test_video_000000002",
        "playurl": "https://www.example.com/test_video/002/index.m3u8",
        "poster": "https://www.example.com/test_video/002/poster.jpg",
        "vduser": "临时测试短剧作者",
        "vdtitle": "02临时测试短剧第二集：用于验证分页、统计和 UI 展示字段",
        "duration": 72,
        "likeSum": 202,
        "commemtSum": 22,
        "shareSum": 14,
        "showLookAllBtn": False,
        "showBottomArea": True,
        "toolInfo": [
            {"icon": "shoucang", "text": "追剧"},
            {"icon": "dianzan", "num": 202, "text": "点赞"},
            {"icon": "share", "text": "分享"},
        ],
    },
]


def seed_temp_test_data() -> dict[str, Any]:
    """写入临时测试短剧数据。

    该函数用于开发、联调和临时验收场景，重复执行时会更新同一批测试用户、短剧、分集和统计数据，
    不会无限追加重复记录。生产环境应移除或关闭调用入口。
    """

    author_sample = TEMP_TEST_PLAY_ITEMS[0]
    author, _ = User.get_or_create(
        external_user_id=author_sample["userId"],
        defaults={
            "nickname": author_sample["nickname"],
            "avatar_url": author_sample["avatar"],
            "status": 1,
        },
    )
    save_model(
        author,
        {
            "nickname": author_sample["nickname"],
            "avatar_url": author_sample["avatar"],
            "status": 1,
        },
    )

    drama, _ = Drama.get_or_create(
        external_drama_id="test_drama_00000001",
        defaults={
            "title": "临时测试短剧",
            "display_author_name": author_sample["vduser"],
            "author_user": author,
            "total_episodes": len(TEMP_TEST_PLAY_ITEMS),
            "cover_url": author_sample["poster"],
            "vip_free": True,
            "status": 1,
        },
    )
    save_model(
        drama,
        {
            "title": "临时测试短剧",
            "display_author_name": author_sample["vduser"],
            "author_user": author,
            "total_episodes": len(TEMP_TEST_PLAY_ITEMS),
            "cover_url": author_sample["poster"],
            "vip_free": True,
            "status": 1,
        },
    )

    episode_ids: list[int] = []
    for index, item in enumerate(TEMP_TEST_PLAY_ITEMS, start=1):
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
            "loop": True,
            "play_ing": False,
            "muted": False,
            "is_playing": False,
            "show_title_arrow": True,
            "show_look_all_btn": item["showLookAllBtn"],
            "look_all_btn_text": f"观看完整短剧 · 全{len(TEMP_TEST_PLAY_ITEMS)}集",
            "show_bottom_area": item["showBottomArea"],
            "bottom_area_btn_text": f"选集 · 全{len(TEMP_TEST_PLAY_ITEMS)}集 · vip免费",
            "tool_info_json": json.dumps(item["toolInfo"], ensure_ascii=False, separators=(",", ":")),
        }
        episode, _ = DramaEpisode.get_or_create(
            external_video_id=item["videoId"],
            defaults=episode_values,
        )
        save_model(episode, episode_values)
        episode_ids.append(int(episode.id))

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
        save_model(
            stat,
            {
                "like_count": item["likeSum"],
                "comment_count": item["commemtSum"],
                "share_count": item["shareSum"],
                "play_count": 0,
                "favorite_count": 0,
            },
        )

    return {
        "drama_id": int(drama.id),
        "external_drama_id": drama.external_drama_id,
        "episode_ids": episode_ids,
        "episode_count": len(episode_ids),
        "message": "临时测试数据已写入或更新完成",
    }
