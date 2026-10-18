"""真实观看时长统计接口测试（tmp_path SQLite，不进 lifespan，不连真实库）。"""

import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from peewee import SqliteDatabase

from app.core.config import get_settings
from app.db import database as database_module
from app.db.database import database_proxy
from app.main import app
from app.models import (
    ALL_MODELS,
    Drama,
    DramaEpisode,
    DramaEpisodeStat,
    User,
    UserEpisodeWatchDaily,
    UserWatchDaily,
    UserWatchSession,
)
from app.schemas.watch import WatchEventIn
from app.services import auth_service, watch_service

SECRET = "test-secret-for-watch-stats-0123456789"
T0 = datetime(2026, 10, 19, 1, 0, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self, start: datetime) -> None:
        self.t = start

    def now(self) -> datetime:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t = self.t + timedelta(seconds=seconds)


@pytest.fixture()
def env(tmp_path: Path, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "jwt_secret", SECRET)
    monkeypatch.setattr(settings, "watch_session_secret", "")
    monkeypatch.setattr(settings, "watch_events_enabled", True)
    previous = database_proxy.obj
    db = SqliteDatabase(tmp_path / "watch.db", pragmas={"journal_mode": "wal"}, timeout=10)
    database_proxy.initialize(db)
    db.connect()
    db.create_tables(ALL_MODELS)
    clock = Clock(T0)
    monkeypatch.setattr(watch_service, "_now", clock.now)
    watch_service.reset_rate_limits()

    alice = User.create(external_user_id="user_alice", nickname="Alice")
    bob = User.create(external_user_id="user_bob", nickname="Bob")
    drama = Drama.create(external_drama_id="drama_w", title="W", author_user=alice,
                         total_episodes=4, play_count=1000)
    ep1 = DramaEpisode.create(drama=drama, external_video_id="w_ep1", episode_no=1,
                              play_url="w/1.mp4", duration_seconds=120)
    ep2 = DramaEpisode.create(drama=drama, external_video_id="w_ep2", episode_no=2,
                              play_url="w/2.mp4", duration_seconds=120)
    ep_zero = DramaEpisode.create(drama=drama, external_video_id="w_zero", episode_no=3,
                                  play_url="w/3.mp4", duration_seconds=0)
    ep_short = DramaEpisode.create(drama=drama, external_video_id="w_short", episode_no=4,
                                   play_url="w/4.mp4", duration_seconds=3)
    DramaEpisodeStat.create(episode=ep1, play_count=777)
    try:
        yield SimpleNamespace(client=TestClient(app), db=db, clock=clock, alice=alice, bob=bob,
                              drama=drama, ep1=ep1, ep2=ep2, ep_zero=ep_zero, ep_short=ep_short)
    finally:
        watch_service.reset_rate_limits()
        db.close()
        database_proxy.initialize(previous)


def bearer(user: User) -> dict:
    return {"Authorization": "Bearer " + auth_service._create_backend_token(user)}


def create(env, user=None, video="w_ep1") -> dict:
    user = user or env.alice
    return env.client.post("/api/v1/me/watch-sessions", json={"video_id": video},
                           headers=bearer(user)).json()


def start(env, user=None, video="w_ep1") -> str:
    body = create(env, user, video)
    assert body["code"] == 0, body
    assert body["data"]["session_id"].startswith("ws1.")
    assert body["data"]["expires_in"] == 1800
    return body["data"]["session_id"]


def report(env, sid, seq, watched, user=None, video="w_ep1", position=None, headers=None) -> dict:
    user = user or env.alice
    body = {"session_id": sid, "seq": seq, "video_id": video, "watched_seconds": watched,
            "position_seconds": watched if position is None else position, "is_finished": False}
    return env.client.post("/api/v1/me/watch-events", json=body,
                           headers=bearer(user) if headers is None else headers).json()


def ue_row(user, episode, day=None):
    day = day or T0.date()
    return UserEpisodeWatchDaily.get((UserEpisodeWatchDaily.user == user.id)
                                     & (UserEpisodeWatchDaily.episode == episode.id)
                                     & (UserEpisodeWatchDaily.stat_date == day))


