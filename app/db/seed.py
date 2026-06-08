from __future__ import annotations

import json
from typing import Any

from app.db.helpers import save_model
from app.models import (
    Drama,
    DramaEpisode,
    DramaEpisodeStat,
    User,
)

# ============ 测试用户 ============

SAMPLE_USERS: list[dict[str, Any]] = [
    {"userId": "user_mama", "nickname": "追风少女💓", "avatar": "https://env-00jxgwsep3px.normal.cloudstatic.cn/snsPro/image/1744677303367.jpg"},
    {"userId": "user_haomen", "nickname": "短剧制作组", "avatar": ""},
    {"userId": "user_rebirth", "nickname": "短剧制作组", "avatar": ""},
    {"userId": "user_zongcai", "nickname": "短剧制作组", "avatar": ""},
    {"userId": "user_tishen", "nickname": "短剧制作组", "avatar": ""},
    {"userId": "user_shenyi", "nickname": "短剧制作组", "avatar": ""},
    {"userId": "user_shanhun", "nickname": "短剧制作组", "avatar": ""},
    {"userId": "user_qianjin", "nickname": "短剧制作组", "avatar": ""},
    {"userId": "user_xuanyi", "nickname": "悬疑故事人", "avatar": "https://env-00jxgwsep3px.normal.cloudstatic.cn/snsPro/image/1744677303367.jpg"},
    {"userId": "user_xiju", "nickname": "笑点制造机", "avatar": ""},
    {"userId": "user_qihuan", "nickname": "幻想工坊", "avatar": ""},
    {"userId": "user_xianxia", "nickname": "仙侠小生", "avatar": ""},
    {"userId": "user_tianchong", "nickname": "糖分补给站", "avatar": ""},
    {"userId": "user_niandai", "nickname": "时光客栈", "avatar": ""},
    {"userId": "user_gongdou", "nickname": "深宫说书人", "avatar": ""},
    {"userId": "user_zhuixu", "nickname": "逆袭故事会", "avatar": ""},
]

# ============ 短剧数据 ============

