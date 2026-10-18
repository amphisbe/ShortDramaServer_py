# 短剧服务端 Demo 接口调用示例

作者：**Manus AI**

本文档记录 FastAPI + Peewee Demo 项目的核心接口调用方式，重点覆盖播放数据源接口。项目启动后，所有示例默认以 `http://127.0.0.1:8000` 为服务地址。

## 一、健康检查

```bash
curl http://127.0.0.1:8000/health
```

示例响应如下。

```json
{
  "status": "ok",
  "service": "Short Drama FastAPI Server"
}
```

## 二、播放列表原始兼容格式

该接口返回顶层数组，适合兼容此前上传的 `data.json` 播放接口标准。

```bash
curl "http://127.0.0.1:8000/api/v1/video/play-list/raw?viewer_user_id=666dd802f366f40a8b9a4aa1&page=1&page_size=10"
```

核心字段包括 `userId`、`avatar`、`nickname`、`videoId`、`playurl`、`poster`、`vdtitle`、`likeSum`、`commemtSum`、`shareSum`、`isfollow`、`isLiked`、`position`、`lookAllBtnText`、`bottomAreaBtnText` 和 `toolInfo`。

## 三、播放列表统一包装格式

该接口更适合正式服务端使用，返回 `code`、`message` 和 `data` 包装结构。

```bash
curl "http://127.0.0.1:8000/api/v1/video/play-list?page=1&page_size=2"
```

示例响应结构如下。

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "list": [],
    "page": 1,
    "pageSize": 2,
    "hasMore": true
  }
}
```

## 四、Demo 短剧管理列表

该接口用于验证短剧主数据管理链路。正式项目应增加管理员登录、RBAC 权限、操作审计、分页筛选和状态管理。

```bash
curl http://127.0.0.1:8000/api/v1/admin/dramas
```

## 五、本地冒烟测试

```bash
cd /home/ubuntu/short_drama_fastapi_server
PYTHONPATH=. python3.11 scripts/smoke_test.py
```

若输出 `Smoke tests passed.`，说明基础服务、数据库初始化与核心 API 均正常。

## 六、真实观看时长统计（需 Bearer JWT，用户只取自令牌）

设计见 `docs/watch-time-statistics-design.md`。错误沿用 HTTP 200 + 信封业务码：400 参数错误、401 未登录、403 会话签名/归属不符、404 分集不存在、410 会话过期、429 会话创建过频。

### 1. 创建观看会话 `POST /api/v1/me/watch-sessions`

```bash
curl -X POST http://127.0.0.1:8000/api/v1/me/watch-sessions \
  -H "Authorization: Bearer <JWT>" -H "Content-Type: application/json" \
  -d '{"video_id": "video_001"}'
```

```json
{ "code": 0, "message": "success", "data": { "session_id": "ws1.<payload>.<sig>", "expires_in": 1800 } }
```

### 2. 上报观看累计值 `POST /api/v1/me/watch-events`

客户端每 10s 及暂停/后台/结束/切集时上报**会话内累计**观看秒数，`seq` 每次 +1；重复或乱序的旧 `seq` 增量为 0。

```bash
curl -X POST http://127.0.0.1:8000/api/v1/me/watch-events \
  -H "Authorization: Bearer <JWT>" -H "Content-Type: application/json" \
  -d '{"session_id": "ws1...", "seq": 3, "video_id": "video_001", "watched_seconds": 25.0, "position_seconds": 48.5, "is_finished": false}'
```

```json
{ "code": 0, "message": "success",
  "data": { "accepted_seq": 3, "accepted_watched_seconds": 24.8, "credited_delta_seconds": 9.9, "play_counted": true } }
```

`play_counted` 表示该用户·分集·UTC 日是否已计过播放（累计观看 ≥ min(5s, 分集时长) 时计 1 次，只递增 `real_play_count`，种子 `play_count` 不变）。Profile（`/api/v1/user/{user_id}/profile` 与登录返回的 user）新增 `totalWatchSeconds`、`todayWatchSeconds`；剧/剧集列表项新增 `realPlayCount`。
