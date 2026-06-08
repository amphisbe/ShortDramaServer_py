"""
从 pasted_content.txt 读取短剧数据并更新数据库。
运行方式：python scripts/import_dramas.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# 确保能找到 app 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import close_database, initialize_runtime
from app.db.helpers import save_model
from app.models import (
    Drama,
    DramaEpisode,
    DramaEpisodeStat,
    User,
)


def parse_tags(tags_str: str) -> list[str]:
    return [t.strip() for t in tags_str.split(",") if t.strip()]


def parse_cast(cast_str: str) -> list[tuple[str, str, str]]:
    """解析 cast 字符串 '演员名(角色名)|演员名(角色名)'"""
    result = []
    for item in cast_str.split("|"):
        item = item.strip()
        if "(" in item:
            name, role = item.split("(", 1)
            role = role.rstrip(")")
            result.append((name.strip(), role.strip()))
        else:
            result.append((item.strip(), item.strip()))
    return result


def parse_cast_colors(colors_str: str) -> list[str]:
    return [c.strip() for c in colors_str.split(",") if c.strip()]


def parse_w_count(val: str) -> int:
    """将 '143.8w' 转换为整数"""
    num = float(val.replace("w", ""))
    return int(num * 10000)


def import_dramas() -> None:
    data_path = Path(__file__).parent.parent / "uploads" / "pasted_content.txt"
    if not data_path.exists():
        # 尝试从上传目录加载
        alt_path = Path(
            "C:\\Users\\wangs\\AppData\\Local\\Claude-3p\\local-agent-mode-sessions"
            "\\a987f584-5947-4785-a580-87a6c97a5f48\\00000000-0000-4000-8000-000000000001"
            "\\local_98a9957d-39c2-4fd2-ba93-4cc6047514c9\\uploads\\pasted_content.txt"
        )
        if alt_path.exists():
            data_path = alt_path
        else:
            print(f"数据文件未找到，请检查路径")
            return

    with open(data_path, "r", encoding="utf-8") as f:
        dramas_data = json.load(f)

    print(f"共读取 {len(dramas_data)} 部短剧数据")

    # 初始化数据库
    initialize_runtime(create_schema=True, seed=False)

    for idx, item in enumerate(dramas_data):
        drama_id = item["drama_id"]
        title = item["title_cn"]
        category = item["category"]
        description = item["description"]
        tags = parse_tags(item["tags"])
        total_ep = item["total_episodes"]
        updated_ep = item.get("updated_episodes", total_ep)
        play_count = parse_w_count(item["play_count"])
        follow_count = parse_w_count(item["follow_count"])
        is_finished = item["is_finished"]
        rating = item.get("rating", 0)
        year = item.get("year", "2025")
        lang = item.get("language", "CN")
        cast_list = parse_cast(item["cast"])
        cast_colors = parse_cast_colors(item.get("cast_colors", ""))

        # 获取或创建用户（使用 drama_id 作为 userId）
        user_id = f"user_{drama_id}"
        user, _ = User.get_or_create(
            external_user_id=user_id,
            defaults={
                "nickname": title,
                "avatar_url": "",
                "status": 1,
            },
        )
        save_model(user, {"nickname": title, "status": 1})

        # 创建或更新 Drama
        drama, _ = Drama.get_or_create(
            external_drama_id=drama_id,
            defaults={
                "title": title,
                "description": description,
                "category": category,
                "tags": json.dumps(tags, ensure_ascii=False),
                "display_author_name": title,
                "author_user": user,
                "total_episodes": total_ep,
                "cover_url": item.get("cover", ""),
                "vip_free": True,
                "play_count": play_count,
                "follow_count": follow_count,
                "status": 2 if is_finished else 1,
            },
        )
        save_model(
            drama,
            {
                "title": title,
                "description": description,
                "category": category,
                "tags": json.dumps(tags, ensure_ascii=False),
                "display_author_name": title,
                "author_user": user,
                "total_episodes": total_ep,
                "cover_url": item.get("cover", ""),
                "vip_free": True,
                "play_count": play_count,
                "follow_count": follow_count,
                "status": 2 if is_finished else 1,
            },
        )

        # 清除该短剧的旧剧集和统计数据
        DramaEpisode.delete().where(DramaEpisode.drama == drama).execute()

        # 为该短剧创建若干集（根据实际需要，创建样本集）
        sample_ep_count = min(4, total_ep)
        tool_info = json.dumps(
            [
                {"icon": "shoucang", "text": "追剧"},
                {"icon": "dianzan", "num": play_count // 10000, "text": "点赞"},
                {"icon": "share", "text": "分享"},
            ],
            ensure_ascii=False,
            separators=(",", ":"),
        )

        for ep_no in range(1, sample_ep_count + 1):
            video_id = f"vid_{drama_id}_ep{ep_no:02d}"
            ep_title = f"{ep_no:02d} {title}"

            ep_values = {
                "drama": drama,
                "episode_no": ep_no,
                "title": ep_title,
                "play_url": f"https://zydm-1312140528.cos.ap-guangzhou.myqcloud.com/dongman/video/sample_{video_id}.mp4",
                "poster_url": item.get("cover", f"/images/dramas/{drama_id}.jpg"),
                "duration_seconds": 0,
                "sort_order": ep_no,
                "status": 1,
                "display_nickname": title,
                "loop": True,
                "play_ing": False,
                "muted": False,
                "is_playing": False,
                "show_title_arrow": True,
                "show_look_all_btn": True if ep_no == 1 else False,
                "look_all_btn_text": f"观看完整短剧 · 全{total_ep}集" if ep_no == 1 else "",
                "show_bottom_area": ep_no > 1,
                "bottom_area_btn_text": f"选集 · 全{total_ep}集 · {'vip免费' if True else '付费'}",
                "tool_info_json": tool_info,
            }

            episode, _ = DramaEpisode.get_or_create(
                external_video_id=video_id,
                defaults=ep_values,
            )
            save_model(episode, ep_values)

            # 创建统计数据
            stat, _ = DramaEpisodeStat.get_or_create(
                episode=episode,
                defaults={
                    "like_count": play_count // 10000,
                    "comment_count": 0,
                    "share_count": 0,
                    "play_count": play_count,
                    "favorite_count": follow_count,
                },
            )
            save_model(
                stat,
                {
                    "like_count": play_count // 10000,
                    "comment_count": 0,
                    "share_count": 0,
                    "play_count": play_count,
                    "favorite_count": follow_count,
                },
            )

        progress = (idx + 1) / len(dramas_data) * 100
        print(f"  [{idx + 1}/{len(dramas_data)}] {title} ({category}) - {total_ep}集 - {progress:.0f}%")

    print(f"\n✅ 导入完成！共导入 {len(dramas_data)} 部短剧")


if __name__ == "__main__":
    try:
        import_dramas()
    finally:
        close_database()
