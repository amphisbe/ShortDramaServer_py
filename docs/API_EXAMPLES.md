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