def user_row(user, day=None):
    day = day or T0.date()
    return UserWatchDaily.get((UserWatchDaily.user == user.id) & (UserWatchDaily.stat_date == day))


def real_counts(env, episode=None):
    episode = episode or env.ep1
    stat = DramaEpisodeStat.get_or_none(DramaEpisodeStat.episode == episode.id)
    return (stat.real_play_count if stat else 0), Drama.get_by_id(env.drama.id).real_play_count


# ---------------- 鉴权 / 签名 ----------------


def test_requires_token_and_rejects_foreign_or_forged_sessions(env):
    c = env.client
    assert c.post("/api/v1/me/watch-sessions", json={"video_id": "w_ep1"}).json()["code"] == 401
    assert c.post("/api/v1/me/watch-events", json={}).json()["code"] == 401
    bad = {"Authorization": "Bearer nope"}
    assert c.post("/api/v1/me/watch-sessions", json={"video_id": "w_ep1"}, headers=bad).json()["code"] == 401

    sid = start(env)
    env.clock.advance(10)
    # 他人会话
    assert report(env, sid, 1, 10, user=env.bob)["code"] == 403
    # 伪造签名 / 篡改 payload / 其他密钥签发
    head, payload, sig = sid.split(".")
    forged_sig = sig[:-1] + ("A" if sig[-1] != "A" else "B")
    assert report(env, f"{head}.{payload}.{forged_sig}", 1, 10)["code"] == 403
    other = watch_service.issue_session_token("user_alice", env.ep1.id, int(T0.timestamp()), "00" * 8)
    tampered_payload = other.split(".")[1]
    assert report(env, f"{head}.{tampered_payload}.{sig}", 1, 10)["code"] == 403
    assert report(env, "garbage", 1, 10)["code"] == 403
    # 正常
    r = report(env, sid, 1, 10)
    assert r["code"] == 0 and r["data"]["accepted_watched_seconds"] == 10.0
    # 令牌字符串不落库，只存 nonce
    row = UserWatchSession.get()
    assert len(row.session_id) == 16 and watch_service.parse_session_token(sid)["n"] == row.session_id


def test_validation_errors_and_missing_episode(env):
    c, h = env.client, bearer(env.alice)
    assert c.post("/api/v1/me/watch-sessions", json={}, headers=h).json()["code"] == 400
    assert c.post("/api/v1/me/watch-sessions", headers=h).json()["code"] == 400
    assert create(env, video="nope")["code"] == 404
    DramaEpisode.update(status=0).where(DramaEpisode.id == env.ep2.id).execute()
    assert create(env, video="w_ep2")["code"] == 404

    sid = start(env)
    env.clock.advance(10)
    assert report(env, sid, 0, 10)["code"] == 400
    assert report(env, sid, 100001, 10)["code"] == 400
    assert report(env, sid, 1, -1)["code"] == 400
    assert report(env, sid, 1, 21601)["code"] == 400
    assert report(env, sid, 1, 10, position=-1)["code"] == 400
    assert c.post("/api/v1/me/watch-events", json=[1, 2], headers=h).json()["code"] == 400
    # video_id 与会话绑定分集不一致
    assert report(env, sid, 1, 10, video="w_ep2")["code"] == 400
    assert report(env, sid, 1, 10)["code"] == 0


# ---------------- 累计与上限 ----------------


def test_normal_reports_accumulate(env):
    sid = start(env)
    for seq, watched in enumerate((10, 20, 30), start=1):
        env.clock.advance(10)
        r = report(env, sid, seq, watched)
        assert r["code"] == 0
        assert r["data"]["accepted_seq"] == seq
        assert r["data"]["credited_delta_seconds"] == 10.0
    assert r["data"]["accepted_watched_seconds"] == 30.0
    assert ue_row(env.alice, env.ep1).watch_ms == 30000
    assert ue_row(env.alice, env.ep1).credited_ms == 30000
    assert user_row(env.alice).watch_ms == 30000
    session = UserWatchSession.get()
    assert session.last_seq == 3 and session.reported_ms == 30000 and session.last_position_ms == 30000