DRAMAS: list[dict[str, Any]] = [
    {
        "external_drama_id": "drama_001",
        "title": "妈妈不要哭泣",
        "description": "黄亚男早年丧偶，带着年幼的两个儿子和一个女儿艰难度日，其中一个孩子还遗传了逝父的哮喘。面对生活的重重困难，她坚强不屈，用自己的双手撑起了一个家。",
        "category": "家庭",
        "tags": ["家庭", "伦理", "催泪"],
        "author_user_id": "user_mama",
        "total_episodes": 80,
        "play_count": 1567000,
        "follow_count": 123000,
        "vip_free": True,
        "status": 1,
        "episodes": [
            {"video_id": "vid_mama_01", "title": "01 黄亚男早年丧偶，带着年幼的两个儿子和一个女儿艰难度日", "sort": 1},
            {"video_id": "vid_mama_02", "title": "02 黄亚男带着孩子们努力生活，却遭遇意外变故", "sort": 2},
            {"video_id": "vid_mama_03", "title": "03 面对命运的捉弄，她从不轻言放弃", "sort": 3},
            {"video_id": "vid_mama_04", "title": "04 黄亚男凭自己的双手撑起一个家", "sort": 4},
        ],
    },
    {
        "external_drama_id": "drama_002",
        "title": "误入豪门",
        "description": "她意外闯入上流社会，命运的齿轮开始转动。豪门深处的秘密、阴谋与爱情交织，她能否在这场没有硝烟的战争中守护自己？",
        "category": "都市",
        "tags": ["都市", "豪门", "情感"],
        "author_user_id": "user_haomen",
        "total_episodes": 80,
        "play_count": 983000,
        "follow_count": 96000,
        "vip_free": True,
        "status": 1,
        "episodes": [
            {"video_id": "vid_haomen_01", "title": "01 她意外闯入上流社会，命运从此改变", "sort": 1},
            {"video_id": "vid_haomen_02", "title": "02 豪门恩怨，她能否在明争暗斗中生存？", "sort": 2},
            {"video_id": "vid_haomen_03", "title": "03 一张神秘照片引出的惊天秘密", "sort": 3},
        ],
    },
    {
        "external_drama_id": "drama_003",
        "title": "重生之女王归来",
        "description": "前世被最信任的人背叛，重生回到命运的转折点。这一次，她不再天真，步步为营，要让所有伤害过她的人付出代价。",
        "category": "穿越",
        "tags": ["穿越", "重生", "爽文"],
        "author_user_id": "user_rebirth",
        "total_episodes": 60,
        "play_count": 876000,
        "follow_count": 78000,
        "vip_free": True,
        "status": 2,
        "episodes": [
            {"video_id": "vid_rebirth_01", "title": "01 重生一世，她誓要改写命运", "sort": 1},
            {"video_id": "vid_rebirth_02", "title": "02 手撕白莲花，这一次她绝不手软", "sort": 2},
            {"video_id": "vid_rebirth_03", "title": "03 商业帝国的第一步，从收购开始", "sort": 3},
        ],
    },
    {
        "external_drama_id": "drama_004",
        "title": "我的极品总裁",
        "description": "一场意外让她遇见了高冷总裁，契约婚姻，各取所需。然而当真心悄然萌动，这场交易还能继续吗？",
        "category": "言情",
        "tags": ["言情", "甜宠", "都市"],
        "author_user_id": "user_zongcai",
        "total_episodes": 100,
        "play_count": 762000,
        "follow_count": 68000,
        "vip_free": True,
        "status": 1,
        "episodes": [
            {"video_id": "vid_zongcai_01", "title": "01 一场意外，让她遇见了那个男人", "sort": 1},
            {"video_id": "vid_zongcai_02", "title": "02 契约婚姻，各取所需的交易", "sort": 2},
        ],
    },
    {
        "external_drama_id": "drama_005",
        "title": "替身新娘",
        "description": "她替姐姐出嫁，却不知嫁的是那个传说中冷酷无情的男人。新婚之夜他冷眼相待，却不知真正的爱情正在悄然萌芽。",
        "category": "古装",
        "tags": ["古装", "虐恋", "言情"],
        "author_user_id": "user_tishen",
        "total_episodes": 75,
        "play_count": 654000,
        "follow_count": 56000,
        "vip_free": True,
        "status": 1,
        "episodes": [
            {"video_id": "vid_tishen_01", "title": "01 她替姐姐出嫁，却不知嫁的是那个男人", "sort": 1},
            {"video_id": "vid_tishen_02", "title": "02 新婚之夜，他冷眼相待", "sort": 2},
        ],
    },
    {
        "external_drama_id": "drama_006",
        "title": "神医嫡女",
        "description": "绝世医术在身，她不再是那个任人欺凌的嫡女。且看她如何用医术救人、用智慧复仇，活出精彩人生。",
        "category": "古装",
        "tags": ["古装", "医术", "复仇"],
        "author_user_id": "user_shenyi",
        "total_episodes": 120,
        "play_count": 587000,
        "follow_count": 41000,
        "vip_free": True,
        "status": 2,
        "episodes": [
            {"video_id": "vid_shenyi_01", "title": "01 绝世医术在手，她誓要讨回一切", "sort": 1},
        ],
    },
    {
        "external_drama_id": "drama_007",
        "title": "闪婚后大佬他慌了",
        "description": "闪婚老公竟是隐藏大佬？一场偶然的相遇，一次冲动的闪婚，她不知道自己的生活即将发生翻天覆地的变化。",
        "category": "言情",
        "tags": ["言情", "甜宠", "闪婚"],
        "author_user_id": "user_shanhun",
        "total_episodes": 55,
        "play_count": 423000,
        "follow_count": 48000,
        "vip_free": True,
        "status": 2,
        "episodes": [
            {"video_id": "vid_shanhun_01", "title": "01 闪婚老公竟是隐藏大佬？", "sort": 1},
        ],
    },
    {
        "external_drama_id": "drama_008",
        "title": "我本千金",
        "description": "流落民间的大小姐终于回归，面对家族的明争暗斗，她用自己的智慧和善良赢得尊重，也收获了真爱。",
        "category": "现代",
        "tags": ["现代", "励志", "言情"],
        "author_user_id": "user_qianjin",
        "total_episodes": 85,
        "play_count": 365000,
        "follow_count": 37000,
        "vip_free": True,
        "status": 1,
        "episodes": [
            {"video_id": "vid_qianjin_01", "title": "01 流落民间的大小姐终于回归", "sort": 1},
        ],
    },
    {
        "external_drama_id": "drama_009",
        "title": "重生之将门毒后",
        "description": "前世她为家族呕心沥血，却落得满门抄斩的下场。重活一世，她誓要护住至亲，手刃仇敌，让所有欺她辱她之人付出代价。",
        "category": "古装",
        "tags": ["古装", "重生", "复仇", "虐恋"],
        "author_user_id": "user_gongdou",
        "total_episodes": 90,
        "play_count": 1345000,
        "follow_count": 115000,
        "vip_free": True,
        "status": 1,
        "episodes": [
            {"video_id": "vid_gongdou_01", "title": "01 重活一世，她誓要改写家族命运", "sort": 1},
            {"video_id": "vid_gongdou_02", "title": "02 步步为营，她让仇人血债血偿", "sort": 2},
            {"video_id": "vid_gongdou_03", "title": "03 旧爱重逢，这一世他还会错过吗", "sort": 3},
        ],
    },
    {
        "external_drama_id": "drama_010",
        "title": "战神归来",
        "description": "他，一代战神，隐退都市。为守护挚爱，他甘愿平凡。当爱人受辱、家人被欺，他决定不再隐藏，让整个城市为之颤抖！",
        "category": "都市",
        "tags": ["都市", "战神", "逆袭", "爽文"],
        "author_user_id": "user_zhuixu",
        "total_episodes": 100,
        "play_count": 2130000,
        "follow_count": 189000,
        "vip_free": True,
        "status": 1,
        "episodes": [
            {"video_id": "vid_zhuixu_01", "title": "01 一代战神隐退都市，为爱甘愿平凡", "sort": 1},
            {"video_id": "vid_zhuixu_02", "title": "02 爱人受辱，他决定不再隐藏实力", "sort": 2},
            {"video_id": "vid_zhuixu_03", "title": "03 战神一怒，整个城市为之颤抖", "sort": 3},
        ],
    },
    {
        "external_drama_id": "drama_011",
        "title": "夜半歌声",
        "description": "废弃剧院每晚传出神秘歌声，新来的实习警察不信鬼神，执意调查。当她一步步揭开真相，却发现最恐怖的并非鬼怪，而是人心。",
        "category": "悬疑",
        "tags": ["悬疑", "惊悚", "推理"],
        "author_user_id": "user_xuanyi",
        "total_episodes": 40,
        "play_count": 892000,
        "follow_count": 72000,
        "vip_free": True,
        "status": 1,
        "episodes": [
            {"video_id": "vid_xuanyi_01", "title": "01 废弃剧院的午夜歌声", "sort": 1},
            {"video_id": "vid_xuanyi_02", "title": "02 实习警察的深入调查", "sort": 2},
        ],
    },
    {
        "external_drama_id": "drama_012",
        "title": "我在古代当网红",
        "description": "现代网红穿越到古代王朝，凭借直播带货、短视频等现代技能混得风生水起。皇帝成了她的榜一大哥，太子追着要签名，且看她如何用互联网思维颠覆古代！",
        "category": "喜剧",
        "tags": ["喜剧", "穿越", "搞笑", "甜宠"],
        "author_user_id": "user_xiju",
        "total_episodes": 60,
        "play_count": 1780000,
        "follow_count": 156000,
        "vip_free": True,
        "status": 1,
        "episodes": [
            {"video_id": "vid_xiju_01", "title": "01 穿越古代第一件事：开直播", "sort": 1},
            {"video_id": "vid_xiju_02", "title": "02 皇帝成了我的榜一大哥", "sort": 2},
            {"video_id": "vid_xiju_03", "title": "03 用现代营销术征服古代市场", "sort": 3},
        ],
    },
    {
        "external_drama_id": "drama_013",
        "title": "我的师父是神仙",
        "description": "普通大学生偶然救下一只白猫，没想到竟是仙界下凡的仙尊。从此他开启了修真之路，校园生活变得精彩纷呈……",
        "category": "奇幻",
        "tags": ["奇幻", "修真", "校园", "搞笑"],
        "author_user_id": "user_qihuan",
        "total_episodes": 70,
        "play_count": 756000,
        "follow_count": 63000,
        "vip_free": True,
        "status": 1,
        "episodes": [
            {"video_id": "vid_qihuan_01", "title": "01 救了一只猫，从此人生开挂", "sort": 1},
            {"video_id": "vid_qihuan_02", "title": "02 仙界仙尊当我的师父", "sort": 2},
        ],
    },
    {
        "external_drama_id": "drama_014",
        "title": "九重天劫",
        "description": "修真界第一天才渡劫失败，却意外重生到下界一名废柴身上。前世仇敌环伺，这一世他凭借前世记忆，重修无上功法，再踏修仙之路。",
        "category": "仙侠",
        "tags": ["仙侠", "修真", "重生", "热血"],
        "author_user_id": "user_xianxia",
        "total_episodes": 120,
        "play_count": 1456000,
        "follow_count": 134000,
        "vip_free": False,
        "status": 1,
        "episodes": [
            {"video_id": "vid_xianxia_01", "title": "01 渡劫失败，重生废柴之身", "sort": 1},
            {"video_id": "vid_xianxia_02", "title": "02 重修无上功法，震惊宗门", "sort": 2},
            {"video_id": "vid_xianxia_03", "title": "03 前世仇人现身，这一世谁主沉浮", "sort": 3},
        ],
    },
    {
        "external_drama_id": "drama_015",
        "title": "冰糖炖雪梨",
        "description": "元气少女遇上高冷学霸，一场意外的合租让两人从互看不顺眼到渐生情愫。甜到掉牙的校园纯恋，每一帧都是心动的信号。",
        "category": "青春",
        "tags": ["青春", "甜宠", "校园", "言情"],
        "author_user_id": "user_tianchong",
        "total_episodes": 50,
        "play_count": 967000,
        "follow_count": 85000,
        "vip_free": True,
        "status": 1,
        "episodes": [
            {"video_id": "vid_tianchong_01", "title": "01 元气少女遇上高冷学霸", "sort": 1},
            {"video_id": "vid_tianchong_02", "title": "02 意外的合租生活开始了", "sort": 2},
        ],
    },
    {
        "external_drama_id": "drama_016",
        "title": "胡同烟火",
        "description": "八十年代的老北京胡同里，几个年轻人怀揣梦想共同成长。改革开放的浪潮中，他们经历了爱情的甜蜜与苦涩、友情的考验与坚守。一幅充满烟火气的生活画卷。",
        "category": "年代",
        "tags": ["年代", "情感", "励志", "怀旧"],
        "author_user_id": "user_niandai",
        "total_episodes": 65,
        "play_count": 534000,
        "follow_count": 48000,
        "vip_free": True,
        "status": 1,
        "episodes": [
            {"video_id": "vid_niandai_01", "title": "01 八十年代胡同里的青春", "sort": 1},
            {"video_id": "vid_niandai_02", "title": "02 改革开放浪潮中的抉择", "sort": 2},
        ],
    },
    {
        "external_drama_id": "drama_017",
        "title": "消失的她",
        "description": "新婚妻子突然失踪，丈夫焦急寻妻。然而随着调查深入，一个个惊人的秘密浮出水面——每个人都戴着面具，真相远比想象中更加残酷。",
        "category": "悬疑",
        "tags": ["悬疑", "反转", "都市", "情感"],
        "author_user_id": "user_xuanyi",
        "total_episodes": 30,
        "play_count": 2100000,
        "follow_count": 198000,
        "vip_free": True,
        "status": 1,
        "episodes": [
            {"video_id": "vid_xuanyi_04", "title": "01 新婚妻子离奇失踪", "sort": 1},
            {"video_id": "vid_xuanyi_05", "title": "02 调查越深，秘密越多", "sort": 2},
            {"video_id": "vid_xuanyi_06", "title": "03 真相让人不寒而栗", "sort": 3},
        ],
    },
    {
        "external_drama_id": "drama_018",
        "title": "龙王殿",
        "description": "三年前他入赘被嘲，三年后龙王殿主归来，整个天下都要为他让路！且看一代龙王如何碾压仇敌，站在世界之巅。",
        "category": "都市",
        "tags": ["都市", "赘婿", "龙王", "爽文"],
        "author_user_id": "user_zhuixu",
        "total_episodes": 120,
        "play_count": 1870000,
        "follow_count": 167000,
        "vip_free": True,
        "status": 1,
        "episodes": [
            {"video_id": "vid_zhuixu_04", "title": "01 入赘三年受尽白眼", "sort": 1},
            {"video_id": "vid_zhuixu_05", "title": "02 龙王殿主归来，万人俯首", "sort": 2},
            {"video_id": "vid_zhuixu_06", "title": "03 碾压仇敌，登顶世界之巅", "sort": 3},
        ],
    },
    {
        "external_drama_id": "drama_019",
        "title": "权宠天下",
        "description": "她是现代金牌特工，穿越成冷宫弃妃。面对皇子们的明争暗斗，她凭借现代技能游刃有余。却不想那个冷面王爷早已看穿一切，对她步步紧逼……",
        "category": "古装",
        "tags": ["古装", "穿越", "宫斗", "甜宠"],
        "author_user_id": "user_gongdou",
        "total_episodes": 80,
        "play_count": 1123000,
        "follow_count": 98000,
        "vip_free": True,
        "status": 1,
        "episodes": [
            {"video_id": "vid_gongdou_04", "title": "01 金牌特工穿越成冷宫弃妃", "sort": 1},
            {"video_id": "vid_gongdou_05", "title": "02 冷面王爷的步步紧逼", "sort": 2},
        ],
    },
    {
        "external_drama_id": "drama_020",
        "title": "我和我的神仙闺蜜",
        "description": "平凡女孩偶然结识了一位来自仙界的神仙，从此开启了啼笑皆非的同居生活。神仙闺蜜用法力帮她解决各种难题，却也惹来一堆麻烦。",
        "category": "喜剧",
        "tags": ["喜剧", "奇幻", "搞笑", "友情"],
        "author_user_id": "user_xiju",
        "total_episodes": 45,
        "play_count": 689000,
        "follow_count": 57000,
        "vip_free": True,
        "status": 1,
        "episodes": [
            {"video_id": "vid_xiju_04", "title": "01 我的闺蜜是神仙", "sort": 1},
            {"video_id": "vid_xiju_05", "title": "02 神仙闺蜜的现代生存指南", "sort": 2},
        ],
    },
]

