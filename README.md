# 短剧服务端 Demo：FastAPI + Peewee

作者：**Manus AI**

本项目是一个基于 **Python FastAPI** 与 **Peewee ORM** 的短剧服务端 Demo，用于验证短剧播放数据源服务的基础架构。项目当前以此前记录的 `data.json` 播放接口为标准，重点实现了短剧播放列表、短剧主数据管理列表、Peewee 数据模型、数据库初始化和 Demo 种子数据。

> **定位说明**：该项目不是完整生产系统，而是用于后续正式服务端开发的 Python Demo 底座。它保留了向 MySQL 切换的能力，同时默认使用 SQLite，便于在无 MySQL 环境下快速启动和验证接口。

## 一、技术栈与设计原则

FastAPI 用于提供 HTTP API 服务，Peewee 用于数据库建模与读写，PyMySQL 用于连接 MySQL。Peewee 官方支持 SQLite、MySQL、PostgreSQL 等数据库后端，FastAPI 则天然提供 OpenAPI 文档能力，因此本 Demo 适合快速搭建可测试、可扩展的短剧服务端原型。[1] [2]

| 模块 | 当前选型 | 说明 |
|---|---|---|
| Web 框架 | FastAPI | 提供 REST API、自动 OpenAPI 文档和类型友好的接口开发方式。 |
| ORM | Peewee | 轻量级 ORM，适合 Demo、小型服务和清晰的数据模型定义。 |
| Demo 数据库 | SQLite | 默认配置，便于一键运行。 |
| 生产数据库 | MySQL | 通过 `.env` 设置 `DB_DRIVER=mysql` 后切换。 |
| 初始化方式 | `initialize_runtime()` | 统一完成日志、数据库代理、连接、建表和可选种子数据初始化。 |

## 二、目录结构

```text
short_drama_fastapi_server/
├── app/
│   ├── api/
│   │   └── video.py                 # 播放接口与 Demo 管理接口
│   ├── core/
│   │   ├── config.py                # 环境变量配置
│   │   └── logging.py               # 日志初始化
│   ├── db/
│   │   ├── database.py              # Peewee 数据库连接与一键初始化
│   │   └── seed.py                  # Demo 种子数据
│   ├── models/
│   │   └── drama.py                 # 用户、短剧、分集、统计、互动模型
│   ├── services/
│   │   └── play_service.py          # 播放接口业务组装逻辑
│   └── main.py                      # FastAPI 应用入口
├── scripts/
│   ├── init_db.py                   # 一键建表与初始化 Demo 数据
│   └── smoke_test.py                # 冒烟测试脚本
├── .env.example                     # 环境变量样例
├── requirements.txt                 # Python 依赖
└── README.md
```

## 三、快速启动

请在项目目录中执行以下命令。Demo 默认使用 SQLite，因此无需提前安装 MySQL。

```bash
cd /home/ubuntu/short_drama_fastapi_server
cp .env.example .env
sudo pip3 install -r requirements.txt
PYTHONPATH=. python3.11 scripts/init_db.py
PYTHONPATH=. uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

启动后可访问以下地址。

| 地址 | 用途 |
|---|---|
| `http://127.0.0.1:8000/health` | 健康检查。 |
| `http://127.0.0.1:8000/docs` | FastAPI 自动生成的 Swagger API 文档。 |
| `http://127.0.0.1:8000/api/v1/video/play-list/raw` | 与原始 `data.json` 兼容的播放列表数组格式。 |
| `http://127.0.0.1:8000/api/v1/video/play-list` | 推荐给正式服务端使用的统一响应包装格式。 |
| `http://127.0.0.1:8000/api/v1/admin/dramas` | Demo 短剧管理列表接口。 |

## 四、接口说明

`/api/v1/video/play-list/raw` 会直接返回顶层数组，适合兼容已有前端播放组件。字段命名沿用 `data.json`，例如 `userId`、`avatar`、`nickname`、`videoId`、`playurl`、`poster`、`vdtitle`、`likeSum`、`commemtSum`、`shareSum`、`toolInfo` 等。

| 接口 | 方法 | 说明 |
|---|---:|---|
| `/health` | GET | 服务健康检查。 |
| `/api/v1/video/play-list/raw` | GET | 返回原始数组格式，便于兼容既有播放接口。 |
| `/api/v1/video/play-list` | GET | 返回 `{code,message,data}` 包装结构，更适合正式 API。 |
| `/api/v1/admin/dramas` | GET | 返回短剧主数据列表，作为后台管理 Demo。 |

播放列表接口支持以下查询参数。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---:|---:|---|
| `viewer_user_id` | string | 否 | 空 | 当前观看用户的外部 ID，用于计算是否关注、是否点赞和播放进度。 |
| `drama_id` | integer | 否 | 空 | 短剧内部 ID，用于筛选指定短剧。 |
| `page` | integer | 否 | `1` | 页码。 |
| `page_size` | integer | 否 | `20` | 每页数量，最大 `100`。 |

## 五、数据库模型

当前 Demo 建立了短剧播放接口所需的核心表。用户、短剧、分集和分集统计是播放数据源的主链路，关注、点赞、收藏和播放进度用于计算当前用户视角下的状态字段。

| 表名 | 模型 | 业务含义 |
|---|---|---|
| `users` | `User` | 用户、作者、观众基础信息。 |
| `dramas` | `Drama` | 短剧主数据，如标题、作者、总集数、封面和 VIP 状态。 |
| `drama_episodes` | `DramaEpisode` | 短剧分集数据，如播放地址、海报、标题和排序。 |
| `drama_episode_stats` | `DramaEpisodeStat` | 分集点赞、评论、分享、播放、收藏等计数。 |
| `user_follows` | `UserFollow` | 用户关注关系。 |
| `users_episode_likes` | `UserEpisodeLike` | 用户对分集的点赞关系。 |
| `users_drama_favorites` | `UserDramaFavorite` | 用户追剧、收藏关系。 |
| `users_episode_progress` | `UserEpisodeProgress` | 用户播放进度。 |
| `episode_comments` | `EpisodeComment` | 分集评论。 |
| `episode_shares` | `EpisodeShare` | 分集分享记录。 |

## 六、切换到 MySQL

将 `.env` 修改为以下配置后，项目会使用 Peewee 的 `PooledMySQLDatabase` 连接 MySQL。

```env
DB_DRIVER=mysql
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=short_drama
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_CHARSET=utf8mb4
```

修改后执行初始化命令即可创建表结构并写入 Demo 数据。

```bash
PYTHONPATH=. python3.11 scripts/init_db.py
```

## 七、测试结果

已在本地执行 `scripts/smoke_test.py`，验证通过的接口包括健康检查、原始播放列表、统一播放列表和 Demo 管理列表。当前结果为：`Smoke tests passed.`

```bash
PYTHONPATH=. python3.11 scripts/smoke_test.py
```

## 八、后续开发建议

正式进入短剧服务端开发时，建议在该 Demo 基础上补充管理员认证、用户登录态、RBAC 权限、操作审计、内容审核、分页筛选、推荐位管理、播放统计异步写入、CDN 播放地址签名和数据库迁移机制。管理后台可以继续结合前面评估过的 MineAdmin，而本项目更适合作为短剧数据源 API 服务的 Python 原型或服务端验证工程。

## References

[1]: https://fastapi.tiangolo.com/ "FastAPI Documentation"
[2]: https://docs.peewee-orm.com/ "Peewee ORM Documentation"
