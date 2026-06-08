"""
短剧服务端全接口测试脚本

用法（在 ShortDramaServer_py 目录下运行）：
    python scripts/smoke_test.py

或者先启动服务再手动测试：
    python -m app.main            # 启动服务
    python scripts/test_all_api.py  # 另一个终端运行本脚本
"""

import sys
import os

# 确保能找到 app 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app.db.database import initialize_runtime, close_database
from app.main import app


def setup_module():
    """初始化数据库并填充种子数据"""
    initialize_runtime(create_schema=True, seed=True)


def teardown_module():
    close_database()


def test_health():
    """1. 健康检查"""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    print("[PASS] /health")


def test_drama_list():
    """2. 短剧列表（首页）"""
    r = client.get("/api/v1/dramas", params={"category": "推荐", "page": 1, "page_size": 10})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["code"] == 0, data
    assert len(data["data"]["data"]) == 8, f"期望 8 部短剧，实际 {len(data['data']['data'])}"
    dramas = data["data"]["data"]
    print(f"  → 返回 {len(dramas)} 部短剧")
    for d in dramas:
        assert "dramaId" in d
        assert "title" in d
        assert "category" in d
        assert "tags" in d
        assert "playCount" in d
        print(f"    {d['dramaId']}: {d['title']} [{d['category']}] 播放:{d['playCount']}")
    print("[PASS] /api/v1/dramas")


def test_drama_list_with_category():
    """3. 分类筛选"""
    r = client.get("/api/v1/dramas", params={"category": "古装"})
    data = r.json()
    assert len(data["data"]["data"]) >= 2, f"古装类应有至少 2 部，实际 {len(data['data']['data'])}"
    for d in data["data"]["data"]:
        assert d["category"] == "古装"
    print(f"  → 古装类返回 {len(data['data']['data'])} 部")
    print("[PASS] /api/v1/dramas?category=古装")


def test_featured():
    """4. 主推短剧"""
    r = client.get("/api/v1/dramas/featured")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data is not None
    assert data["title"] == "妈妈不要哭泣"
    assert data["playCount"] == "156.7w"
    print(f"  → 主推: {data['title']}")
    print("[PASS] /api/v1/dramas/featured")


def test_hot():
    """5. 热门短剧"""
    r = client.get("/api/v1/dramas/hot", params={"count": 4})
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) == 4
    # 验证按播放量降序
    for i in range(len(data) - 1):
        pc_i = float(data[i]["playCount"].replace("w", ""))
        pc_j = float(data[i + 1]["playCount"].replace("w", ""))
        assert pc_i >= pc_j, f"{data[i]['title']} 播放量应 >= {data[i+1]['title']}"
    print(f"  → 热门 Top4: {[d['title'] for d in data]}")
    print("[PASS] /api/v1/dramas/hot")


def test_trending():
    """6. 热搜短剧"""
    r = client.get("/api/v1/dramas/trending", params={"count": 5})
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) == 5
    print(f"  → 热搜 Top5: {[d['title'] for d in data]}")
    print("[PASS] /api/v1/dramas/trending")


def test_recommended():
    """7. 猜你喜欢"""
    r = client.get("/api/v1/dramas/recommended", params={"exclude_id": "drama_001", "count": 4})
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) == 4
    for d in data:
        assert d["dramaId"] != "drama_001", "不应包含被排除的短剧"
    print(f"  → 推荐 4 部: {[d['title'] for d in data]}")
    print("[PASS] /api/v1/dramas/recommended")


def test_detail():
    """8. 短剧详情"""
    r = client.get("/api/v1/dramas/drama_001")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["title"] == "妈妈不要哭泣"
    assert data["category"] == "家庭"
    assert len(data["tags"]) >= 2
    assert "description" in data
    print(f"  → 标题: {data['title']}  分类: {data['category']}  标签: {data['tags']}")
    print("[PASS] /api/v1/dramas/drama_001")


def test_detail_not_found():
    """9. 短剧详情 - 不存在"""
    r = client.get("/api/v1/dramas/not_exist_id")
    assert r.status_code == 200
    assert r.json()["code"] == 404
    print("[PASS] /api/v1/dramas/not_exist_id → 404")


