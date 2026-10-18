# 修改记录：客户端与服务端接口对齐（2026-10-18）

依据：客户端（`ShortDrama_03`）与服务端（`ShortDramaServer_py`）接口一致性审计。
改动已应用到本地工作目录，尚未提交 git，也未同步到远程服务器（`/root/workspace/ShortDramaServer`）。

## 第一批：小改动（已应用）

### 服务端（1 个文件）

| 文件 | 改动 |
|---|---|
| `app/services/drama_service.py` | 新增 `_resolve_subtitle_url`：字幕地址不再走 demo 模式随机挑选视频地址的逻辑；为空时返回 `""`，`http(s)://` / `//` 开头原样返回，相对路径前拼 `STATIC_HOST`；`subtitleEnabled` 按地址是否非空判断 |

### 客户端（6 个文件）

| 文件 | 改动 |
|---|---|
| `pages/detail/index.uvue` | 删除写死的 `option = {dramaId: "drama_002"}`，改用页面真实参数 |
| `api/authService.uts` | 删除导入不存在的 `SHORTDRAMA_BASE`（编译风险） |
| `pages/home/index.uvue` | 删除导入不存在的 `login`，只保留 `requireGoogleLogin` |
| `api/dramaService.uts` | `parseDramaItem` 读取服务端 `description`，不再强制为空；`getFeaturedDrama` 在 `data:null` 时回调 null |
| `pages/index/index.uvue` | 进度改为按秒上报（毫秒 / 1000）；恢复同一视频 5 秒节流，播完必报；加载剧集时把服务端秒级 `position` / `duration` 换算成毫秒交给播放器（Android 播放器内部用毫秒） |
| `api/baseService.uts` | `http()`：请求地址以 `BASE` 开头且响应 `code != 0` 时返回 `ok:false`（Reward 后端不受影响） |

## 第二批 A：点赞收藏幂等、JWT 鉴权、剧集个性化（已应用）

### 服务端（10 个文件）

| 文件 | 改动 |
|---|---|
| `app/core/security.py`（新增） | `decode_user_id`（HS256 + `JWT_SECRET`，要求 `exp`、`sub`）、`get_optional_user`、`get_current_user`（401）、`require_path_user`（路径 user_id 与 token 不一致 403）、`require_admin`（`X-Admin-Token`，`ADMIN_TOKEN` 为空时 403） |
| `app/main.py` | 注册 `ApiAuthError` 处理器，鉴权失败返回 HTTP 200 + `{code:401/403, message, data:null}` |
| `app/api/user.py` | 所有 `/api/v1/user/{user_id}/*` 挂鉴权；`is_like` / `is_favorite` 改为可选 `bool`，传值即按目标状态设置，不传保持切换 |
| `app/api/video.py` | `/api/v1/admin/*` 挂 `require_admin` |
| `app/api/drama.py` | `/dramas/{id}/episodes` 未传 `viewer_user_id` 时取 Bearer token 用户，token 无效按匿名处理 |
| `app/services/user_service.py` | `toggle_like` / `toggle_favorite` 新增 `desired` 参数，幂等设置，计数最低为 0 |
| `app/services/drama_service.py` | 剧集返回 `isFavorite`；`_apply_tool_state` 按状态下发 `dianzan_h` / `shoucang_h` 选中图标 |
| `app/core/config.py` | 新增 `ADMIN_TOKEN` |
| `README.md` | 新增“鉴权”一节 |
| `tests/test_auth_guard.py`（新增） | 7 个用例：401/403、幂等点赞收藏、剧集个性化、管理接口 |

### 客户端（4 个文件）