def test_overclaim_is_capped_by_elapsed_time(env):
    sid = start(env)
    env.clock.advance(10)
    r = report(env, sid, 1, 300)
    assert r["code"] == 0
    assert r["data"]["accepted_watched_seconds"] <= 15.0
    assert ue_row(env.alice, env.ep1).watch_ms <= 15000
    # 声称值已记录，后续不能再把超报部分“补”回来
    env.clock.advance(10)
    r = report(env, sid, 2, 310)
    assert r["data"]["credited_delta_seconds"] == 10.0


def test_duplicate_and_stale_seq_are_idempotent(env):
    sid = start(env)
    env.clock.advance(10)
    assert report(env, sid, 1, 10)["data"]["credited_delta_seconds"] == 10.0
    env.clock.advance(10)
    dup = report(env, sid, 1, 20)["data"]
    assert dup == {"accepted_seq": 1, "accepted_watched_seconds": 10.0,
                   "credited_delta_seconds": 0.0, "play_counted": True}
    env.clock.advance(10)
    assert report(env, sid, 2, 30)["data"]["accepted_watched_seconds"] == 30.0
    env.clock.advance(10)
    stale = report(env, sid, 1, 40)["data"]
    assert stale["accepted_seq"] == 2 and stale["credited_delta_seconds"] == 0.0
    assert ue_row(env.alice, env.ep1).watch_ms == 30000


def test_lost_report_is_covered_by_next_cumulative_value(env):
    sid = start(env)
    env.clock.advance(10)
    report(env, sid, 1, 10)
    env.clock.advance(20)  # seq2 丢失
    r = report(env, sid, 3, 30)["data"]
    assert r["accepted_seq"] == 3 and r["accepted_watched_seconds"] == 30.0


def test_reports_within_two_seconds_are_treated_as_duplicates(env):
    sid = start(env)
    env.clock.advance(10)
    report(env, sid, 1, 10)
    env.clock.advance(1)
    r = report(env, sid, 2, 11)["data"]
    assert r["accepted_seq"] == 1 and r["credited_delta_seconds"] == 0.0
    env.clock.advance(9)
    r = report(env, sid, 2, 20)["data"]
    assert r["accepted_seq"] == 2 and r["accepted_watched_seconds"] == 20.0


def test_daily_episode_watch_is_capped_at_duration(env):
    sid = start(env)
    for seq in range(1, 21):  # 循环看 200s，分集时长 120s
        env.clock.advance(10)
        assert report(env, sid, seq, seq * 10)["code"] == 0
    assert ue_row(env.alice, env.ep1).watch_ms == 120000
    # 同日新会话也不再计入
    sid2 = start(env)
    env.clock.advance(10)
    assert report(env, sid2, 1, 10)["data"]["credited_delta_seconds"] == 0.0
    assert ue_row(env.alice, env.ep1).watch_ms == 120000
    assert user_row(env.alice).watch_ms == 120000


def test_unknown_duration_uses_fallback_cap_and_no_credit(env, monkeypatch):
    assert get_settings().watch_unknown_duration_cap_seconds == 1800
    monkeypatch.setattr(get_settings(), "watch_unknown_duration_cap_seconds", 30)
    sid = start(env, video="w_zero")
    for seq in range(1, 6):
        env.clock.advance(10)
        r = report(env, sid, seq, seq * 10, video="w_zero")
        assert r["code"] == 0 and r["data"]["credited_delta_seconds"] == 0.0
    row = ue_row(env.alice, env.ep_zero)
    assert row.watch_ms == 30000 and row.credited_ms == 0
    assert row.play_counted is True  # 阈值 5s 仍按 watch 判定


def test_user_daily_cap(env, monkeypatch):
    monkeypatch.setattr(get_settings(), "watch_user_daily_cap_seconds", 25)
    s1 = start(env, video="w_ep1")
    env.clock.advance(10)
    report(env, s1, 1, 10)
    env.clock.advance(10)
    report(env, s1, 2, 20)
    s2 = start(env, video="w_ep2")
    env.clock.advance(10)
    r = report(env, s2, 1, 10, video="w_ep2")["data"]
    assert r["credited_delta_seconds"] == 5.0
    assert user_row(env.alice).watch_ms == 25000


# ---------------- 播放计数 ----------------