DEFAULT_TOOL_INFO = [
    {"icon": "shoucang", "text": "追剧"},
    {"icon": "dianzan", "num": 0, "text": "点赞"},
    {"icon": "share", "text": "分享"},
]

PLAY_URL_TEMPLATE = "https://zydm-1312140528.cos.ap-guangzhou.myqcloud.com/dongman/video/sample_{}.mp4"
POSTER_URL_TEMPLATE = "https://env-00jxgwsep3px.normal.cloudstatic.cn/snsPro/image/sample_poster_{}.jpg"


def get_or_create_user(user_id: str, nickname: str, avatar_url: str) -> User:
    user, _ = User.get_or_create(
        external_user_id=user_id,
        defaults={"nickname": nickname, "avatar_url": avatar_url, "status": 1},
    )
    save_model(user, {"nickname": nickname, "avatar_url": avatar_url, "status": 1})
    return user


def seed_demo_data() -> None:
    """初始化短剧 Demo 数据：8 部短剧，含多集播放数据和统计信息。"""

    # 1. upsert 所有用户
    user_map: dict[str, User] = {}
    for u in SAMPLE_USERS:
        user_map[u["userId"]] = get_or_create_user(
            u["userId"], u["nickname"], u["avatar"]
        )

    # 2. upsert 所有短剧
    for drama_info in DRAMAS:
        author = user_map[drama_info["author_user_id"]]
        drama, _ = Drama.get_or_create(
            external_drama_id=drama_info["external_drama_id"],
            defaults={
                "title": drama_info["title"],
                "description": drama_info["description"],
                "category": drama_info["category"],
                "tags": json.dumps(drama_info["tags"], ensure_ascii=False),
                "display_author_name": author.nickname,
                "author_user": author,
                "total_episodes": drama_info["total_episodes"],
                "cover_url": "",
                "vip_free": drama_info.get("vip_free", True),
                "play_count": drama_info["play_count"],
                "follow_count": drama_info["follow_count"],
                "status": drama_info["status"],
            },
        )
        save_model(
            drama,
            {
                "title": drama_info["title"],
                "description": drama_info["description"],
                "category": drama_info["category"],
                "tags": json.dumps(drama_info["tags"], ensure_ascii=False),
                "display_author_name": author.nickname,
                "author_user": author,
                "total_episodes": drama_info["total_episodes"],
                "cover_url": "",
                "vip_free": drama_info.get("vip_free", True),
                "play_count": drama_info["play_count"],
                "follow_count": drama_info["follow_count"],
                "status": drama_info["status"],
            },
        )

        # 3. upsert 剧集
        sample_video_ids = [ep["video_id"] for ep in drama_info["episodes"]]
        DramaEpisode.update(status=0).where(
            (DramaEpisode.drama == drama)
            & ~(DramaEpisode.external_video_id.in_(sample_video_ids))
        ).execute()

        for idx, ep_info in enumerate(drama_info["episodes"], start=1):
            episode_values = {
                "drama": drama,
                "episode_no": idx,
                "title": ep_info["title"],
                "play_url": PLAY_URL_TEMPLATE.format(ep_info["video_id"]),
                "poster_url": POSTER_URL_TEMPLATE.format(drama_info["external_drama_id"]),
                "duration_seconds": 0,
                "sort_order": ep_info["sort"],
                "status": 1,
                "display_nickname": drama_info["title"],
                "loop": True,
                "play_ing": False,
                "muted": False,
                "is_playing": False,
                "show_title_arrow": True,
                "show_look_all_btn": True,
                "look_all_btn_text": f"观看完整短剧 · 全{drama_info['total_episodes']}集",
                "show_bottom_area": idx > 1,
                "bottom_area_btn_text": f"选集 · 全{drama_info['total_episodes']}集 · {'vip免费' if drama_info.get('vip_free', True) else '付费'}",
                "tool_info_json": json.dumps(
                    [{"icon": "shoucang", "text": "追剧"},
                     {"icon": "dianzan", "num": drama_info["play_count"] // 10000, "text": "点赞"},
                     {"icon": "share", "text": "分享"}],
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            }
            episode, _ = DramaEpisode.get_or_create(
                external_video_id=ep_info["video_id"],
                defaults=episode_values,
            )
            save_model(episode, episode_values)

            stat, _ = DramaEpisodeStat.get_or_create(
                episode=episode,
                defaults={
                    "like_count": drama_info["play_count"] // 10000,
                    "comment_count": 0,
                    "share_count": 0,
                    "play_count": drama_info["play_count"],
                    "favorite_count": drama_info["follow_count"],
                },
            )
            save_model(
                stat,
                {
                    "like_count": drama_info["play_count"] // 10000,
                    "comment_count": 0,
                    "share_count": 0,
                    "play_count": drama_info["play_count"],
                    "favorite_count": drama_info["follow_count"],
                },
            )