def test_related():
    """10. 同类推荐"""
    r = client.get("/api/v1/dramas/drama_001/related", params={"category": "家庭"})
    assert r.status_code == 200
    data = r.json()["data"]
    for d in data:
        assert d["dramaId"] != "drama_001"
    print(f"  → 同类推荐 {len(data)} 部")
    print("[PASS] /api/v1/dramas/drama_001/related")


def test_episodes():
    """11. 剧集列表"""
    r = client.get("/api/v1/dramas/drama_001/episodes")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    episodes = body["data"]["list"]
    assert len(episodes) >= 4, f"drama_001 应有至少 4 集，实际 {len(episodes)}"
    ep = episodes[0]
    assert "videoId" in ep
    assert "playurl" in ep
    assert "vdtitle" in ep
    assert "toolInfo" in ep
    assert len(ep["toolInfo"]) == 3
    print(f"  → 返回 {len(episodes)} 集，首集: {ep['vdtitle']}")
    print("[PASS] /api/v1/dramas/drama_001/episodes")


def test_episodes_not_found():
    """12. 剧集列表 - 不存在"""
    r = client.get("/api/v1/dramas/not_exist/episodes")
    assert r.status_code == 200
    assert r.json()["code"] == 404
    print("[PASS] /api/v1/dramas/not_exist/episodes → 404")


def test_find_by_user():
    """13. 通过 userId 反查短剧"""
    r = client.get("/api/v1/dramas/by-user/user_mama")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["dramaId"] == "drama_001", f"期望 drama_001，实际 {data['dramaId']}"
    print(f"  → 反查 userId=user_mama → dramaId={data['dramaId']}")
    print("[PASS] /api/v1/dramas/by-user/user_mama")


def test_find_by_user_not_found():
    """14. 反查 - 不存在"""
    r = client.get("/api/v1/dramas/by-user/nonexistent")
    assert r.status_code == 200
    assert r.json()["code"] == 404
    print("[PASS] /api/v1/dramas/by-user/nonexistent → 404")


def test_categories():
    """15. 分类覆盖测试 - 验证每个分类都有数据"""
    categories = ["推荐", "古装", "现代", "言情", "家庭", "都市", "穿越"]
    for cat in categories:
        r = client.get("/api/v1/dramas", params={"category": cat, "page_size": 50})
        count = len(r.json()["data"]["data"])
        if cat == "推荐":
            assert count == 8, f"推荐应返回全部 8 部，实际 {count}"
        else:
            assert count >= 1, f"分类 '{cat}' 应至少有 1 部短剧，实际 {count}"
        print(f"  [{cat}] {count} 部")


if __name__ == "__main__":
    print("=" * 60)
    print("短剧服务端 API 全接口测试")
    print("=" * 60)
    print()

    # 初始化
    print("[初始化] 创建数据库 + 种子数据...")
    setup_module()
    print("[初始化] 完成\n")

    client = TestClient(app)

    tests = [
        ("健康检查", test_health),
        ("短剧列表", test_drama_list),
        ("分类筛选", test_drama_list_with_category),
        ("主推短剧", test_featured),
        ("热门短剧", test_hot),
        ("热搜短剧", test_trending),
        ("猜你喜欢", test_recommended),
        ("短剧详情", test_detail),
        ("详情-不存在", test_detail_not_found),
        ("同类推荐", test_related),
        ("剧集列表", test_episodes),
        ("剧集-不存在", test_episodes_not_found),
        ("反查短剧", test_find_by_user),
        ("反查-不存在", test_find_by_user_not_found),
        ("分类覆盖", test_categories),
    ]

    passed = 0
    failed = 0
    for name, fn_test in tests:
        try:
            fn_test()
            passed += 1
        except Exception as e:
            print(f"[FAIL] {name}: {e}")
            failed += 1
        print()

    print("=" * 60)
    print(f"结果: {passed} 通过, {failed} 失败 / {len(tests)} 项")
    print("=" * 60)

    teardown_module()
    sys.exit(0 if failed == 0 else 1)