def test_play_count_threshold_dedupe_and_next_day(env):
    sid = start(env)
    env.clock.advance(4)
    r = report(env, sid, 1, 4)["data"]
    assert r["play_counted"] is False
    assert real_counts(env) == (0, 0)
    env.clock.advance(4)
    r = report(env, sid, 2, 8)["data"]
    assert r["play_counted"] is True
    assert real_counts(env) == (1, 1)
    assert user_row(env.alice).play_count == 1
    # 种子假播放量不变
    assert DramaEpisodeStat.get(DramaEpisodeStat.episode == env.ep1.id).play_count == 777
    assert Drama.get_by_id(env.drama.id).play_count == 1000

    # 同日再看（新会话）不再计
    sid2 = start(env)
    env.clock.advance(10)
    assert report(env, sid2, 1, 10)["data"]["play_counted"] is True
    assert real_counts(env) == (1, 1)

    # 次日（UTC）再计 1 次
    env.clock.advance(24 * 3600)
    sid3 = start(env)
    env.clock.advance(6)
    assert report(env, sid3, 1, 6)["data"]["play_counted"] is True
    assert real_counts(env) == (2, 2)
    assert user_row(env.alice, (T0 + timedelta(days=1)).date()).play_count == 1

    # 剧播放量 = 各集播放之和；短集阈值 = min(5s, 时长)
    sid4 = start(env, video="w_short")
    env.clock.advance(3)
    assert report(env, sid4, 1, 3, video="w_short")["data"]["play_counted"] is True
    assert real_counts(env, env.ep_short) == (1, 3)


def test_concurrent_reports_count_play_once(env):
    sids = [start(env), start(env)]
    env.clock.advance(10)
    barrier = threading.Barrier(2)
    results, errors = [], []

    def worker(sid):
        try:
            barrier.wait()
            with env.db.connection_context():
                event = WatchEventIn(session_id=sid, seq=1, video_id="w_ep1",
                                     watched_seconds=6, position_seconds=6)
                results.append(watch_service.report_event("user_alice", event))
        except Exception as exc:  # pragma: no cover - surfaced below
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(s,)) for s in sids]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    assert not errors, errors
    assert len(results) == 2 and all(r["play_counted"] for r in results)
    assert real_counts(env) == (1, 1)
    assert user_row(env.alice).play_count == 1
    assert ue_row(env.alice, env.ep1).watch_ms == 12000


# ---------------- 会话过期 / 并发 / 限流 / 开关 ----------------


def test_session_expires_after_idle_and_max_age(env):
    sid = start(env)
    env.clock.advance(10)
    assert report(env, sid, 1, 10)["code"] == 0
    env.clock.advance(31 * 60)
    assert report(env, sid, 2, 20)["code"] == 410

    sid2 = start(env, video="w_ep2")
    seq = 0
    code = 0
    for _ in range(16):  # 每 25 分钟上报一次，6 小时后过期
        env.clock.advance(25 * 60)
        seq += 1
        code = report(env, sid2, seq, seq * 10, video="w_ep2")["code"]
        if code != 0:
            break
    assert code == 410 and seq == 15


def test_third_concurrent_session_gets_no_credit(env):
    sids = [start(env, video=v) for v in ("w_ep1", "w_ep2", "w_zero")]
    env.clock.advance(10)
    assert report(env, sids[0], 1, 10, video="w_ep1")["data"]["credited_delta_seconds"] == 10.0
    assert report(env, sids[1], 1, 10, video="w_ep2")["data"]["credited_delta_seconds"] == 10.0
    r = report(env, sids[2], 1, 10, video="w_zero")["data"]
    assert r["accepted_watched_seconds"] == 0.0
    assert UserEpisodeWatchDaily.get_or_none(UserEpisodeWatchDaily.episode == env.ep_zero.id).watch_ms == 0


def test_sequential_episode_switch_is_not_concurrency(env):
    # 顺序切集：旧会话在新会话开始前结束，不应被当作并发
    s1 = start(env, video="w_ep1")
    env.clock.advance(10)
    report(env, s1, 1, 10, video="w_ep1")
    s2 = start(env, video="w_ep2")
    env.clock.advance(10)
    report(env, s2, 1, 10, video="w_ep2")
    s3 = start(env, video="w_zero")
    env.clock.advance(10)
    assert report(env, s3, 1, 10, video="w_zero")["data"]["accepted_watched_seconds"] == 10.0