| 文件 | 改动 |
|---|---|
| `api/baseService.uts` | 新增存储键 `serverAuthToken`、`serverUserId` |
| `api/authService.uts` | 新增 `getServerAuthToken` / `getServerUserId` / `getServerAuthHeader`；`verifyIdToken` 成功时单独保存服务端 token，`googleLogout` 时清除 |
| `api/dramaService.uts` | 剧集、profile、history、favorites 及进度/点赞/收藏/分享请求改带服务端 token；点赞收藏传目标状态，回调 `(ok, 状态, 计数)` |
| `pages/index/index.uvue` | 用户 ID 改用 `getServerUserId()`（替换写死的 `user_xuanyi`），未登录时跳过写请求；点赞收藏用返回结果回写 `isLiked` / `likeSum` / `toolInfo`；修复已点赞时取消点赞不发请求的问题 |

## 部署需要的配置（`.env`）

- `JWT_SECRET`：至少 32 字节随机串（默认 `change-me-in-production` 不安全）
- `GOOGLE_WEB_CLIENT_ID`：与客户端 `api/baseService.uts` 中的 Web Client ID 一致
- `ADMIN_TOKEN`：可选，不配置则 `/admin/*` 全部禁用
- `requirements.txt` 建议补充 `requests`（google-auth 依赖）

## 本地验证（2026-10-18 13:00 左右）

本地 `run.py` 启动于 9011 端口（MySQL `127.0.0.1:31306/drama`），只读接口与鉴权冒烟测试 21 项中 20 项通过，未通过项为测试账号不存在导致的 404（符合预期）。写接口（进度、点赞、收藏、分享）尚未在该库上测试。

数据问题（非代码）：示例剧 `description` 为空，剧集 `duration` 为 0，`poster` 为空。

## 待办

- 第二批 B：统一用户身份（App 启动时 Reward 登录不再覆盖服务端登录态；未登录用户处理方式待定）
- 第三批：封面 URL / 静态目录、字段命名统一、分类与分页、`video_id` 含义统一
- 第四批：清理 `print` 中的个人信息、统一端口、删除无用测试数据、补全接口文档；编写 Reward 后端职责说明

## Google 登录插件升级（Credential Manager，已应用，14:55）

### 客户端（8 个文件）

| 文件 | 改动 |
|---|---|
| `uni_modules/dc-google-signin/utssdk/app-android/GoogleCredentialHelper.kt`（新增） | 基于 Credential Manager 的登录：silent / auto / button 三种模式，直接回调，防并发，可传 nonce，登出清除凭据 |
| `uni_modules/dc-google-signin/utssdk/app-android/GoogleSignInActivity.kt`（删除） | 旧 Identity.getSignInClient 实现，备份在 `D:\wangs\sdpatch\backup-gsignin` |
| `uni_modules/dc-google-signin/utssdk/app-android/index.uts` | 重写，返回 idToken / email / displayName / givenName / familyName / photoUrl / phoneNumber 及错误码 0-10 |
| `uni_modules/dc-google-signin/utssdk/interface.uts`（新增） | 类型定义 |
| `uni_modules/dc-google-signin/utssdk/app-android/config.json` | 依赖 credentials 1.6.0、credentials-play-services-auth 1.6.0、googleid 1.2.1，minSdk 24 |
| `uni_modules/dc-google-signin/utssdk/app-android/AndroidManifest.xml` | 移除旧 Activity 声明 |
| `uni_modules/dc-google-signin/package.json` | 描述与版本 |
| `api/authService.uts` | 资料以服务端为准、插件值补空；按错误码提示；不再打印 idToken；登出清除凭据 |

### 服务端（4 个文件）

| 文件 | 改动 |
|---|---|
| `app/services/auth_service.py` | 空资料不覆盖已有值；响应增加 `emailVerified`；签发方错误 401、证书获取失败 500；30 秒时钟偏差 |
| `requirements.txt` | 补充 `requests` |
| `test_auth_google.py` | 期望值增加 `emailVerified` |
| `tests/test_google_auth.py`（新增） | 4 个用例 |

验证：服务端测试 13 个全部通过；本地冒烟 21 项通过 20 项（未通过项为测试账号不存在，符合预期）。客户端需重新打自定义基座并在真机验证；需要 HBuilderX 4.81+（旧版本改用 credentials 1.5.0 + googleid 1.1.1）；离线原生工程需手动同步依赖。