def test_session_create_rate_limit(env, monkeypatch):
    monkeypatch.setattr(get_settings(), "watch_session_create_per_min", 3)
    for _ in range(3):
        start(env)
    assert create(env)["code"] == 429
    assert create(env, user=env.bob)["code"] == 0  # 按用户计
    env.clock.advance(61)
    assert create(env)["code"] == 0


def test_disabled_switch_returns_zero(env, monkeypatch):
    sid = start(env)
    monkeypatch.setattr(get_settings(), "watch_events_enabled", False)
    body = create(env)
    assert body["code"] == 0 and body["data"]["session_id"] == ""
    env.clock.advance(10)
    r = report(env, sid, 1, 10)
    assert r["code"] == 0 and r["data"]["credited_delta_seconds"] == 0.0
    assert UserWatchDaily.select().count() == 0


def test_cleanup_stale_sessions(env):
    old = start(env)
    env.clock.advance(10)
    report(env, old, 1, 10)
    env.clock.advance(31 * 24 * 3600)
    start(env)
    assert watch_service.cleanup_stale_sessions() == 1
    assert UserWatchSession.select().count() == 1
    assert ue_row(env.alice, env.ep1).watch_ms == 10000  # daily 表保留


# ---------------- Profile / 迁移 ----------------


def test_profile_returns_watch_totals(env):
    h = bearer(env.alice)
    data = env.client.get("/api/v1/user/user_alice/profile", headers=h).json()["data"]
    assert data["totalWatchSeconds"] == 0.0 and data["todayWatchSeconds"] == 0.0
    sid = start(env)
    env.clock.advance(10)
    report(env, sid, 1, 10)
    data = env.client.get("/api/v1/user/user_alice/profile", headers=h).json()["data"]
    assert data["totalWatchSeconds"] == 10.0 and data["todayWatchSeconds"] == 10.0
    assert data["watchedCount"] == 0  # 仍为 is_finished 口径
    env.clock.advance(24 * 3600)
    data = env.client.get("/api/v1/user/user_alice/profile", headers=h).json()["data"]
    assert data["totalWatchSeconds"] == 10.0 and data["todayWatchSeconds"] == 0.0
    assert auth_service._format_auth_user(env.alice)["totalWatchSeconds"] == 10.0


def test_real_play_count_exposed_in_episode_list(env):
    sid = start(env)
    env.clock.advance(6)
    report(env, sid, 1, 6)
    items = env.client.get("/api/v1/dramas/drama_w/episodes").json()["data"]["list"]
    first = next(i for i in items if i["videoId"] == "w_ep1")
    assert first["realPlayCount"] == 1


def test_migration_adds_real_play_count_columns(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "db_driver", "sqlite")
    previous = database_proxy.obj
    db = SqliteDatabase(tmp_path / "old_schema.db")
    database_proxy.initialize(db)
    try:
        db.connect()
        db.execute_sql("CREATE TABLE dramas (id INTEGER PRIMARY KEY, play_count INTEGER NOT NULL DEFAULT 0)")
        db.execute_sql("INSERT INTO dramas (id, play_count) VALUES (1, 123456)")
        db.execute_sql("CREATE TABLE drama_episode_stats (episode_id INTEGER PRIMARY KEY, play_count INTEGER NOT NULL DEFAULT 0)")
        db.execute_sql("INSERT INTO drama_episode_stats (episode_id, play_count) VALUES (1, 999)")
        for _ in range(2):  # 幂等
            database_module._migrate_dramas()
            database_module._migrate_drama_episode_stats()
        assert db.execute_sql("SELECT play_count, real_play_count FROM dramas").fetchone() == (123456, 0)
        assert db.execute_sql("SELECT play_count, real_play_count FROM drama_episode_stats").fetchone() == (999, 0)
    finally:
        db.close()
        database_proxy.initialize(previous)


def test_new_tables_have_no_physical_foreign_keys(env):
    for table in ("user_watch_sessions", "user_episode_watch_daily", "user_watch_daily"):
        assert env.db.get_foreign_keys(table) == []