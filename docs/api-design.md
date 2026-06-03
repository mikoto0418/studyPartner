# API 接口设计文档

> AI 伴学与智能体协同平台 — RESTful API 设计规范

版本：V1.0
更新日期：2026-06-02
基础路径：`/api/v1`

---

## 目录

- [一、通用约定](#一通用约定)
  - [1.1 通用响应格式](#11-通用响应格式)
  - [1.2 分页约定](#12-分页约定)
  - [1.3 认证方式](#13-认证方式)
  - [1.4 错误码定义](#14-错误码定义)
  - [1.5 SSE 流式接口规范](#15-sse-流式接口规范)
  - [1.6 文件上传规范](#16-文件上传规范)
  - [1.7 WebSocket 接口规范](#17-websocket-接口规范)
  - [1.8 通用请求头](#18-通用请求头)
  - [1.9 时间格式约定](#19-时间格式约定)
- [二、认证模块 /api/v1/auth](#二认证模块)
- [三、用户管理 /api/v1/users](#三用户管理)
- [四、学生档案 /api/v1/students](#四学生档案)
- [五、仪表盘 /api/v1/dashboard](#五仪表盘)
- [六、TODO /api/v1/todos](#六todo)
- [七、便签 /api/v1/notes](#七便签)
- [八、倒数日 /api/v1/countdowns](#八倒数日)
- [九、书签 /api/v1/bookmarks](#九书签)
- [十、公告 /api/v1/announcements](#十公告)
- [十一、任务 /api/v1/tasks](#十一任务)
- [十二、日历计划 /api/v1/calendar](#十二日历计划)
- [十三、学习时长 /api/v1/study-time](#十三学习时长)
- [十四、行为日志 /api/v1/behavior-logs](#十四行为日志)
- [十五、学习热力图 /api/v1/heatmap](#十五学习热力图)
- [十六、B站资源 /api/v1/bilibili](#十六b站资源)
- [十七、文件上传 /api/v1/files](#十七文件上传)
- [十八、知识库 /api/v1/knowledge](#十八知识库)
- [十九、AI 对话 /api/v1/ai/chat](#十九ai-对话)
- [二十、Memory /api/v1/ai/memory](#二十memory)
- [二十一、每日复盘 /api/v1/reviews](#二十一每日复盘)
- [二十二、通知 /api/v1/notifications](#二十二通知)
- [二十三、模型配置 /api/v1/admin/llm-configs](#二十三模型配置)
- [二十四、系统管理 /api/v1/admin/system](#二十四系统管理)
- [二十五、数据统计 /api/v1/stats](#二十五数据统计)

---

## 一、通用约定

### 1.1 通用响应格式

所有接口统一返回以下 JSON 结构：

```json
{
  "code": 0,
  "message": "success",
  "data": { ... }
}
```

| 字段      | 类型              | 说明                                       |
| --------- | ----------------- | ------------------------------------------ |
| `code`    | `integer`         | 业务状态码，`0` 表示成功，非 `0` 表示异常  |
| `message` | `string`          | 状态描述信息                               |
| `data`    | `object` / `null` | 业务数据，无数据时为 `null`                |

**成功示例：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "abc123",
    "name": "张三"
  }
}
```

**错误示例：**

```json
{
  "code": 40100,
  "message": "登录已过期，请重新登录",
  "data": null
}
```

### 1.2 分页约定

分页请求统一使用 Query 参数：

| 参数        | 类型      | 默认值 | 说明                    |
| ----------- | --------- | ------ | ----------------------- |
| `page`      | `integer` | `1`    | 当前页码，从 1 开始     |
| `page_size` | `integer` | `20`   | 每页条数，最大值 `100`  |

分页响应统一格式：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [ ... ],
    "total": 150,
    "page": 1,
    "page_size": 20,
    "total_pages": 8
  }
}
```

| 字段          | 类型      | 说明           |
| ------------- | --------- | -------------- |
| `items`       | `array`   | 数据列表       |
| `total`       | `integer` | 总记录数       |
| `page`        | `integer` | 当前页码       |
| `page_size`   | `integer` | 每页条数       |
| `total_pages` | `integer` | 总页数         |

### 1.3 认证方式

- 认证方式：**Bearer Token**（JWT）
- Token 通过登录接口获取，在 `Authorization` 请求头中携带
- Token 由 `access_token`（短期）和 `refresh_token`（长期）组成

```
Authorization: Bearer <access_token>
```

- `access_token` 有效期：**2 小时**
- `refresh_token` 有效期：**7 天**
- 公开接口（如登录）无需携带 Token，文档中会标注 **无需认证**

### 1.4 错误码定义

#### HTTP 状态码

| HTTP 状态码 | 说明                         |
| ----------- | ---------------------------- |
| `200`       | 请求成功                     |
| `201`       | 资源创建成功                 |
| `204`       | 操作成功，无返回内容         |
| `400`       | 请求参数错误                 |
| `401`       | 未认证或 Token 过期          |
| `403`       | 无权限访问                   |
| `404`       | 资源不存在                   |
| `409`       | 资源冲突（如用户名已存在）   |
| `413`       | 上传文件过大                 |
| `422`       | 请求参数校验失败             |
| `429`       | 请求过于频繁                 |
| `500`       | 服务器内部错误               |

#### 业务错误码

| 错误码    | 说明                           | 所属模块      |
| --------- | ------------------------------ | ------------- |
| `0`       | 成功                           | 全局          |
| `40000`   | 请求参数错误                   | 全局          |
| `40001`   | 参数校验失败                   | 全局          |
| `40100`   | 未认证，请先登录               | 认证          |
| `40101`   | Token 已过期                   | 认证          |
| `40102`   | Token 无效                     | 认证          |
| `40103`   | Refresh Token 已过期           | 认证          |
| `40104`   | 用户名或密码错误               | 认证          |
| `40105`   | 账号已被禁用                   | 认证          |
| `40106`   | 原密码错误                     | 认证          |
| `40300`   | 无权限访问该资源               | 权限          |
| `40301`   | 无权限操作其他用户数据         | 权限          |
| `40302`   | 角色权限不足                   | 权限          |
| `40400`   | 资源不存在                     | 全局          |
| `40401`   | 用户不存在                     | 用户          |
| `40402`   | TODO 不存在                    | TODO          |
| `40403`   | 便签不存在                     | 便签          |
| `40404`   | 倒数日不存在                   | 倒数日        |
| `40405`   | 书签不存在                     | 书签          |
| `40406`   | 公告不存在                     | 公告          |
| `40407`   | 任务不存在                     | 任务          |
| `40408`   | 日历事件不存在                 | 日历          |
| `40409`   | 文件不存在                     | 文件          |
| `40410`   | 知识库文档不存在               | 知识库        |
| `40411`   | 对话不存在                     | AI 对话       |
| `40412`   | B站资源不存在                  | B站           |
| `40413`   | 通知不存在                     | 通知          |
| `40414`   | 模型配置不存在                 | 模型配置      |
| `40415`   | 复盘记录不存在                 | 复盘          |
| `40900`   | 资源冲突                       | 全局          |
| `40901`   | 用户名已存在                   | 用户          |
| `40902`   | 邮箱已存在                     | 用户          |
| `41300`   | 上传文件过大                   | 文件          |
| `41301`   | 文件类型不支持                 | 文件          |
| `42200`   | 请求体校验失败                 | 全局          |
| `42900`   | 请求过于频繁，请稍后再试       | 全局          |
| `42901`   | AI 调用频率超限                | AI            |
| `42902`   | AI 每日额度已用完              | AI            |
| `50000`   | 服务器内部错误                 | 全局          |
| `50001`   | 数据库操作失败                 | 全局          |
| `50002`   | AI 模型调用失败                | AI            |
| `50003`   | 文件存储服务异常               | 文件          |
| `50004`   | 向量数据库异常                 | 知识库        |
| `50005`   | 定时任务执行失败               | 系统          |

### 1.5 SSE 流式接口规范

AI 对话采用 **Server-Sent Events (SSE)** 实现流式输出。

**请求方式：** `POST`（请求体包含消息内容，响应为 SSE 流）

**请求头：**

```
Content-Type: application/json
Authorization: Bearer <access_token>
Accept: text/event-stream
```

**SSE 事件格式：**

```
event: message
data: {"type": "content", "content": "你", "conversation_id": "xxx"}

event: message
data: {"type": "content", "content": "好", "conversation_id": "xxx"}

event: message
data: {"type": "content", "content": "！", "conversation_id": "xxx"}

event: message
data: {"type": "done", "content": "", "usage": {"prompt_tokens": 120, "completion_tokens": 45, "total_tokens": 165}}

```

**SSE data 字段说明：**

| 字段              | 类型     | 说明                                     |
| ----------------- | -------- | ---------------------------------------- |
| `type`            | `string` | 事件类型：`content` / `thinking` / `done` / `error` |
| `content`         | `string` | 内容片段                                 |
| `conversation_id` | `string` | 对话 ID                                  |
| `message_id`      | `string` | 消息 ID（在 `done` 事件中返回）          |
| `usage`           | `object` | Token 使用统计（仅在 `done` 事件中）     |
| `error`           | `string` | 错误信息（仅在 `error` 事件中）          |

**错误处理：**

```
event: message
data: {"type": "error", "error": "AI 模型调用失败，请稍后重试", "code": 50002}

```

**前端实现建议：** 使用 `fetch` + `ReadableStream` 或 `@microsoft/fetch-event-source` 库。

### 1.6 文件上传规范

- 请求头：`Content-Type: multipart/form-data`
- 单文件最大：**50MB**（可通过系统设置调整）
- 支持文件类型（MVP）：`.pdf`、`.doc`、`.docx`、`.md`、`.txt`
- 图片类型：`.jpg`、`.jpeg`、`.png`、`.gif`、`.webp`
- 文件名长度上限：**255 字符**
- 上传进度通过前端 `XMLHttpRequest` 或 `axios` 的 `onUploadProgress` 实现

**上传请求示例：**

```
POST /api/v1/files/upload
Content-Type: multipart/form-data
Authorization: Bearer <access_token>

------boundary
Content-Disposition: form-data; name="file"; filename="论文.pdf"
Content-Type: application/pdf

<文件二进制内容>
------boundary
Content-Disposition: form-data; name="category"

学习资料
------boundary--
```

### 1.7 WebSocket 接口规范

WebSocket 用于实时通知推送。

**连接地址：**

```
ws(s)://<domain>/api/v1/ws/notifications?token=<access_token>
```

**连接认证：** 通过 Query 参数传递 `token` 或在连接建立后发送认证消息。

**服务端推送消息格式：**

```json
{
  "type": "notification",
  "data": {
    "id": "notif_001",
    "title": "新任务通知",
    "content": "老师发布了新任务：完成论文阅读",
    "category": "task",
    "created_at": "2026-06-02T10:30:00+08:00",
    "is_read": false
  }
}
```

**心跳机制：**

```json
// 客户端发送
{"type": "ping"}

// 服务端响应
{"type": "pong"}
```

**心跳间隔：** 30 秒

**断线重连：** 客户端应实现指数退避重连策略（初始 1s，最大 30s）。

**WebSocket 消息类型：**

| type                | 说明                    |
| ------------------- | ----------------------- |
| `notification`      | 新通知推送              |
| `task_update`       | 任务状态更新            |
| `announcement_new`  | 新公告发布              |
| `review_ready`      | 每日复盘已生成          |
| `file_processed`    | 知识库文件处理完成      |
| `ping` / `pong`     | 心跳                    |

### 1.8 通用请求头

| 请求头           | 值                              | 说明               |
| ---------------- | ------------------------------- | ------------------ |
| `Authorization`  | `Bearer <access_token>`         | 认证令牌           |
| `Content-Type`   | `application/json`              | 请求体格式         |
| `Accept`         | `application/json`              | 期望响应格式       |
| `Accept-Language`| `zh-CN`                         | 语言偏好           |
| `X-Request-ID`   | `<uuid>`                        | 请求追踪 ID（可选）|

### 1.9 时间格式约定

- 所有时间字段使用 **ISO 8601** 格式：`2026-06-02T10:30:00+08:00`
- 日期字段使用：`2026-06-02`
- 服务端统一使用 **UTC** 存储，响应中返回带时区偏移的时间
- 前端按用户本地时区展示

---

## 二、认证模块

> 基础路径：`/api/v1/auth`

### 2.1 用户登录

| 项目     | 说明                              |
| -------- | --------------------------------- |
| 接口     | `POST /api/v1/auth/login`         |
| 描述     | 用户通过用户名和密码登录系统      |
| 权限     | **无需认证**                      |

**请求体：**

```json
{
  "username": "string, 必填, 用户名",
  "password": "string, 必填, 密码"
}
```

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "登录成功",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "Bearer",
    "expires_in": 7200,
    "user": {
      "id": "u_001",
      "username": "zhangsan",
      "display_name": "张三",
      "role": "student",
      "avatar_url": "/files/avatars/u_001.jpg",
      "email": "zhangsan@example.com"
    }
  }
}
```

**错误响应：**

| HTTP 状态码 | 业务错误码 | 说明               |
| ----------- | ---------- | ------------------ |
| `401`       | `40104`    | 用户名或密码错误   |
| `403`       | `40105`    | 账号已被禁用       |

---

### 2.2 用户退出

| 项目     | 说明                              |
| -------- | --------------------------------- |
| 接口     | `POST /api/v1/auth/logout`        |
| 描述     | 退出登录，服务端将 Token 加入黑名单 |
| 权限     | 所有已登录用户                    |

**请求头：** `Authorization: Bearer <access_token>`

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "退出成功",
  "data": null
}
```

---

### 2.3 刷新 Token

| 项目     | 说明                                  |
| -------- | ------------------------------------- |
| 接口     | `POST /api/v1/auth/refresh`           |
| 描述     | 使用 refresh_token 获取新的 access_token |
| 权限     | **无需 access_token**                 |

**请求体：**

```json
{
  "refresh_token": "string, 必填, 刷新令牌"
}
```

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "刷新成功",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "Bearer",
    "expires_in": 7200
  }
}
```

**错误响应：**

| HTTP 状态码 | 业务错误码 | 说明                   |
| ----------- | ---------- | ---------------------- |
| `401`       | `40103`    | Refresh Token 已过期   |
| `401`       | `40102`    | Token 无效             |

---

### 2.4 修改密码

| 项目     | 说明                                  |
| -------- | ------------------------------------- |
| 接口     | `PUT /api/v1/auth/password`           |
| 描述     | 当前用户修改自己的密码                |
| 权限     | 所有已登录用户                        |

**请求体：**

```json
{
  "old_password": "string, 必填, 原密码",
  "new_password": "string, 必填, 新密码（至少8位，含字母和数字）"
}
```

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "密码修改成功，请重新登录",
  "data": null
}
```

**错误响应：**

| HTTP 状态码 | 业务错误码 | 说明         |
| ----------- | ---------- | ------------ |
| `400`       | `40106`    | 原密码错误   |
| `422`       | `42200`    | 新密码不符合规则 |

---

### 2.5 获取当前用户信息

| 项目     | 说明                              |
| -------- | --------------------------------- |
| 接口     | `GET /api/v1/auth/me`             |
| 描述     | 获取当前登录用户的详细信息        |
| 权限     | 所有已登录用户                    |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "u_001",
    "username": "zhangsan",
    "display_name": "张三",
    "role": "student",
    "email": "zhangsan@example.com",
    "avatar_url": "/files/avatars/u_001.jpg",
    "phone": "13800138000",
    "is_active": true,
    "last_login_at": "2026-06-02T09:00:00+08:00",
    "created_at": "2026-01-15T10:00:00+08:00"
  }
}
```

---

## 三、用户管理

> 基础路径：`/api/v1/users`

### 3.1 创建用户

| 项目     | 说明                            |
| -------- | ------------------------------- |
| 接口     | `POST /api/v1/users`            |
| 描述     | 管理员创建新用户（学生或老师）  |
| 权限     | **Admin**                       |

**请求体：**

```json
{
  "username": "string, 必填, 用户名（唯一）",
  "password": "string, 必填, 初始密码",
  "display_name": "string, 必填, 显示名称",
  "role": "string, 必填, 角色: student | teacher | admin",
  "email": "string, 选填, 邮箱",
  "phone": "string, 选填, 手机号",
  "student_id": "string, 选填, 学号（学生角色时）",
  "department": "string, 选填, 院系/部门",
  "grade": "string, 选填, 年级（学生角色时）",
  "research_direction": "string, 选填, 研究方向（学生角色时）"
}
```

**成功响应 (201)：**

```json
{
  "code": 0,
  "message": "用户创建成功",
  "data": {
    "id": "u_002",
    "username": "lisi",
    "display_name": "李四",
    "role": "student",
    "email": "lisi@example.com",
    "is_active": true,
    "created_at": "2026-06-02T10:00:00+08:00"
  }
}
```

**错误响应：**

| HTTP 状态码 | 业务错误码 | 说明             |
| ----------- | ---------- | ---------------- |
| `409`       | `40901`    | 用户名已存在     |
| `409`       | `40902`    | 邮箱已存在       |
| `403`       | `40302`    | 角色权限不足     |

---

### 3.2 获取用户列表

| 项目     | 说明                              |
| -------- | --------------------------------- |
| 接口     | `GET /api/v1/users`               |
| 描述     | 获取用户列表，支持按角色过滤      |
| 权限     | **Admin**：全部；**Teacher**：关联学生 |

**Query 参数：**

| 参数        | 类型      | 必填 | 说明                                    |
| ----------- | --------- | ---- | --------------------------------------- |
| `page`      | `integer` | 否   | 页码，默认 1                            |
| `page_size` | `integer` | 否   | 每页条数，默认 20                       |
| `role`      | `string`  | 否   | 角色过滤：`student` / `teacher` / `admin` |
| `keyword`   | `string`  | 否   | 搜索关键词（匹配用户名、显示名称）      |
| `is_active` | `boolean` | 否   | 账号状态过滤                            |
| `sort_by`   | `string`  | 否   | 排序字段：`created_at` / `display_name` |
| `sort_order`| `string`  | 否   | 排序方向：`asc` / `desc`，默认 `desc`  |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "u_001",
        "username": "zhangsan",
        "display_name": "张三",
        "role": "student",
        "email": "zhangsan@example.com",
        "is_active": true,
        "last_login_at": "2026-06-02T09:00:00+08:00",
        "created_at": "2026-01-15T10:00:00+08:00"
      }
    ],
    "total": 50,
    "page": 1,
    "page_size": 20,
    "total_pages": 3
  }
}
```

---

### 3.3 获取用户详情

| 项目     | 说明                            |
| -------- | ------------------------------- |
| 接口     | `GET /api/v1/users/{user_id}`   |
| 描述     | 获取指定用户详细信息            |
| 权限     | **Admin**；**Teacher**（关联学生）；用户本人 |

**路径参数：**

| 参数      | 类型     | 说明     |
| --------- | -------- | -------- |
| `user_id` | `string` | 用户 ID  |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "u_001",
    "username": "zhangsan",
    "display_name": "张三",
    "role": "student",
    "email": "zhangsan@example.com",
    "phone": "13800138000",
    "avatar_url": "/files/avatars/u_001.jpg",
    "is_active": true,
    "department": "计算机科学与技术",
    "last_login_at": "2026-06-02T09:00:00+08:00",
    "created_at": "2026-01-15T10:00:00+08:00",
    "updated_at": "2026-06-01T10:00:00+08:00"
  }
}
```

---

### 3.4 更新用户信息

| 项目     | 说明                              |
| -------- | --------------------------------- |
| 接口     | `PUT /api/v1/users/{user_id}`     |
| 描述     | 更新用户信息                      |
| 权限     | **Admin**；用户本人（仅部分字段） |

**请求体：**

```json
{
  "display_name": "string, 选填, 显示名称",
  "email": "string, 选填, 邮箱",
  "phone": "string, 选填, 手机号",
  "avatar_url": "string, 选填, 头像地址",
  "department": "string, 选填, 院系/部门"
}
```

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "更新成功",
  "data": {
    "id": "u_001",
    "username": "zhangsan",
    "display_name": "张三（更新）",
    "email": "zhangsan_new@example.com",
    "updated_at": "2026-06-02T11:00:00+08:00"
  }
}
```

---

### 3.5 启用/禁用账号

| 项目     | 说明                                        |
| -------- | ------------------------------------------- |
| 接口     | `PATCH /api/v1/users/{user_id}/status`      |
| 描述     | 启用或禁用用户账号                          |
| 权限     | **Admin**                                   |

**请求体：**

```json
{
  "is_active": "boolean, 必填, true=启用, false=禁用"
}
```

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "账号状态已更新",
  "data": {
    "id": "u_001",
    "is_active": false
  }
}
```

---

### 3.6 重置用户密码

| 项目     | 说明                                        |
| -------- | ------------------------------------------- |
| 接口     | `POST /api/v1/users/{user_id}/reset-password` |
| 描述     | 管理员重置指定用户的密码                    |
| 权限     | **Admin**                                   |

**请求体：**

```json
{
  "new_password": "string, 必填, 新密码"
}
```

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "密码重置成功",
  "data": null
}
```

---

### 3.7 删除用户

| 项目     | 说明                                |
| -------- | ----------------------------------- |
| 接口     | `DELETE /api/v1/users/{user_id}`    |
| 描述     | 删除用户（软删除，标记为已删除）    |
| 权限     | **Admin**                           |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "用户已删除",
  "data": null
}
```

---

### 3.8 批量创建用户

| 项目     | 说明                                |
| -------- | ----------------------------------- |
| 接口     | `POST /api/v1/users/batch`         |
| 描述     | 管理员批量创建用户                  |
| 权限     | **Admin**                           |

**请求体：**

```json
{
  "users": [
    {
      "username": "string",
      "password": "string",
      "display_name": "string",
      "role": "student",
      "email": "string",
      "student_id": "string"
    }
  ]
}
```

**成功响应 (201)：**

```json
{
  "code": 0,
  "message": "批量创建成功",
  "data": {
    "success_count": 5,
    "fail_count": 1,
    "failures": [
      {
        "username": "wangwu",
        "reason": "用户名已存在"
      }
    ]
  }
}
```

---

## 四、学生档案

> 基础路径：`/api/v1/students`

### 4.1 获取学生档案

| 项目     | 说明                                       |
| -------- | ------------------------------------------ |
| 接口     | `GET /api/v1/students/{student_id}/profile` |
| 描述     | 获取学生详细档案信息                       |
| 权限     | **Admin**；**Teacher**（关联学生）；学生本人 |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "user_id": "u_001",
    "student_id": "2024001",
    "display_name": "张三",
    "grade": "研二",
    "department": "计算机科学与技术",
    "research_direction": "自然语言处理",
    "advisor": "王教授",
    "enrollment_date": "2024-09-01",
    "bio": "对NLP方向感兴趣",
    "tags": ["NLP", "Python", "深度学习"],
    "created_at": "2026-01-15T10:00:00+08:00",
    "updated_at": "2026-06-01T10:00:00+08:00"
  }
}
```

---

### 4.2 更新学生档案

| 项目     | 说明                                       |
| -------- | ------------------------------------------ |
| 接口     | `PUT /api/v1/students/{student_id}/profile` |
| 描述     | 更新学生档案信息                           |
| 权限     | **Admin**；学生本人                        |

**请求体：**

```json
{
  "grade": "string, 选填",
  "department": "string, 选填",
  "research_direction": "string, 选填",
  "advisor": "string, 选填",
  "bio": "string, 选填",
  "tags": ["string, 选填, 标签列表"]
}
```

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "档案更新成功",
  "data": {
    "user_id": "u_001",
    "updated_at": "2026-06-02T11:00:00+08:00"
  }
}
```

---

### 4.3 获取学生列表（老师视角）

| 项目     | 说明                          |
| -------- | ----------------------------- |
| 接口     | `GET /api/v1/students`        |
| 描述     | 获取学生列表，含学习概览数据  |
| 权限     | **Admin**；**Teacher**        |

**Query 参数：**

| 参数        | 类型      | 必填 | 说明                     |
| ----------- | --------- | ---- | ------------------------ |
| `page`      | `integer` | 否   | 页码                     |
| `page_size` | `integer` | 否   | 每页条数                 |
| `keyword`   | `string`  | 否   | 搜索关键词               |
| `grade`     | `string`  | 否   | 年级过滤                 |
| `sort_by`   | `string`  | 否   | 排序：`study_time` / `task_rate` / `name` |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "user_id": "u_001",
        "display_name": "张三",
        "student_id": "2024001",
        "grade": "研二",
        "research_direction": "NLP",
        "today_study_minutes": 120,
        "week_task_completion_rate": 0.85,
        "streak_days": 15,
        "last_active_at": "2026-06-02T10:00:00+08:00"
      }
    ],
    "total": 20,
    "page": 1,
    "page_size": 20,
    "total_pages": 1
  }
}
```

---

## 五、仪表盘

> 基础路径：`/api/v1/dashboard`

### 5.1 获取仪表盘布局配置

| 项目     | 说明                                |
| -------- | ----------------------------------- |
| 接口     | `GET /api/v1/dashboard/layout`      |
| 描述     | 获取当前用户的仪表盘布局配置        |
| 权限     | **Student**                         |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "user_id": "u_001",
    "layout": [
      {
        "widget_id": "study_time",
        "title": "今日学习时长",
        "x": 0,
        "y": 0,
        "w": 4,
        "h": 2,
        "visible": true,
        "order": 1
      },
      {
        "widget_id": "todo",
        "title": "TODO",
        "x": 4,
        "y": 0,
        "w": 4,
        "h": 4,
        "visible": true,
        "order": 2
      },
      {
        "widget_id": "notes",
        "title": "便签",
        "x": 8,
        "y": 0,
        "w": 4,
        "h": 3,
        "visible": true,
        "order": 3
      },
      {
        "widget_id": "countdown",
        "title": "倒数日",
        "x": 0,
        "y": 2,
        "w": 4,
        "h": 3,
        "visible": true,
        "order": 4
      },
      {
        "widget_id": "bookmarks",
        "title": "书签",
        "x": 4,
        "y": 4,
        "w": 4,
        "h": 3,
        "visible": true,
        "order": 5
      },
      {
        "widget_id": "tasks_today",
        "title": "今日任务",
        "x": 8,
        "y": 3,
        "w": 4,
        "h": 3,
        "visible": true,
        "order": 6
      },
      {
        "widget_id": "announcements",
        "title": "公告提醒",
        "x": 0,
        "y": 5,
        "w": 6,
        "h": 2,
        "visible": true,
        "order": 7
      },
      {
        "widget_id": "heatmap",
        "title": "学习热力图",
        "x": 0,
        "y": 7,
        "w": 12,
        "h": 3,
        "visible": true,
        "order": 8
      },
      {
        "widget_id": "calendar",
        "title": "月日历计划",
        "x": 6,
        "y": 5,
        "w": 6,
        "h": 2,
        "visible": false,
        "order": 9
      },
      {
        "widget_id": "ai_suggestion",
        "title": "AI 今日建议",
        "x": 0,
        "y": 10,
        "w": 6,
        "h": 3,
        "visible": true,
        "order": 10
      },
      {
        "widget_id": "recent_files",
        "title": "最近上传文件",
        "x": 6,
        "y": 10,
        "w": 6,
        "h": 3,
        "visible": false,
        "order": 11
      },
      {
        "widget_id": "recent_knowledge",
        "title": "最近知识库访问",
        "x": 0,
        "y": 13,
        "w": 6,
        "h": 3,
        "visible": false,
        "order": 12
      }
    ],
    "updated_at": "2026-06-01T15:00:00+08:00"
  }
}
```

---

### 5.2 保存仪表盘布局配置

| 项目     | 说明                                |
| -------- | ----------------------------------- |
| 接口     | `PUT /api/v1/dashboard/layout`      |
| 描述     | 保存当前用户的仪表盘布局配置        |
| 权限     | **Student**                         |

**请求体：**

```json
{
  "layout": [
    {
      "widget_id": "string, 必填, 组件标识",
      "x": "integer, 必填, 网格X坐标",
      "y": "integer, 必填, 网格Y坐标",
      "w": "integer, 必填, 网格宽度",
      "h": "integer, 必填, 网格高度",
      "visible": "boolean, 必填, 是否可见",
      "order": "integer, 必填, 排列顺序"
    }
  ]
}
```

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "布局保存成功",
  "data": {
    "updated_at": "2026-06-02T11:30:00+08:00"
  }
}
```

---

### 5.3 重置仪表盘布局

| 项目     | 说明                                  |
| -------- | ------------------------------------- |
| 接口     | `POST /api/v1/dashboard/layout/reset` |
| 描述     | 恢复默认仪表盘布局                    |
| 权限     | **Student**                           |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "布局已重置为默认",
  "data": {
    "layout": [ ... ],
    "updated_at": "2026-06-02T11:35:00+08:00"
  }
}
```

---

### 5.4 获取仪表盘聚合数据

| 项目     | 说明                             |
| -------- | -------------------------------- |
| 接口     | `GET /api/v1/dashboard/data`     |
| 描述     | 一次性获取仪表盘所有组件需要的数据 |
| 权限     | **Student**                      |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "study_time": {
      "today_minutes": 120,
      "week_minutes": 840,
      "month_minutes": 3600
    },
    "todos": {
      "today_total": 5,
      "today_completed": 3,
      "overdue_count": 1,
      "items": [ ... ]
    },
    "notes": {
      "pinned": [ ... ],
      "recent": [ ... ]
    },
    "countdowns": {
      "items": [ ... ]
    },
    "bookmarks": {
      "categories": [ ... ]
    },
    "tasks_today": {
      "pending_count": 2,
      "items": [ ... ]
    },
    "announcements": {
      "unread_count": 3,
      "recent": [ ... ]
    },
    "ai_suggestion": {
      "content": "根据你最近的学习情况，建议今天...",
      "generated_at": "2026-06-02T00:05:00+08:00"
    },
    "recent_files": [ ... ],
    "recent_knowledge": [ ... ]
  }
}
```

---

## 六、TODO

> 基础路径：`/api/v1/todos`

### 6.1 创建 TODO

| 项目     | 说明                        |
| -------- | --------------------------- |
| 接口     | `POST /api/v1/todos`        |
| 描述     | 创建一个新的 TODO 项        |
| 权限     | **Student**                 |

**请求体：**

```json
{
  "title": "string, 必填, 标题",
  "description": "string, 选填, 详细描述",
  "priority": "string, 选填, 优先级: low | medium | high | urgent, 默认 medium",
  "category": "string, 选填, 分类",
  "due_date": "string, 选填, 截止时间, ISO 8601 格式"
}
```

**成功响应 (201)：**

```json
{
  "code": 0,
  "message": "创建成功",
  "data": {
    "id": "todo_001",
    "title": "阅读论文 Attention is All You Need",
    "description": "重点关注 Multi-Head Attention 机制",
    "priority": "high",
    "category": "论文阅读",
    "status": "pending",
    "due_date": "2026-06-05T23:59:59+08:00",
    "created_at": "2026-06-02T10:00:00+08:00",
    "updated_at": "2026-06-02T10:00:00+08:00",
    "completed_at": null
  }
}
```

---

### 6.2 获取 TODO 列表

| 项目     | 说明                        |
| -------- | --------------------------- |
| 接口     | `GET /api/v1/todos`         |
| 描述     | 获取当前用户的 TODO 列表    |
| 权限     | **Student**                 |

**Query 参数：**

| 参数        | 类型      | 必填 | 说明                                               |
| ----------- | --------- | ---- | -------------------------------------------------- |
| `page`      | `integer` | 否   | 页码                                               |
| `page_size` | `integer` | 否   | 每页条数                                           |
| `status`    | `string`  | 否   | 状态过滤：`pending` / `completed` / `all`          |
| `priority`  | `string`  | 否   | 优先级过滤：`low` / `medium` / `high` / `urgent`   |
| `category`  | `string`  | 否   | 分类过滤                                           |
| `date`      | `string`  | 否   | 日期过滤（截止日期为该天的项）                     |
| `overdue`   | `boolean` | 否   | 是否只显示逾期项                                   |
| `sort_by`   | `string`  | 否   | 排序：`due_date` / `priority` / `created_at`       |
| `sort_order`| `string`  | 否   | `asc` / `desc`                                     |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "todo_001",
        "title": "阅读论文 Attention is All You Need",
        "description": "重点关注 Multi-Head Attention 机制",
        "priority": "high",
        "category": "论文阅读",
        "status": "pending",
        "due_date": "2026-06-05T23:59:59+08:00",
        "is_overdue": false,
        "created_at": "2026-06-02T10:00:00+08:00",
        "updated_at": "2026-06-02T10:00:00+08:00",
        "completed_at": null
      }
    ],
    "total": 15,
    "page": 1,
    "page_size": 20,
    "total_pages": 1
  }
}
```

---

### 6.3 获取 TODO 详情

| 项目     | 说明                            |
| -------- | ------------------------------- |
| 接口     | `GET /api/v1/todos/{todo_id}`   |
| 描述     | 获取单个 TODO 详细信息          |
| 权限     | **Student**（仅本人）           |

**成功响应 (200)：** 同创建响应中的 `data` 结构。

---

### 6.4 更新 TODO

| 项目     | 说明                            |
| -------- | ------------------------------- |
| 接口     | `PUT /api/v1/todos/{todo_id}`   |
| 描述     | 更新 TODO 内容                  |
| 权限     | **Student**（仅本人）           |

**请求体：**

```json
{
  "title": "string, 选填",
  "description": "string, 选填",
  "priority": "string, 选填",
  "category": "string, 选填",
  "due_date": "string, 选填"
}
```

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "更新成功",
  "data": { ... }
}
```

---

### 6.5 标记 TODO 完成/未完成

| 项目     | 说明                                      |
| -------- | ----------------------------------------- |
| 接口     | `PATCH /api/v1/todos/{todo_id}/status`    |
| 描述     | 切换 TODO 完成状态                        |
| 权限     | **Student**（仅本人）                     |

**请求体：**

```json
{
  "status": "string, 必填, pending | completed"
}
```

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "状态已更新",
  "data": {
    "id": "todo_001",
    "status": "completed",
    "completed_at": "2026-06-02T15:00:00+08:00"
  }
}
```

---

### 6.6 删除 TODO

| 项目     | 说明                              |
| -------- | --------------------------------- |
| 接口     | `DELETE /api/v1/todos/{todo_id}`  |
| 描述     | 删除指定 TODO                     |
| 权限     | **Student**（仅本人）             |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "删除成功",
  "data": null
}
```

---

## 七、便签

> 基础路径：`/api/v1/notes`

### 7.1 创建便签

| 项目     | 说明                        |
| -------- | --------------------------- |
| 接口     | `POST /api/v1/notes`        |
| 描述     | 创建一个新便签              |
| 权限     | **Student**                 |

**请求体：**

```json
{
  "content": "string, 必填, 便签内容",
  "color": "string, 选填, 颜色标记: yellow | green | blue | pink | purple, 默认 yellow",
  "category": "string, 选填, 分类",
  "is_pinned": "boolean, 选填, 是否置顶, 默认 false"
}
```

**成功响应 (201)：**

```json
{
  "code": 0,
  "message": "创建成功",
  "data": {
    "id": "note_001",
    "content": "今天学到了 Transformer 的关键原理...",
    "color": "yellow",
    "category": "学习笔记",
    "is_pinned": false,
    "created_at": "2026-06-02T10:00:00+08:00",
    "updated_at": "2026-06-02T10:00:00+08:00"
  }
}
```

---

### 7.2 获取便签列表

| 项目     | 说明                        |
| -------- | --------------------------- |
| 接口     | `GET /api/v1/notes`         |
| 描述     | 获取当前用户的便签列表      |
| 权限     | **Student**                 |

**Query 参数：**

| 参数        | 类型      | 必填 | 说明                     |
| ----------- | --------- | ---- | ------------------------ |
| `page`      | `integer` | 否   | 页码                     |
| `page_size` | `integer` | 否   | 每页条数                 |
| `color`     | `string`  | 否   | 颜色过滤                 |
| `category`  | `string`  | 否   | 分类过滤                 |
| `is_pinned` | `boolean` | 否   | 置顶过滤                 |
| `keyword`   | `string`  | 否   | 内容搜索关键词           |

**成功响应 (200)：** 分页格式，`items` 中每项结构同创建响应。

---

### 7.3 更新便签

| 项目     | 说明                            |
| -------- | ------------------------------- |
| 接口     | `PUT /api/v1/notes/{note_id}`   |
| 描述     | 更新便签内容                    |
| 权限     | **Student**（仅本人）           |

**请求体：**

```json
{
  "content": "string, 选填",
  "color": "string, 选填",
  "category": "string, 选填"
}
```

**成功响应 (200)：** 同创建响应。

---

### 7.4 置顶/取消置顶便签

| 项目     | 说明                                  |
| -------- | ------------------------------------- |
| 接口     | `PATCH /api/v1/notes/{note_id}/pin`   |
| 描述     | 切换便签置顶状态                      |
| 权限     | **Student**（仅本人）                 |

**请求体：**

```json
{
  "is_pinned": "boolean, 必填"
}
```

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "置顶状态已更新",
  "data": {
    "id": "note_001",
    "is_pinned": true
  }
}
```

---

### 7.5 删除便签

| 项目     | 说明                              |
| -------- | --------------------------------- |
| 接口     | `DELETE /api/v1/notes/{note_id}`  |
| 描述     | 删除指定便签                      |
| 权限     | **Student**（仅本人）             |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "删除成功",
  "data": null
}
```

---

## 八、倒数日

> 基础路径：`/api/v1/countdowns`

### 8.1 创建倒数日

| 项目     | 说明                            |
| -------- | ------------------------------- |
| 接口     | `POST /api/v1/countdowns`       |
| 描述     | 创建一个新的倒数日              |
| 权限     | **Student**                     |

**请求体：**

```json
{
  "title": "string, 必填, 倒数日标题",
  "target_date": "string, 必填, 目标日期, 如 2026-09-01",
  "color": "string, 选填, 颜色标记",
  "icon": "string, 选填, 图标标识",
  "remind_before_days": "integer, 选填, 提前提醒天数, 如 7",
  "related_task_id": "string, 选填, 关联任务ID"
}
```

**成功响应 (201)：**

```json
{
  "code": 0,
  "message": "创建成功",
  "data": {
    "id": "cd_001",
    "title": "论文投稿截止",
    "target_date": "2026-09-01",
    "color": "#FF5722",
    "icon": "calendar",
    "remaining_days": 91,
    "remind_before_days": 7,
    "related_task_id": null,
    "is_expired": false,
    "created_at": "2026-06-02T10:00:00+08:00",
    "updated_at": "2026-06-02T10:00:00+08:00"
  }
}
```

---

### 8.2 获取倒数日列表

| 项目     | 说明                            |
| -------- | ------------------------------- |
| 接口     | `GET /api/v1/countdowns`        |
| 描述     | 获取当前用户的倒数日列表        |
| 权限     | **Student**                     |

**Query 参数：**

| 参数           | 类型      | 必填 | 说明                           |
| -------------- | --------- | ---- | ------------------------------ |
| `include_expired` | `boolean` | 否 | 是否包含已过期的项，默认 false |
| `sort_by`      | `string`  | 否   | `target_date` / `created_at`   |

**成功响应 (200)：** 数组格式，`data.items` 中每项结构同创建响应。

---

### 8.3 更新倒数日

| 项目     | 说明                                      |
| -------- | ----------------------------------------- |
| 接口     | `PUT /api/v1/countdowns/{countdown_id}`   |
| 描述     | 更新倒数日信息                            |
| 权限     | **Student**（仅本人）                     |

**请求体：**

```json
{
  "title": "string, 选填",
  "target_date": "string, 选填",
  "color": "string, 选填",
  "icon": "string, 选填",
  "remind_before_days": "integer, 选填",
  "related_task_id": "string, 选填"
}
```

**成功响应 (200)：** 同创建响应。

---

### 8.4 删除倒数日

| 项目     | 说明                                        |
| -------- | ------------------------------------------- |
| 接口     | `DELETE /api/v1/countdowns/{countdown_id}`  |
| 描述     | 删除指定倒数日                              |
| 权限     | **Student**（仅本人）                       |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "删除成功",
  "data": null
}
```

---

## 九、书签

> 基础路径：`/api/v1/bookmarks`

### 9.1 创建书签

| 项目     | 说明                           |
| -------- | ------------------------------ |
| 接口     | `POST /api/v1/bookmarks`      |
| 描述     | 添加一个新书签                 |
| 权限     | **Student**                    |

**请求体：**

```json
{
  "title": "string, 必填, 书签标题",
  "url": "string, 必填, 链接地址",
  "category": "string, 选填, 分类",
  "icon": "string, 选填, 图标URL或标识",
  "description": "string, 选填, 简短描述"
}
```

**成功响应 (201)：**

```json
{
  "code": 0,
  "message": "创建成功",
  "data": {
    "id": "bm_001",
    "title": "PyTorch 官方文档",
    "url": "https://pytorch.org/docs/stable/",
    "category": "开发文档",
    "icon": "https://pytorch.org/favicon.ico",
    "description": "PyTorch 官方技术文档",
    "visit_count": 0,
    "created_at": "2026-06-02T10:00:00+08:00",
    "updated_at": "2026-06-02T10:00:00+08:00"
  }
}
```

---

### 9.2 获取书签列表

| 项目     | 说明                           |
| -------- | ------------------------------ |
| 接口     | `GET /api/v1/bookmarks`        |
| 描述     | 获取当前用户的书签列表         |
| 权限     | **Student**                    |

**Query 参数：**

| 参数        | 类型      | 必填 | 说明           |
| ----------- | --------- | ---- | -------------- |
| `page`      | `integer` | 否   | 页码           |
| `page_size` | `integer` | 否   | 每页条数       |
| `category`  | `string`  | 否   | 分类过滤       |
| `keyword`   | `string`  | 否   | 关键词搜索     |

**成功响应 (200)：** 分页格式，`items` 结构同创建响应。

---

### 9.3 更新书签

| 项目     | 说明                                      |
| -------- | ----------------------------------------- |
| 接口     | `PUT /api/v1/bookmarks/{bookmark_id}`     |
| 描述     | 更新书签信息                              |
| 权限     | **Student**（仅本人）                     |

**请求体：**

```json
{
  "title": "string, 选填",
  "url": "string, 选填",
  "category": "string, 选填",
  "icon": "string, 选填",
  "description": "string, 选填"
}
```

**成功响应 (200)：** 同创建响应。

---

### 9.4 删除书签

| 项目     | 说明                                        |
| -------- | ------------------------------------------- |
| 接口     | `DELETE /api/v1/bookmarks/{bookmark_id}`    |
| 描述     | 删除指定书签                                |
| 权限     | **Student**（仅本人）                       |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "删除成功",
  "data": null
}
```

---

### 9.5 记录书签访问

| 项目     | 说明                                            |
| -------- | ----------------------------------------------- |
| 接口     | `POST /api/v1/bookmarks/{bookmark_id}/visit`    |
| 描述     | 记录一次书签访问行为（前端点击后调用）          |
| 权限     | **Student**（仅本人）                           |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "访问已记录",
  "data": {
    "visit_count": 15
  }
}
```

---

### 9.6 获取书签分类列表

| 项目     | 说明                                  |
| -------- | ------------------------------------- |
| 接口     | `GET /api/v1/bookmarks/categories`    |
| 描述     | 获取当前用户的书签分类列表            |
| 权限     | **Student**                           |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "categories": [
      { "name": "开发文档", "count": 5 },
      { "name": "课程资源", "count": 3 },
      { "name": "工具网站", "count": 8 }
    ]
  }
}
```

---

## 十、公告

> 基础路径：`/api/v1/announcements`

### 10.1 创建公告

| 项目     | 说明                              |
| -------- | --------------------------------- |
| 接口     | `POST /api/v1/announcements`      |
| 描述     | 创建一条新公告                    |
| 权限     | **Admin**；**Teacher**            |

**请求体：**

```json
{
  "title": "string, 必填, 公告标题",
  "content": "string, 必填, 公告内容（支持 Markdown）",
  "target_type": "string, 必填, 发布对象类型: all | students | teachers | specific_users | group",
  "target_ids": ["string, 选填, 当 target_type 为 specific_users 或 group 时，指定用户/分组 ID"],
  "is_pinned": "boolean, 选填, 是否置顶, 默认 false",
  "expire_at": "string, 选填, 过期时间, ISO 8601 格式",
  "attachments": ["string, 选填, 附件文件 ID 列表"],
  "is_draft": "boolean, 选填, 是否为草稿, 默认 false"
}
```

**成功响应 (201)：**

```json
{
  "code": 0,
  "message": "创建成功",
  "data": {
    "id": "ann_001",
    "title": "关于暑期学习安排的通知",
    "content": "...",
    "target_type": "all",
    "target_ids": [],
    "is_pinned": true,
    "status": "published",
    "expire_at": "2026-07-01T00:00:00+08:00",
    "author": {
      "id": "u_teacher_001",
      "display_name": "王教授",
      "role": "teacher"
    },
    "read_count": 0,
    "total_receivers": 20,
    "created_at": "2026-06-02T10:00:00+08:00",
    "updated_at": "2026-06-02T10:00:00+08:00"
  }
}
```

---

### 10.2 获取公告列表

| 项目     | 说明                              |
| -------- | --------------------------------- |
| 接口     | `GET /api/v1/announcements`       |
| 描述     | 获取公告列表                      |
| 权限     | 所有已登录用户（按角色过滤可见范围） |

**Query 参数：**

| 参数        | 类型      | 必填 | 说明                                       |
| ----------- | --------- | ---- | ------------------------------------------ |
| `page`      | `integer` | 否   | 页码                                       |
| `page_size` | `integer` | 否   | 每页条数                                   |
| `status`    | `string`  | 否   | 状态：`published` / `draft` / `expired`    |
| `is_read`   | `boolean` | 否   | 是否已读（学生视角）                       |
| `keyword`   | `string`  | 否   | 标题搜索                                   |
| `author_id` | `string`  | 否   | 发布者 ID（管理/老师视角）                 |

**成功响应 (200)：** 分页格式。

---

### 10.3 获取公告详情

| 项目     | 说明                                          |
| -------- | --------------------------------------------- |
| 接口     | `GET /api/v1/announcements/{announcement_id}` |
| 描述     | 获取公告详细内容，自动标记为已读              |
| 权限     | 所有已登录用户（需在接收范围内）              |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "ann_001",
    "title": "关于暑期学习安排的通知",
    "content": "# 暑期学习安排\n\n各位同学...",
    "target_type": "all",
    "is_pinned": true,
    "status": "published",
    "expire_at": "2026-07-01T00:00:00+08:00",
    "author": {
      "id": "u_teacher_001",
      "display_name": "王教授",
      "role": "teacher"
    },
    "attachments": [
      {
        "id": "file_001",
        "filename": "暑期计划.pdf",
        "url": "/api/v1/files/file_001/download"
      }
    ],
    "is_read": true,
    "read_at": "2026-06-02T11:00:00+08:00",
    "read_count": 15,
    "total_receivers": 20,
    "created_at": "2026-06-02T10:00:00+08:00"
  }
}
```

---

### 10.4 更新公告

| 项目     | 说明                                          |
| -------- | --------------------------------------------- |
| 接口     | `PUT /api/v1/announcements/{announcement_id}` |
| 描述     | 更新公告内容                                  |
| 权限     | **Admin**；**Teacher**（仅本人创建的公告）    |

**请求体：**

```json
{
  "title": "string, 选填",
  "content": "string, 选填",
  "target_type": "string, 选填",
  "target_ids": ["string, 选填"],
  "is_pinned": "boolean, 选填",
  "expire_at": "string, 选填",
  "attachments": ["string, 选填"]
}
```

**成功响应 (200)：** 同详情响应。

---

### 10.5 删除公告

| 项目     | 说明                                              |
| -------- | ------------------------------------------------- |
| 接口     | `DELETE /api/v1/announcements/{announcement_id}`  |
| 描述     | 删除指定公告                                      |
| 权限     | **Admin**；**Teacher**（仅本人创建的公告）        |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "删除成功",
  "data": null
}
```

---

### 10.6 发布草稿公告

| 项目     | 说明                                                      |
| -------- | --------------------------------------------------------- |
| 接口     | `POST /api/v1/announcements/{announcement_id}/publish`    |
| 描述     | 将草稿状态的公告正式发布                                  |
| 权限     | **Admin**；**Teacher**（仅本人创建的公告）                |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "公告已发布",
  "data": {
    "id": "ann_001",
    "status": "published",
    "published_at": "2026-06-02T12:00:00+08:00"
  }
}
```

---

### 10.7 标记公告已读

| 项目     | 说明                                                  |
| -------- | ----------------------------------------------------- |
| 接口     | `POST /api/v1/announcements/{announcement_id}/read`   |
| 描述     | 手动标记公告为已读                                    |
| 权限     | 所有已登录用户                                        |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "已标记为已读",
  "data": null
}
```

---

### 10.8 获取公告阅读统计

| 项目     | 说明                                                    |
| -------- | ------------------------------------------------------- |
| 接口     | `GET /api/v1/announcements/{announcement_id}/read-stats`|
| 描述     | 获取公告的阅读统计详情                                  |
| 权限     | **Admin**；**Teacher**（仅本人创建的公告）              |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "total_receivers": 20,
    "read_count": 15,
    "unread_count": 5,
    "read_rate": 0.75,
    "read_users": [
      { "user_id": "u_001", "display_name": "张三", "read_at": "2026-06-02T11:00:00+08:00" }
    ],
    "unread_users": [
      { "user_id": "u_005", "display_name": "赵六" }
    ]
  }
}
```

---

## 十一、任务

> 基础路径：`/api/v1/tasks`

### 11.1 创建任务

| 项目     | 说明                          |
| -------- | ----------------------------- |
| 接口     | `POST /api/v1/tasks`          |
| 描述     | 创建并分配一个新任务          |
| 权限     | **Admin**；**Teacher**        |

**请求体：**

```json
{
  "title": "string, 必填, 任务标题",
  "description": "string, 必填, 任务详细描述（支持 Markdown）",
  "priority": "string, 选填, 优先级: low | medium | high | urgent, 默认 medium",
  "due_date": "string, 必填, 截止时间",
  "assignee_ids": ["string, 必填, 被分配学生 ID 列表"],
  "attachments": ["string, 选填, 附件文件 ID 列表"],
  "category": "string, 选填, 任务分类",
  "max_submissions": "integer, 选填, 最大提交次数, 默认不限"
}
```

**成功响应 (201)：**

```json
{
  "code": 0,
  "message": "任务创建成功",
  "data": {
    "id": "task_001",
    "title": "完成论文综述初稿",
    "description": "...",
    "priority": "high",
    "status": "published",
    "due_date": "2026-06-10T23:59:59+08:00",
    "assignee_count": 5,
    "attachments": [],
    "category": "论文",
    "creator": {
      "id": "u_teacher_001",
      "display_name": "王教授",
      "role": "teacher"
    },
    "created_at": "2026-06-02T10:00:00+08:00"
  }
}
```

---

### 11.2 获取任务列表

| 项目     | 说明                          |
| -------- | ----------------------------- |
| 接口     | `GET /api/v1/tasks`           |
| 描述     | 获取任务列表                  |
| 权限     | 所有已登录用户（按角色过滤）  |

**Query 参数：**

| 参数          | 类型      | 必填 | 说明                                                                            |
| ------------- | --------- | ---- | ------------------------------------------------------------------------------- |
| `page`        | `integer` | 否   | 页码                                                                            |
| `page_size`   | `integer` | 否   | 每页条数                                                                        |
| `status`      | `string`  | 否   | 状态：`not_started` / `in_progress` / `submitted` / `completed` / `rejected` / `overdue` / `cancelled` |
| `priority`    | `string`  | 否   | 优先级过滤                                                                      |
| `creator_id`  | `string`  | 否   | 创建者 ID（管理/老师视角）                                                      |
| `assignee_id` | `string`  | 否   | 被分配人 ID                                                                     |
| `keyword`     | `string`  | 否   | 标题搜索                                                                        |
| `due_before`  | `string`  | 否   | 截止日期早于                                                                    |
| `due_after`   | `string`  | 否   | 截止日期晚于                                                                    |

**成功响应 (200)：** 分页格式。

**学生视角的任务项结构：**

```json
{
  "id": "task_001",
  "title": "完成论文综述初稿",
  "priority": "high",
  "my_status": "in_progress",
  "due_date": "2026-06-10T23:59:59+08:00",
  "is_overdue": false,
  "creator": {
    "id": "u_teacher_001",
    "display_name": "王教授"
  },
  "submission_count": 0,
  "created_at": "2026-06-02T10:00:00+08:00"
}
```

**老师/管理员视角的任务项结构：**

```json
{
  "id": "task_001",
  "title": "完成论文综述初稿",
  "priority": "high",
  "status": "published",
  "due_date": "2026-06-10T23:59:59+08:00",
  "assignee_count": 5,
  "completed_count": 2,
  "submitted_count": 1,
  "overdue_count": 0,
  "completion_rate": 0.4,
  "creator": {
    "id": "u_teacher_001",
    "display_name": "王教授"
  },
  "created_at": "2026-06-02T10:00:00+08:00"
}
```

---

### 11.3 获取任务详情

| 项目     | 说明                            |
| -------- | ------------------------------- |
| 接口     | `GET /api/v1/tasks/{task_id}`   |
| 描述     | 获取任务详细信息                |
| 权限     | 相关用户                        |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "task_001",
    "title": "完成论文综述初稿",
    "description": "# 要求\n\n1. 综述不少于5000字...",
    "priority": "high",
    "due_date": "2026-06-10T23:59:59+08:00",
    "category": "论文",
    "attachments": [
      {
        "id": "file_002",
        "filename": "参考格式.docx",
        "url": "/api/v1/files/file_002/download"
      }
    ],
    "creator": {
      "id": "u_teacher_001",
      "display_name": "王教授",
      "role": "teacher"
    },
    "assignees": [
      {
        "user_id": "u_001",
        "display_name": "张三",
        "status": "in_progress",
        "submitted_at": null,
        "completed_at": null
      },
      {
        "user_id": "u_002",
        "display_name": "李四",
        "status": "submitted",
        "submitted_at": "2026-06-05T14:00:00+08:00",
        "completed_at": null
      }
    ],
    "stats": {
      "total": 5,
      "not_started": 1,
      "in_progress": 2,
      "submitted": 1,
      "completed": 1,
      "rejected": 0,
      "overdue": 0
    },
    "created_at": "2026-06-02T10:00:00+08:00",
    "updated_at": "2026-06-02T10:00:00+08:00"
  }
}
```

---

### 11.4 更新任务

| 项目     | 说明                            |
| -------- | ------------------------------- |
| 接口     | `PUT /api/v1/tasks/{task_id}`   |
| 描述     | 更新任务信息                    |
| 权限     | **Admin**；**Teacher**（仅创建者） |

**请求体：**

```json
{
  "title": "string, 选填",
  "description": "string, 选填",
  "priority": "string, 选填",
  "due_date": "string, 选填",
  "category": "string, 选填",
  "attachments": ["string, 选填"]
}
```

**成功响应 (200)：** 同详情响应。

---

### 11.5 删除任务

| 项目     | 说明                              |
| -------- | --------------------------------- |
| 接口     | `DELETE /api/v1/tasks/{task_id}`  |
| 描述     | 删除/取消指定任务                 |
| 权限     | **Admin**；**Teacher**（仅创建者） |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "任务已取消",
  "data": null
}
```

---

### 11.6 学生提交任务

| 项目     | 说明                                      |
| -------- | ----------------------------------------- |
| 接口     | `POST /api/v1/tasks/{task_id}/submit`     |
| 描述     | 学生提交任务成果                          |
| 权限     | **Student**（已被分配的学生）             |

**请求体：**

```json
{
  "content": "string, 选填, 提交说明（支持 Markdown）",
  "attachments": ["string, 选填, 附件文件 ID 列表"]
}
```

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "提交成功",
  "data": {
    "submission_id": "sub_001",
    "task_id": "task_001",
    "content": "论文综述初稿已完成...",
    "attachments": [
      {
        "id": "file_003",
        "filename": "综述初稿.pdf"
      }
    ],
    "status": "submitted",
    "submitted_at": "2026-06-05T14:00:00+08:00"
  }
}
```

---

### 11.7 老师审核任务

| 项目     | 说明                                      |
| -------- | ----------------------------------------- |
| 接口     | `POST /api/v1/tasks/{task_id}/review`     |
| 描述     | 老师审核学生提交的任务（通过或退回）      |
| 权限     | **Admin**；**Teacher**（任务创建者）      |

**请求体：**

```json
{
  "student_id": "string, 必填, 学生 ID",
  "action": "string, 必填, approve | reject",
  "comment": "string, 选填, 审核意见"
}
```

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "审核完成",
  "data": {
    "task_id": "task_001",
    "student_id": "u_001",
    "action": "approve",
    "status": "completed",
    "comment": "论文综述写得不错，通过",
    "reviewed_at": "2026-06-06T10:00:00+08:00"
  }
}
```

---

### 11.8 获取任务提交记录

| 项目     | 说明                                            |
| -------- | ----------------------------------------------- |
| 接口     | `GET /api/v1/tasks/{task_id}/submissions`       |
| 描述     | 获取某任务下的所有提交记录                      |
| 权限     | **Admin**；**Teacher**（创建者）；**Student**（本人） |

**Query 参数：**

| 参数         | 类型     | 必填 | 说明                               |
| ------------ | -------- | ---- | ---------------------------------- |
| `student_id` | `string` | 否   | 学生 ID（老师查看特定学生的提交）  |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "submission_id": "sub_001",
        "student": {
          "id": "u_001",
          "display_name": "张三"
        },
        "content": "论文综述初稿已完成...",
        "attachments": [ ... ],
        "status": "submitted",
        "submitted_at": "2026-06-05T14:00:00+08:00",
        "review": null
      }
    ]
  }
}
```

---

### 11.9 获取任务统计

| 项目     | 说明                                |
| -------- | ----------------------------------- |
| 接口     | `GET /api/v1/tasks/stats`           |
| 描述     | 获取任务统计概览                    |
| 权限     | **Admin**；**Teacher**              |

**Query 参数：**

| 参数         | 类型     | 必填 | 说明                                  |
| ------------ | -------- | ---- | ------------------------------------- |
| `creator_id` | `string` | 否   | 按创建者过滤                          |
| `start_date` | `string` | 否   | 统计起始日期                          |
| `end_date`   | `string` | 否   | 统计截止日期                          |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "total_tasks": 30,
    "active_tasks": 10,
    "completed_tasks": 15,
    "overdue_tasks": 3,
    "cancelled_tasks": 2,
    "avg_completion_rate": 0.78,
    "avg_completion_days": 5.2
  }
}
```

---

## 十二、日历计划

> 基础路径：`/api/v1/calendar`

### 12.1 创建日历事件

| 项目     | 说明                           |
| -------- | ------------------------------ |
| 接口     | `POST /api/v1/calendar/events` |
| 描述     | 创建一个日历事件/计划          |
| 权限     | **Student**；**Teacher**（可为学生创建） |

**请求体：**

```json
{
  "title": "string, 必填, 事件标题",
  "description": "string, 选填, 事件描述",
  "start_time": "string, 必填, 开始时间",
  "end_time": "string, 必填, 结束时间",
  "all_day": "boolean, 选填, 是否全天事件, 默认 false",
  "color": "string, 选填, 颜色标记",
  "category": "string, 选填, 分类: study | task | meeting | personal | other",
  "reminder_minutes": "integer, 选填, 提前提醒分钟数",
  "recurrence": "string, 选填, 重复规则: none | daily | weekly | monthly",
  "related_task_id": "string, 选填, 关联任务 ID",
  "related_countdown_id": "string, 选填, 关联倒数日 ID",
  "target_student_id": "string, 选填, 目标学生 ID（老师为学生创建时使用）"
}
```

**成功响应 (201)：**

```json
{
  "code": 0,
  "message": "创建成功",
  "data": {
    "id": "evt_001",
    "title": "阅读论文",
    "description": "阅读 Attention is All You Need",
    "start_time": "2026-06-03T09:00:00+08:00",
    "end_time": "2026-06-03T11:00:00+08:00",
    "all_day": false,
    "color": "#4CAF50",
    "category": "study",
    "status": "pending",
    "reminder_minutes": 30,
    "recurrence": "none",
    "creator": {
      "id": "u_001",
      "display_name": "张三"
    },
    "created_at": "2026-06-02T10:00:00+08:00"
  }
}
```

---

### 12.2 获取日历事件列表

| 项目     | 说明                            |
| -------- | ------------------------------- |
| 接口     | `GET /api/v1/calendar/events`   |
| 描述     | 获取日历事件，支持不同视图      |
| 权限     | **Student**（本人）；**Teacher**（关联学生）；**Admin** |

**Query 参数：**

| 参数         | 类型     | 必填 | 说明                                           |
| ------------ | -------- | ---- | ---------------------------------------------- |
| `start_date` | `string` | 必填 | 查询起始日期，如 `2026-06-01`                  |
| `end_date`   | `string` | 必填 | 查询结束日期，如 `2026-06-30`                  |
| `view`       | `string` | 否   | 视图类型：`month` / `week` / `day`，默认 `month` |
| `category`   | `string` | 否   | 分类过滤                                       |
| `student_id` | `string` | 否   | 学生 ID（老师查看学生计划时使用）              |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "events": [
      {
        "id": "evt_001",
        "title": "阅读论文",
        "start_time": "2026-06-03T09:00:00+08:00",
        "end_time": "2026-06-03T11:00:00+08:00",
        "all_day": false,
        "color": "#4CAF50",
        "category": "study",
        "status": "pending"
      }
    ],
    "start_date": "2026-06-01",
    "end_date": "2026-06-30"
  }
}
```

---

### 12.3 更新日历事件

| 项目     | 说明                                       |
| -------- | ------------------------------------------ |
| 接口     | `PUT /api/v1/calendar/events/{event_id}`   |
| 描述     | 更新日历事件                               |
| 权限     | 创建者本人；**Admin**                      |

**请求体：** 同创建请求（所有字段可选）。

**成功响应 (200)：** 同创建响应。

---

### 12.4 更新日历事件状态

| 项目     | 说明                                               |
| -------- | -------------------------------------------------- |
| 接口     | `PATCH /api/v1/calendar/events/{event_id}/status`  |
| 描述     | 更新事件状态（标记完成等）                         |
| 权限     | 创建者本人；**Admin**                              |

**请求体：**

```json
{
  "status": "string, 必填, pending | completed | cancelled"
}
```

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "状态已更新",
  "data": {
    "id": "evt_001",
    "status": "completed",
    "completed_at": "2026-06-03T11:30:00+08:00"
  }
}
```

---

### 12.5 删除日历事件

| 项目     | 说明                                          |
| -------- | --------------------------------------------- |
| 接口     | `DELETE /api/v1/calendar/events/{event_id}`   |
| 描述     | 删除日历事件                                  |
| 权限     | 创建者本人；**Admin**                         |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "删除成功",
  "data": null
}
```

---

## 十三、学习时长

> 基础路径：`/api/v1/study-time`

### 13.1 上报心跳

| 项目     | 说明                                    |
| -------- | --------------------------------------- |
| 接口     | `POST /api/v1/study-time/heartbeat`     |
| 描述     | 前端定期上报心跳，用于计算在线学习时长  |
| 权限     | **Student**                             |

**请求体：**

```json
{
  "page": "string, 必填, 当前页面标识, 如 dashboard / ai_chat / knowledge",
  "timestamp": "string, 必填, 客户端时间戳"
}
```

**心跳间隔：** 建议每 **60 秒** 上报一次。

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "today_minutes": 125,
    "session_minutes": 45
  }
}
```

---

### 13.2 获取学习时长统计

| 项目     | 说明                                |
| -------- | ----------------------------------- |
| 接口     | `GET /api/v1/study-time/stats`      |
| 描述     | 获取学习时长统计数据                |
| 权限     | **Student**（本人）；**Teacher**（关联学生）；**Admin** |

**Query 参数：**

| 参数         | 类型     | 必填 | 说明                                           |
| ------------ | -------- | ---- | ---------------------------------------------- |
| `period`     | `string` | 否   | 时段：`today` / `week` / `month` / `custom`    |
| `start_date` | `string` | 否   | 自定义起始日期                                 |
| `end_date`   | `string` | 否   | 自定义结束日期                                 |
| `student_id` | `string` | 否   | 学生 ID（老师/管理员查看时）                   |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "today_minutes": 125,
    "week_minutes": 840,
    "month_minutes": 3600,
    "total_minutes": 18000,
    "daily_details": [
      { "date": "2026-06-01", "minutes": 180 },
      { "date": "2026-06-02", "minutes": 125 }
    ],
    "page_distribution": [
      { "page": "ai_chat", "minutes": 45, "percentage": 0.36 },
      { "page": "knowledge", "minutes": 30, "percentage": 0.24 },
      { "page": "dashboard", "minutes": 50, "percentage": 0.40 }
    ],
    "avg_daily_minutes": 120,
    "streak_days": 15
  }
}
```

---

### 13.3 获取学习时长排行

| 项目     | 说明                                    |
| -------- | --------------------------------------- |
| 接口     | `GET /api/v1/study-time/ranking`        |
| 描述     | 获取学生学习时长排行榜                  |
| 权限     | **Teacher**；**Admin**                  |

**Query 参数：**

| 参数     | 类型     | 必填 | 说明                          |
| -------- | -------- | ---- | ----------------------------- |
| `period` | `string` | 否   | `today` / `week` / `month`   |
| `limit`  | `integer`| 否   | 返回数量，默认 10             |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "period": "week",
    "ranking": [
      { "rank": 1, "user_id": "u_001", "display_name": "张三", "minutes": 840 },
      { "rank": 2, "user_id": "u_002", "display_name": "李四", "minutes": 720 }
    ]
  }
}
```

---

## 十四、行为日志

> 基础路径：`/api/v1/behavior-logs`

### 14.1 记录行为

| 项目     | 说明                               |
| -------- | ---------------------------------- |
| 接口     | `POST /api/v1/behavior-logs`       |
| 描述     | 记录用户的一条学习行为             |
| 权限     | 所有已登录用户（自动记录）         |

**请求体：**

```json
{
  "action": "string, 必填, 行为类型",
  "target_type": "string, 选填, 目标类型: todo | note | task | bookmark | knowledge | bilibili | file | calendar | ai_chat",
  "target_id": "string, 选填, 目标 ID",
  "metadata": "object, 选填, 附加元数据",
  "page": "string, 选填, 当前页面",
  "timestamp": "string, 选填, 客户端时间戳"
}
```

**行为类型（`action`）枚举：**

| action                 | 说明            |
| ---------------------- | --------------- |
| `login`                | 登录            |
| `logout`               | 退出            |
| `page_view`            | 页面访问        |
| `todo_create`          | 创建 TODO       |
| `todo_complete`        | 完成 TODO       |
| `todo_delete`          | 删除 TODO       |
| `note_create`          | 创建便签        |
| `note_edit`            | 编辑便签        |
| `note_delete`          | 删除便签        |
| `task_view`            | 查看任务        |
| `task_submit`          | 提交任务        |
| `task_complete`        | 完成任务        |
| `announcement_view`    | 查看公告        |
| `calendar_create`      | 创建计划        |
| `calendar_complete`    | 完成计划        |
| `bookmark_visit`       | 访问书签        |
| `file_upload`          | 上传文件        |
| `knowledge_search`     | 知识库搜索      |
| `knowledge_view`       | 知识库文档查看  |
| `ai_chat`              | AI 对话         |
| `bilibili_open`        | 打开B站链接     |
| `bilibili_watch`       | B站学习中       |
| `review_view`          | 查看复盘        |
| `memory_view`          | 查看 memory     |

**成功响应 (201)：**

```json
{
  "code": 0,
  "message": "记录成功",
  "data": {
    "id": "log_001"
  }
}
```

---

### 14.2 批量记录行为

| 项目     | 说明                                   |
| -------- | -------------------------------------- |
| 接口     | `POST /api/v1/behavior-logs/batch`     |
| 描述     | 批量上报行为日志（减少请求次数）       |
| 权限     | 所有已登录用户                         |

**请求体：**

```json
{
  "logs": [
    {
      "action": "string",
      "target_type": "string",
      "target_id": "string",
      "metadata": {},
      "timestamp": "string"
    }
  ]
}
```

**成功响应 (201)：**

```json
{
  "code": 0,
  "message": "批量记录成功",
  "data": {
    "recorded_count": 5
  }
}
```

---

### 14.3 查询行为日志

| 项目     | 说明                                 |
| -------- | ------------------------------------ |
| 接口     | `GET /api/v1/behavior-logs`          |
| 描述     | 查询行为日志列表                     |
| 权限     | **Admin**；**Teacher**（关联学生）   |

**Query 参数：**

| 参数         | 类型      | 必填 | 说明             |
| ------------ | --------- | ---- | ---------------- |
| `page`       | `integer` | 否   | 页码             |
| `page_size`  | `integer` | 否   | 每页条数         |
| `student_id` | `string`  | 否   | 学生 ID          |
| `action`     | `string`  | 否   | 行为类型过滤     |
| `start_date` | `string`  | 否   | 起始日期         |
| `end_date`   | `string`  | 否   | 结束日期         |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "log_001",
        "user_id": "u_001",
        "display_name": "张三",
        "action": "todo_complete",
        "target_type": "todo",
        "target_id": "todo_001",
        "metadata": { "title": "阅读论文" },
        "page": "dashboard",
        "created_at": "2026-06-02T10:30:00+08:00"
      }
    ],
    "total": 200,
    "page": 1,
    "page_size": 20,
    "total_pages": 10
  }
}
```

---

## 十五、学习热力图

> 基础路径：`/api/v1/heatmap`

### 15.1 获取热力图数据

| 项目     | 说明                          |
| -------- | ----------------------------- |
| 接口     | `GET /api/v1/heatmap`         |
| 描述     | 获取学习热力图数据            |
| 权限     | **Student**（本人）；**Teacher**（关联学生）；**Admin** |

**Query 参数：**

| 参数         | 类型     | 必填 | 说明                                           |
| ------------ | -------- | ---- | ---------------------------------------------- |
| `student_id` | `string` | 否   | 学生 ID（老师/管理员查看时必填）               |
| `start_date` | `string` | 必填 | 起始日期，如 `2026-01-01`                      |
| `end_date`   | `string` | 必填 | 结束日期，如 `2026-06-30`                      |
| `dimension`  | `string` | 否   | 统计维度：`total` / `study_time` / `todo` / `task` / `ai_chat` / `knowledge` / `bilibili` / `file`，默认 `total` |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "student_id": "u_001",
    "start_date": "2026-01-01",
    "end_date": "2026-06-30",
    "dimension": "total",
    "days": [
      { "date": "2026-06-01", "level": 3, "value": 180, "details": { "study_minutes": 180, "todos_completed": 3, "tasks_completed": 1, "ai_chats": 5, "knowledge_views": 2, "bilibili_minutes": 30, "files_uploaded": 1 } },
      { "date": "2026-06-02", "level": 2, "value": 120, "details": { ... } },
      { "date": "2026-06-03", "level": 0, "value": 0, "details": { ... } }
    ],
    "level_thresholds": {
      "level_0": "无活动",
      "level_1": "1-30 活跃分",
      "level_2": "31-90 活跃分",
      "level_3": "91-180 活跃分",
      "level_4": "180+ 活跃分"
    },
    "summary": {
      "total_active_days": 120,
      "max_streak": 30,
      "current_streak": 15,
      "avg_daily_value": 85
    }
  }
}
```

---

### 15.2 获取全体热力图概览

| 项目     | 说明                              |
| -------- | --------------------------------- |
| 接口     | `GET /api/v1/heatmap/overview`    |
| 描述     | 获取全体学生的热力图概览          |
| 权限     | **Admin**                         |

**Query 参数：**

| 参数         | 类型     | 必填 | 说明         |
| ------------ | -------- | ---- | ------------ |
| `start_date` | `string` | 必填 | 起始日期     |
| `end_date`   | `string` | 必填 | 结束日期     |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "total_students": 20,
    "active_students_today": 15,
    "students_summary": [
      {
        "user_id": "u_001",
        "display_name": "张三",
        "total_active_days": 120,
        "current_streak": 15,
        "avg_daily_minutes": 150,
        "recent_level": 3
      }
    ]
  }
}
```

---

## 十六、B站资源

> 基础路径：`/api/v1/bilibili`

### 16.1 添加B站资源

| 项目     | 说明                             |
| -------- | -------------------------------- |
| 接口     | `POST /api/v1/bilibili/resources`|
| 描述     | 添加一个B站学习视频资源          |
| 权限     | **Student**；**Teacher**；**Admin** |

**请求体：**

```json
{
  "url": "string, 必填, B站视频链接",
  "title": "string, 选填, 自定义标题（留空则自动解析）",
  "category": "string, 选填, 分类",
  "tags": ["string, 选填, 标签"],
  "description": "string, 选填, 描述"
}
```

**成功响应 (201)：**

```json
{
  "code": 0,
  "message": "添加成功",
  "data": {
    "id": "bili_001",
    "bvid": "BV1xx411c7mD",
    "url": "https://www.bilibili.com/video/BV1xx411c7mD",
    "title": "【机器学习】深入理解 Transformer",
    "cover_url": "https://i0.hdslb.com/...",
    "duration_seconds": 3600,
    "episodes": [
      { "index": 1, "title": "P1 - Attention 机制", "duration_seconds": 1200 },
      { "index": 2, "title": "P2 - Multi-Head Attention", "duration_seconds": 1200 },
      { "index": 3, "title": "P3 - 位置编码", "duration_seconds": 1200 }
    ],
    "category": "机器学习",
    "tags": ["Transformer", "NLP"],
    "added_by": {
      "id": "u_001",
      "display_name": "张三"
    },
    "created_at": "2026-06-02T10:00:00+08:00"
  }
}
```

---

### 16.2 获取B站资源列表

| 项目     | 说明                              |
| -------- | --------------------------------- |
| 接口     | `GET /api/v1/bilibili/resources`  |
| 描述     | 获取B站学习资源列表               |
| 权限     | 所有已登录用户                    |

**Query 参数：**

| 参数        | 类型      | 必填 | 说明               |
| ----------- | --------- | ---- | ------------------ |
| `page`      | `integer` | 否   | 页码               |
| `page_size` | `integer` | 否   | 每页条数           |
| `category`  | `string`  | 否   | 分类过滤           |
| `keyword`   | `string`  | 否   | 关键词搜索         |
| `added_by`  | `string`  | 否   | 添加者 ID 过滤     |

**成功响应 (200)：** 分页格式。

---

### 16.3 获取B站资源详情

| 项目     | 说明                                          |
| -------- | --------------------------------------------- |
| 接口     | `GET /api/v1/bilibili/resources/{resource_id}`|
| 描述     | 获取B站资源详情（含学习记录）                 |
| 权限     | 所有已登录用户                                |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "bili_001",
    "bvid": "BV1xx411c7mD",
    "url": "https://www.bilibili.com/video/BV1xx411c7mD",
    "embed_url": "https://player.bilibili.com/player.html?bvid=BV1xx411c7mD",
    "title": "...",
    "cover_url": "...",
    "duration_seconds": 3600,
    "episodes": [ ... ],
    "category": "机器学习",
    "tags": ["Transformer", "NLP"],
    "my_watch_log": {
      "total_watch_minutes": 45,
      "last_watched_at": "2026-06-01T15:00:00+08:00",
      "completed_episodes": [1],
      "is_completed": false
    }
  }
}
```

---

### 16.4 记录B站观看行为

| 项目     | 说明                                                |
| -------- | --------------------------------------------------- |
| 接口     | `POST /api/v1/bilibili/resources/{resource_id}/watch` |
| 描述     | 记录B站视频观看行为（前端心跳上报）                 |
| 权限     | **Student**                                         |

**请求体：**

```json
{
  "episode_index": "integer, 选填, 当前观看分集序号",
  "watch_duration_seconds": "integer, 必填, 本次观看时长（秒）",
  "is_completed": "boolean, 选填, 是否标记为已完成",
  "timestamp": "string, 必填, 客户端时间戳"
}
```

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "记录成功",
  "data": {
    "total_watch_minutes": 50,
    "session_minutes": 5
  }
}
```

---

### 16.5 更新B站资源

| 项目     | 说明                                              |
| -------- | ------------------------------------------------- |
| 接口     | `PUT /api/v1/bilibili/resources/{resource_id}`    |
| 描述     | 更新B站资源信息                                   |
| 权限     | 添加者本人；**Admin**                             |

**请求体：**

```json
{
  "title": "string, 选填",
  "category": "string, 选填",
  "tags": ["string, 选填"],
  "description": "string, 选填"
}
```

**成功响应 (200)：** 同详情响应。

---

### 16.6 删除B站资源

| 项目     | 说明                                              |
| -------- | ------------------------------------------------- |
| 接口     | `DELETE /api/v1/bilibili/resources/{resource_id}` |
| 描述     | 删除B站资源                                       |
| 权限     | 添加者本人；**Admin**                             |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "删除成功",
  "data": null
}
```

---

## 十七、文件上传

> 基础路径：`/api/v1/files`

### 17.1 上传文件

| 项目     | 说明                           |
| -------- | ------------------------------ |
| 接口     | `POST /api/v1/files/upload`    |
| 描述     | 上传文件到平台                 |
| 权限     | 所有已登录用户                 |

**请求格式：** `multipart/form-data`

**表单字段：**

| 字段       | 类型     | 必填 | 说明                            |
| ---------- | -------- | ---- | ------------------------------- |
| `file`     | `file`   | 是   | 文件                            |
| `category` | `string` | 否   | 文件分类                        |
| `tags`     | `string` | 否   | 标签（JSON 数组字符串）         |
| `purpose`  | `string` | 否   | 用途：`general` / `task_attachment` / `knowledge` / `avatar` |

**成功响应 (201)：**

```json
{
  "code": 0,
  "message": "上传成功",
  "data": {
    "id": "file_001",
    "filename": "论文综述.pdf",
    "original_filename": "论文综述.pdf",
    "mime_type": "application/pdf",
    "size_bytes": 2048000,
    "size_display": "2.0 MB",
    "url": "/api/v1/files/file_001/download",
    "category": "学习资料",
    "tags": ["论文", "NLP"],
    "purpose": "general",
    "uploader": {
      "id": "u_001",
      "display_name": "张三"
    },
    "created_at": "2026-06-02T10:00:00+08:00"
  }
}
```

**错误响应：**

| HTTP 状态码 | 业务错误码 | 说明             |
| ----------- | ---------- | ---------------- |
| `413`       | `41300`    | 文件过大         |
| `422`       | `41301`    | 文件类型不支持   |

---

### 17.2 获取文件列表

| 项目     | 说明                        |
| -------- | --------------------------- |
| 接口     | `GET /api/v1/files`         |
| 描述     | 获取文件列表                |
| 权限     | **Student**（本人上传的）；**Teacher**；**Admin** |

**Query 参数：**

| 参数         | 类型      | 必填 | 说明                        |
| ------------ | --------- | ---- | --------------------------- |
| `page`       | `integer` | 否   | 页码                        |
| `page_size`  | `integer` | 否   | 每页条数                    |
| `category`   | `string`  | 否   | 分类过滤                    |
| `purpose`    | `string`  | 否   | 用途过滤                    |
| `keyword`    | `string`  | 否   | 文件名搜索                  |
| `uploader_id`| `string`  | 否   | 上传者 ID                   |
| `mime_type`  | `string`  | 否   | MIME 类型过滤               |

**成功响应 (200)：** 分页格式。

---

### 17.3 下载文件

| 项目     | 说明                                    |
| -------- | --------------------------------------- |
| 接口     | `GET /api/v1/files/{file_id}/download`  |
| 描述     | 下载指定文件                            |
| 权限     | 所有已登录用户（需有权限访问该文件）    |

**响应：** 文件二进制流，`Content-Disposition: attachment; filename="xxx.pdf"`

---

### 17.4 删除文件

| 项目     | 说明                              |
| -------- | --------------------------------- |
| 接口     | `DELETE /api/v1/files/{file_id}`  |
| 描述     | 删除指定文件                      |
| 权限     | 上传者本人；**Admin**             |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "删除成功",
  "data": null
}
```

---

### 17.5 获取文件详情

| 项目     | 说明                            |
| -------- | ------------------------------- |
| 接口     | `GET /api/v1/files/{file_id}`   |
| 描述     | 获取文件元数据                  |
| 权限     | 所有已登录用户                  |

**成功响应 (200)：** 同上传响应中的 `data` 结构。

---

## 十八、知识库

> 基础路径：`/api/v1/knowledge`

### 18.1 上传知识库文档

| 项目     | 说明                                  |
| -------- | ------------------------------------- |
| 接口     | `POST /api/v1/knowledge/documents`    |
| 描述     | 上传文档到知识库，后台自动解析和向量化 |
| 权限     | 所有已登录用户                        |

**请求格式：** `multipart/form-data`

**表单字段：**

| 字段          | 类型     | 必填 | 说明                               |
| ------------- | -------- | ---- | ---------------------------------- |
| `file`        | `file`   | 是   | 文档文件                           |
| `title`       | `string` | 否   | 自定义标题（留空使用文件名）       |
| `category`    | `string` | 否   | 文档分类                           |
| `tags`        | `string` | 否   | 标签（JSON 数组字符串）            |
| `description` | `string` | 否   | 文档描述                           |
| `access_level`| `string` | 否   | 访问级别：`public` / `restricted` |

**成功响应 (201)：**

```json
{
  "code": 0,
  "message": "文档上传成功，正在后台处理",
  "data": {
    "id": "doc_001",
    "title": "Transformer 论文笔记",
    "filename": "transformer_notes.pdf",
    "category": "论文笔记",
    "tags": ["Transformer", "NLP"],
    "status": "processing",
    "size_bytes": 1024000,
    "uploader": {
      "id": "u_001",
      "display_name": "张三"
    },
    "created_at": "2026-06-02T10:00:00+08:00"
  }
}
```

**文档处理状态（`status`）：**

| 状态          | 说明             |
| ------------- | ---------------- |
| `processing`  | 解析处理中       |
| `ready`       | 处理完成，可用   |
| `failed`      | 处理失败         |

---

### 18.2 获取知识库文档列表

| 项目     | 说明                                |
| -------- | ----------------------------------- |
| 接口     | `GET /api/v1/knowledge/documents`   |
| 描述     | 获取知识库文档列表                  |
| 权限     | 所有已登录用户                      |

**Query 参数：**

| 参数           | 类型      | 必填 | 说明                                   |
| -------------- | --------- | ---- | -------------------------------------- |
| `page`         | `integer` | 否   | 页码                                   |
| `page_size`    | `integer` | 否   | 每页条数                               |
| `category`     | `string`  | 否   | 分类过滤                               |
| `keyword`      | `string`  | 否   | 关键词搜索                             |
| `status`       | `string`  | 否   | 状态过滤：`processing` / `ready` / `failed` |
| `uploader_id`  | `string`  | 否   | 上传者 ID                              |

**成功响应 (200)：** 分页格式。

---

### 18.3 获取文档详情

| 项目     | 说明                                          |
| -------- | --------------------------------------------- |
| 接口     | `GET /api/v1/knowledge/documents/{doc_id}`    |
| 描述     | 获取知识库文档详情                            |
| 权限     | 所有已登录用户（需有访问权限）                |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "doc_001",
    "title": "Transformer 论文笔记",
    "filename": "transformer_notes.pdf",
    "description": "Attention is All You Need 论文详细笔记",
    "category": "论文笔记",
    "tags": ["Transformer", "NLP"],
    "status": "ready",
    "size_bytes": 1024000,
    "chunk_count": 25,
    "summary": "本文档是关于 Transformer 架构的论文笔记...",
    "auto_tags": ["attention", "encoder-decoder", "自注意力"],
    "access_level": "public",
    "download_url": "/api/v1/files/file_kb_001/download",
    "uploader": {
      "id": "u_001",
      "display_name": "张三"
    },
    "created_at": "2026-06-02T10:00:00+08:00",
    "processed_at": "2026-06-02T10:05:00+08:00"
  }
}
```

---

### 18.4 更新文档信息

| 项目     | 说明                                          |
| -------- | --------------------------------------------- |
| 接口     | `PUT /api/v1/knowledge/documents/{doc_id}`    |
| 描述     | 更新知识库文档元信息                          |
| 权限     | 上传者本人；**Admin**                         |

**请求体：**

```json
{
  "title": "string, 选填",
  "category": "string, 选填",
  "tags": ["string, 选填"],
  "description": "string, 选填",
  "access_level": "string, 选填"
}
```

**成功响应 (200)：** 同详情响应。

---

### 18.5 删除知识库文档

| 项目     | 说明                                            |
| -------- | ----------------------------------------------- |
| 接口     | `DELETE /api/v1/knowledge/documents/{doc_id}`   |
| 描述     | 删除知识库文档及其向量数据                      |
| 权限     | 上传者本人；**Admin**                           |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "文档已删除",
  "data": null
}
```

---

### 18.6 知识库语义搜索

| 项目     | 说明                                    |
| -------- | --------------------------------------- |
| 接口     | `POST /api/v1/knowledge/search`         |
| 描述     | 基于向量相似度在知识库中搜索相关内容    |
| 权限     | 所有已登录用户                          |

**请求体：**

```json
{
  "query": "string, 必填, 搜索查询内容",
  "top_k": "integer, 选填, 返回结果数量, 默认 5",
  "category": "string, 选填, 限定分类",
  "score_threshold": "number, 选填, 最低相似度阈值, 默认 0.5"
}
```

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "query": "Transformer 的位置编码是什么",
    "results": [
      {
        "document_id": "doc_001",
        "document_title": "Transformer 论文笔记",
        "chunk_id": "chunk_015",
        "content": "位置编码（Positional Encoding）是 Transformer 中用于表示序列位置信息的关键组件...",
        "score": 0.92,
        "metadata": {
          "page": 5,
          "section": "2.3 位置编码"
        }
      }
    ],
    "total_results": 3
  }
}
```

---

### 18.7 知识库问答

| 项目     | 说明                              |
| -------- | --------------------------------- |
| 接口     | `POST /api/v1/knowledge/qa`       |
| 描述     | 基于知识库内容进行 AI 问答（RAG） |
| 权限     | 所有已登录用户                    |

**请求体：**

```json
{
  "question": "string, 必填, 问题",
  "category": "string, 选填, 限定分类",
  "top_k": "integer, 选填, 检索文档数量, 默认 3",
  "stream": "boolean, 选填, 是否流式返回, 默认 false"
}
```

**非流式成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "answer": "Transformer 中的位置编码使用正弦和余弦函数...",
    "sources": [
      {
        "document_id": "doc_001",
        "document_title": "Transformer 论文笔记",
        "chunk_content": "...",
        "score": 0.92
      }
    ],
    "usage": {
      "prompt_tokens": 500,
      "completion_tokens": 200,
      "total_tokens": 700
    }
  }
}
```

**流式响应：** 遵循 [SSE 流式接口规范](#15-sse-流式接口规范)。

---

### 18.8 获取知识库分类列表

| 项目     | 说明                                    |
| -------- | --------------------------------------- |
| 接口     | `GET /api/v1/knowledge/categories`      |
| 描述     | 获取知识库的文档分类列表                |
| 权限     | 所有已登录用户                          |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "categories": [
      { "name": "论文笔记", "count": 15 },
      { "name": "课程资料", "count": 8 },
      { "name": "项目文档", "count": 5 }
    ]
  }
}
```

---

## 十九、AI 对话

> 基础路径：`/api/v1/ai/chat`

### 19.1 创建对话

| 项目     | 说明                                 |
| -------- | ------------------------------------ |
| 接口     | `POST /api/v1/ai/chat/conversations`|
| 描述     | 创建一个新的 AI 对话会话            |
| 权限     | **Student**                          |

**请求体：**

```json
{
  "title": "string, 选填, 对话标题（留空则自动生成）",
  "type": "string, 选填, 对话类型: general | task_breakdown | plan_generate | knowledge_qa, 默认 general"
}
```

**成功响应 (201)：**

```json
{
  "code": 0,
  "message": "对话创建成功",
  "data": {
    "id": "conv_001",
    "title": "新对话",
    "type": "general",
    "message_count": 0,
    "created_at": "2026-06-02T10:00:00+08:00",
    "updated_at": "2026-06-02T10:00:00+08:00"
  }
}
```

---

### 19.2 获取对话列表

| 项目     | 说明                                 |
| -------- | ------------------------------------ |
| 接口     | `GET /api/v1/ai/chat/conversations` |
| 描述     | 获取当前用户的对话列表              |
| 权限     | **Student**                          |

**Query 参数：**

| 参数        | 类型      | 必填 | 说明                     |
| ----------- | --------- | ---- | ------------------------ |
| `page`      | `integer` | 否   | 页码                     |
| `page_size` | `integer` | 否   | 每页条数                 |
| `type`      | `string`  | 否   | 对话类型过滤             |
| `keyword`   | `string`  | 否   | 标题搜索                 |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "conv_001",
        "title": "关于 Transformer 的讨论",
        "type": "general",
        "message_count": 12,
        "last_message_preview": "好的，我来帮你整理一下...",
        "created_at": "2026-06-02T10:00:00+08:00",
        "updated_at": "2026-06-02T11:30:00+08:00"
      }
    ],
    "total": 5,
    "page": 1,
    "page_size": 20,
    "total_pages": 1
  }
}
```

---

### 19.3 获取对话历史消息

| 项目     | 说明                                                      |
| -------- | --------------------------------------------------------- |
| 接口     | `GET /api/v1/ai/chat/conversations/{conversation_id}/messages` |
| 描述     | 获取指定对话的历史消息列表                                |
| 权限     | **Student**（仅本人的对话）                               |

**Query 参数：**

| 参数        | 类型      | 必填 | 说明                                 |
| ----------- | --------- | ---- | ------------------------------------ |
| `page`      | `integer` | 否   | 页码                                 |
| `page_size` | `integer` | 否   | 每页条数，默认 50                    |
| `before_id` | `string`  | 否   | 获取此消息 ID 之前的消息（向上翻页） |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "msg_001",
        "role": "user",
        "content": "Transformer 的自注意力机制是怎么工作的？",
        "created_at": "2026-06-02T10:00:00+08:00"
      },
      {
        "id": "msg_002",
        "role": "assistant",
        "content": "自注意力机制（Self-Attention）是 Transformer 的核心组件...",
        "usage": {
          "prompt_tokens": 120,
          "completion_tokens": 300,
          "total_tokens": 420
        },
        "created_at": "2026-06-02T10:00:05+08:00"
      }
    ],
    "total": 12,
    "page": 1,
    "page_size": 50,
    "total_pages": 1
  }
}
```

---

### 19.4 发送消息（流式）

| 项目     | 说明                                                      |
| -------- | --------------------------------------------------------- |
| 接口     | `POST /api/v1/ai/chat/conversations/{conversation_id}/messages` |
| 描述     | 向 AI 智能体发送消息，返回 SSE 流式响应                  |
| 权限     | **Student**（仅本人的对话）                               |

**请求头：**

```
Content-Type: application/json
Authorization: Bearer <access_token>
Accept: text/event-stream
```

**请求体：**

```json
{
  "content": "string, 必填, 用户消息内容",
  "context_options": {
    "include_memory": "boolean, 选填, 是否注入 memory 上下文, 默认 true",
    "include_todos": "boolean, 选填, 是否注入 TODO 上下文, 默认 false",
    "include_tasks": "boolean, 选填, 是否注入任务上下文, 默认 false",
    "include_calendar": "boolean, 选填, 是否注入日历上下文, 默认 false",
    "include_knowledge": "boolean, 选填, 是否检索知识库, 默认 false",
    "knowledge_query": "string, 选填, 知识库检索查询（留空则使用消息内容）"
  }
}
```

**响应格式：** SSE 流式，遵循 [SSE 流式接口规范](#15-sse-流式接口规范)。

```
event: message
data: {"type": "content", "content": "自注意力", "conversation_id": "conv_001", "message_id": "msg_003"}

event: message
data: {"type": "content", "content": "机制是", "conversation_id": "conv_001", "message_id": "msg_003"}

event: message
data: {"type": "done", "content": "", "message_id": "msg_003", "conversation_id": "conv_001", "usage": {"prompt_tokens": 500, "completion_tokens": 300, "total_tokens": 800}}

```

**错误响应：**

| HTTP 状态码 | 业务错误码 | 说明                 |
| ----------- | ---------- | -------------------- |
| `429`       | `42901`    | AI 调用频率超限      |
| `429`       | `42902`    | AI 每日额度已用完    |
| `500`       | `50002`    | AI 模型调用失败      |

---

### 19.5 更新对话标题

| 项目     | 说明                                                   |
| -------- | ------------------------------------------------------ |
| 接口     | `PATCH /api/v1/ai/chat/conversations/{conversation_id}`|
| 描述     | 更新对话标题                                           |
| 权限     | **Student**（仅本人的对话）                            |

**请求体：**

```json
{
  "title": "string, 必填, 新标题"
}
```

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "标题已更新",
  "data": {
    "id": "conv_001",
    "title": "Transformer 学习讨论"
  }
}
```

---

### 19.6 删除对话

| 项目     | 说明                                                    |
| -------- | ------------------------------------------------------- |
| 接口     | `DELETE /api/v1/ai/chat/conversations/{conversation_id}`|
| 描述     | 删除指定对话及其所有消息                                |
| 权限     | **Student**（仅本人的对话）                             |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "对话已删除",
  "data": null
}
```

---

## 二十、Memory

> 基础路径：`/api/v1/ai/memory`

### 20.1 获取学生 Memory

| 项目     | 说明                                           |
| -------- | ---------------------------------------------- |
| 接口     | `GET /api/v1/ai/memory/{student_id}`           |
| 描述     | 获取学生的 memory 信息                         |
| 权限     | **Student**（本人，部分可见）；**Teacher**（教学摘要）；**Admin**（日志） |

**Query 参数：**

| 参数    | 类型     | 必填 | 说明                                         |
| ------- | -------- | ---- | -------------------------------------------- |
| `layer` | `string` | 否   | Memory 层级：`short_term` / `long_term` / `all`，默认 `all` |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "student_id": "u_001",
    "short_term": [
      {
        "id": "mem_001",
        "content": "最近正在准备机器学习期末考试",
        "confidence": 0.85,
        "source": "daily_review",
        "evidence_count": 3,
        "created_at": "2026-06-01T00:05:00+08:00",
        "updated_at": "2026-06-02T00:05:00+08:00",
        "expires_at": "2026-06-15T00:00:00+08:00"
      }
    ],
    "long_term": [
      {
        "id": "mem_010",
        "content": "偏好通过视频入门新概念，再通过论文深入",
        "confidence": 0.92,
        "source": "behavior_analysis",
        "evidence_count": 15,
        "created_at": "2026-03-15T00:05:00+08:00",
        "updated_at": "2026-06-01T00:05:00+08:00",
        "expires_at": null
      }
    ],
    "last_updated_at": "2026-06-02T00:05:00+08:00"
  }
}
```

---

### 20.2 申请删除 Memory 条目

| 项目     | 说明                                                |
| -------- | --------------------------------------------------- |
| 接口     | `DELETE /api/v1/ai/memory/{student_id}/{memory_id}` |
| 描述     | 学生申请删除不准确的 memory 条目                    |
| 权限     | **Student**（仅本人）；**Admin**                    |

**请求体：**

```json
{
  "reason": "string, 选填, 申请删除原因"
}
```

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "Memory 条目已删除",
  "data": null
}
```

---

### 20.3 获取 Memory 更新日志

| 项目     | 说明                                              |
| -------- | ------------------------------------------------- |
| 接口     | `GET /api/v1/ai/memory/{student_id}/update-logs`  |
| 描述     | 获取 memory 更新历史记录                          |
| 权限     | **Admin**；**Student**（本人）                    |

**Query 参数：**

| 参数         | 类型      | 必填 | 说明         |
| ------------ | --------- | ---- | ------------ |
| `page`       | `integer` | 否   | 页码         |
| `page_size`  | `integer` | 否   | 每页条数     |
| `start_date` | `string`  | 否   | 起始日期     |
| `end_date`   | `string`  | 否   | 结束日期     |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "mem_log_001",
        "action": "create",
        "memory_id": "mem_001",
        "content": "最近正在准备机器学习期末考试",
        "layer": "short_term",
        "confidence": 0.85,
        "source": "daily_review",
        "review_date": "2026-06-01",
        "created_at": "2026-06-02T00:05:00+08:00"
      }
    ],
    "total": 30,
    "page": 1,
    "page_size": 20,
    "total_pages": 2
  }
}
```

---

## 二十一、每日复盘

> 基础路径：`/api/v1/reviews`

### 21.1 获取每日复盘

| 项目     | 说明                                |
| -------- | ----------------------------------- |
| 接口     | `GET /api/v1/reviews/{date}`        |
| 描述     | 获取指定日期的每日复盘报告          |
| 权限     | **Student**（本人）；**Teacher**（关联学生摘要）；**Admin** |

**路径参数：**

| 参数   | 类型     | 说明                        |
| ------ | -------- | --------------------------- |
| `date` | `string` | 日期，如 `2026-06-01`      |

**Query 参数：**

| 参数         | 类型     | 必填 | 说明                                  |
| ------------ | -------- | ---- | ------------------------------------- |
| `student_id` | `string` | 否   | 学生 ID（老师/管理员查看时必填）      |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "review_001",
    "student_id": "u_001",
    "date": "2026-06-01",
    "summary": "## 昨日学习总结\n\n今天学习状态良好...",
    "study_time_minutes": 180,
    "metrics": {
      "todos_created": 3,
      "todos_completed": 2,
      "tasks_completed": 1,
      "tasks_submitted": 0,
      "ai_chat_count": 5,
      "knowledge_views": 2,
      "bilibili_watch_minutes": 30,
      "files_uploaded": 1,
      "calendar_events_completed": 2
    },
    "highlights": [
      "完成了 Transformer 论文阅读任务",
      "在知识库中搜索了 3 次相关内容"
    ],
    "concerns": [
      "有 1 个任务即将逾期"
    ],
    "suggestions": [
      "建议今天优先处理即将逾期的任务",
      "可以继续深入学习 Multi-Head Attention 的实现"
    ],
    "new_memories": [
      {
        "content": "学生对 Transformer 架构理解在加深",
        "layer": "short_term",
        "confidence": 0.8
      }
    ],
    "generated_at": "2026-06-02T00:05:00+08:00"
  }
}
```

**错误响应：**

| HTTP 状态码 | 业务错误码 | 说明             |
| ----------- | ---------- | ---------------- |
| `404`       | `40415`    | 该日期无复盘记录 |

---

### 21.2 获取复盘列表

| 项目     | 说明                          |
| -------- | ----------------------------- |
| 接口     | `GET /api/v1/reviews`         |
| 描述     | 获取复盘记录列表              |
| 权限     | **Student**（本人）；**Teacher**（关联学生）；**Admin** |

**Query 参数：**

| 参数         | 类型      | 必填 | 说明                       |
| ------------ | --------- | ---- | -------------------------- |
| `page`       | `integer` | 否   | 页码                       |
| `page_size`  | `integer` | 否   | 每页条数                   |
| `student_id` | `string`  | 否   | 学生 ID                    |
| `start_date` | `string`  | 否   | 起始日期                   |
| `end_date`   | `string`  | 否   | 结束日期                   |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "review_001",
        "date": "2026-06-01",
        "study_time_minutes": 180,
        "summary_preview": "今天学习状态良好，完成了论文阅读任务...",
        "concern_count": 1,
        "generated_at": "2026-06-02T00:05:00+08:00"
      }
    ],
    "total": 60,
    "page": 1,
    "page_size": 20,
    "total_pages": 3
  }
}
```

---

### 21.3 手动触发复盘生成

| 项目     | 说明                                        |
| -------- | ------------------------------------------- |
| 接口     | `POST /api/v1/reviews/generate`             |
| 描述     | 手动触发为指定学生生成复盘（用于补生成）    |
| 权限     | **Admin**                                   |

**请求体：**

```json
{
  "student_id": "string, 必填, 学生 ID",
  "date": "string, 必填, 需要复盘的日期"
}
```

**成功响应 (202)：**

```json
{
  "code": 0,
  "message": "复盘生成任务已提交",
  "data": {
    "task_id": "celery_task_001",
    "student_id": "u_001",
    "date": "2026-06-01"
  }
}
```

---

## 二十二、通知

> 基础路径：`/api/v1/notifications`

### 22.1 获取通知列表

| 项目     | 说明                              |
| -------- | --------------------------------- |
| 接口     | `GET /api/v1/notifications`       |
| 描述     | 获取当前用户的通知列表            |
| 权限     | 所有已登录用户                    |

**Query 参数：**

| 参数        | 类型      | 必填 | 说明                                                                                   |
| ----------- | --------- | ---- | -------------------------------------------------------------------------------------- |
| `page`      | `integer` | 否   | 页码                                                                                   |
| `page_size` | `integer` | 否   | 每页条数                                                                               |
| `is_read`   | `boolean` | 否   | 已读状态过滤                                                                           |
| `category`  | `string`  | 否   | 类型过滤：`announcement` / `task` / `review` / `system` / `reminder` / `file` |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "notif_001",
        "title": "新任务通知",
        "content": "王教授发布了新任务：完成论文综述初稿",
        "category": "task",
        "is_read": false,
        "related_type": "task",
        "related_id": "task_001",
        "created_at": "2026-06-02T10:00:00+08:00"
      }
    ],
    "total": 30,
    "unread_count": 5,
    "page": 1,
    "page_size": 20,
    "total_pages": 2
  }
}
```

---

### 22.2 获取未读通知数量

| 项目     | 说明                                    |
| -------- | --------------------------------------- |
| 接口     | `GET /api/v1/notifications/unread-count`|
| 描述     | 获取未读通知数量（轮询或初始加载用）    |
| 权限     | 所有已登录用户                          |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "unread_count": 5,
    "by_category": {
      "announcement": 2,
      "task": 2,
      "review": 1,
      "system": 0
    }
  }
}
```

---

### 22.3 标记通知已读

| 项目     | 说明                                                  |
| -------- | ----------------------------------------------------- |
| 接口     | `PATCH /api/v1/notifications/{notification_id}/read`  |
| 描述     | 标记单条通知为已读                                    |
| 权限     | 所有已登录用户（仅本人的通知）                        |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "已标记为已读",
  "data": null
}
```

---

### 22.4 全部标记已读

| 项目     | 说明                                        |
| -------- | ------------------------------------------- |
| 接口     | `POST /api/v1/notifications/read-all`       |
| 描述     | 将所有未读通知标记为已读                    |
| 权限     | 所有已登录用户                              |

**请求体（可选）：**

```json
{
  "category": "string, 选填, 仅标记指定类型的通知"
}
```

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "全部已标记为已读",
  "data": {
    "marked_count": 5
  }
}
```

---

### 22.5 删除通知

| 项目     | 说明                                            |
| -------- | ----------------------------------------------- |
| 接口     | `DELETE /api/v1/notifications/{notification_id}`|
| 描述     | 删除指定通知                                    |
| 权限     | 所有已登录用户（仅本人的通知）                  |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "删除成功",
  "data": null
}
```

---

## 二十三、模型配置

> 基础路径：`/api/v1/admin/llm-configs`

### 23.1 创建模型配置

| 项目     | 说明                                  |
| -------- | ------------------------------------- |
| 接口     | `POST /api/v1/admin/llm-configs`      |
| 描述     | 创建一个新的 LLM Provider 配置       |
| 权限     | **Admin**                             |

**请求体：**

```json
{
  "provider_name": "string, 必填, 提供商名称, 如 siliconflow",
  "display_name": "string, 必填, 显示名称, 如 硅基流动",
  "base_url": "string, 必填, API 基础 URL",
  "api_key": "string, 必填, API Key",
  "model_name": "string, 必填, 模型名称",
  "task_type": "string, 必填, 任务类型: student_chat | daily_review | memory_extract | task_breakdown | plan_generate | knowledge_qa | document_summary | teacher_assistant | system_summary | embedding",
  "priority": "integer, 选填, 优先级（数字越小优先级越高）, 默认 10",
  "enabled": "boolean, 选填, 是否启用, 默认 true",
  "daily_quota": "integer, 选填, 每日调用上限, -1 为不限",
  "rpm_limit": "integer, 选填, 每分钟请求数限制",
  "tpm_limit": "integer, 选填, 每分钟 Token 数限制",
  "fallback_provider_id": "string, 选填, 降级时使用的 provider ID",
  "extra_config": "object, 选填, 额外配置（如 temperature, max_tokens）"
}
```

**成功响应 (201)：**

```json
{
  "code": 0,
  "message": "配置创建成功",
  "data": {
    "id": "llm_001",
    "provider_name": "siliconflow",
    "display_name": "硅基流动",
    "base_url": "https://api.siliconflow.cn/v1",
    "model_name": "Qwen/Qwen2.5-7B-Instruct",
    "task_type": "student_chat",
    "priority": 1,
    "enabled": true,
    "daily_quota": 1000,
    "used_today": 0,
    "rpm_limit": 60,
    "tpm_limit": 100000,
    "fallback_provider_id": null,
    "created_at": "2026-06-02T10:00:00+08:00"
  }
}
```

> **注意：** 响应中不返回 `api_key`，仅在创建和更新时接受输入。

---

### 23.2 获取模型配置列表

| 项目     | 说明                                  |
| -------- | ------------------------------------- |
| 接口     | `GET /api/v1/admin/llm-configs`       |
| 描述     | 获取所有 LLM Provider 配置           |
| 权限     | **Admin**                             |

**Query 参数：**

| 参数        | 类型      | 必填 | 说明                 |
| ----------- | --------- | ---- | -------------------- |
| `task_type` | `string`  | 否   | 按任务类型过滤       |
| `enabled`   | `boolean` | 否   | 按启用状态过滤       |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "llm_001",
        "provider_name": "siliconflow",
        "display_name": "硅基流动",
        "base_url": "https://api.siliconflow.cn/v1",
        "api_key_masked": "sk-****abcd",
        "model_name": "Qwen/Qwen2.5-7B-Instruct",
        "task_type": "student_chat",
        "priority": 1,
        "enabled": true,
        "daily_quota": 1000,
        "used_today": 250,
        "rpm_limit": 60,
        "tpm_limit": 100000,
        "fallback_provider_id": "llm_002",
        "created_at": "2026-06-02T10:00:00+08:00",
        "updated_at": "2026-06-02T10:00:00+08:00"
      }
    ]
  }
}
```

---

### 23.3 更新模型配置

| 项目     | 说明                                          |
| -------- | --------------------------------------------- |
| 接口     | `PUT /api/v1/admin/llm-configs/{config_id}`   |
| 描述     | 更新模型配置                                  |
| 权限     | **Admin**                                     |

**请求体：** 同创建请求（所有字段可选）。

**成功响应 (200)：** 同创建响应。

---

### 23.4 删除模型配置

| 项目     | 说明                                            |
| -------- | ----------------------------------------------- |
| 接口     | `DELETE /api/v1/admin/llm-configs/{config_id}`  |
| 描述     | 删除模型配置                                    |
| 权限     | **Admin**                                       |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "配置已删除",
  "data": null
}
```

---

### 23.5 测试模型连接

| 项目     | 说明                                                |
| -------- | --------------------------------------------------- |
| 接口     | `POST /api/v1/admin/llm-configs/{config_id}/test`   |
| 描述     | 测试模型配置是否可正常连接                          |
| 权限     | **Admin**                                           |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "连接测试成功",
  "data": {
    "status": "success",
    "latency_ms": 320,
    "model_response": "Hello! I'm working correctly.",
    "tested_at": "2026-06-02T11:00:00+08:00"
  }
}
```

**失败响应 (200)：**

```json
{
  "code": 50002,
  "message": "连接测试失败",
  "data": {
    "status": "failed",
    "error": "API Key 无效或已过期",
    "tested_at": "2026-06-02T11:00:00+08:00"
  }
}
```

---

### 23.6 重置每日用量

| 项目     | 说明                                                      |
| -------- | --------------------------------------------------------- |
| 接口     | `POST /api/v1/admin/llm-configs/{config_id}/reset-usage`  |
| 描述     | 手动重置某个 provider 的每日用量计数                      |
| 权限     | **Admin**                                                 |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "用量已重置",
  "data": {
    "used_today": 0
  }
}
```

---

## 二十四、系统管理

> 基础路径：`/api/v1/admin/system`

### 24.1 获取系统日志

| 项目     | 说明                                  |
| -------- | ------------------------------------- |
| 接口     | `GET /api/v1/admin/system/logs`       |
| 描述     | 获取系统运行日志                      |
| 权限     | **Admin**                             |

**Query 参数：**

| 参数         | 类型      | 必填 | 说明                                                   |
| ------------ | --------- | ---- | ------------------------------------------------------ |
| `page`       | `integer` | 否   | 页码                                                   |
| `page_size`  | `integer` | 否   | 每页条数                                               |
| `level`      | `string`  | 否   | 日志级别：`debug` / `info` / `warning` / `error`       |
| `module`     | `string`  | 否   | 模块过滤：`auth` / `ai` / `task` / `knowledge` / `system` |
| `start_date` | `string`  | 否   | 起始日期                                               |
| `end_date`   | `string`  | 否   | 结束日期                                               |
| `keyword`    | `string`  | 否   | 关键词搜索                                             |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "slog_001",
        "level": "info",
        "module": "auth",
        "message": "用户 zhangsan 登录成功",
        "details": { "ip": "192.168.1.100", "user_agent": "..." },
        "created_at": "2026-06-02T10:00:00+08:00"
      }
    ],
    "total": 500,
    "page": 1,
    "page_size": 20,
    "total_pages": 25
  }
}
```

---

### 24.2 获取 AI 调用日志

| 项目     | 说明                                      |
| -------- | ----------------------------------------- |
| 接口     | `GET /api/v1/admin/system/ai-logs`        |
| 描述     | 获取 AI 模型调用日志                      |
| 权限     | **Admin**                                 |

**Query 参数：**

| 参数            | 类型      | 必填 | 说明               |
| --------------- | --------- | ---- | ------------------ |
| `page`          | `integer` | 否   | 页码               |
| `page_size`     | `integer` | 否   | 每页条数           |
| `provider_name` | `string`  | 否   | 提供商过滤         |
| `task_type`     | `string`  | 否   | 任务类型过滤       |
| `status`        | `string`  | 否   | `success` / `failed` |
| `student_id`    | `string`  | 否   | 学生 ID 过滤       |
| `start_date`    | `string`  | 否   | 起始日期           |
| `end_date`      | `string`  | 否   | 结束日期           |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "ai_log_001",
        "provider_name": "siliconflow",
        "model_name": "Qwen/Qwen2.5-7B-Instruct",
        "task_type": "student_chat",
        "user_id": "u_001",
        "display_name": "张三",
        "status": "success",
        "prompt_tokens": 500,
        "completion_tokens": 300,
        "total_tokens": 800,
        "latency_ms": 1200,
        "error_message": null,
        "created_at": "2026-06-02T10:00:05+08:00"
      }
    ],
    "total": 1000,
    "page": 1,
    "page_size": 20,
    "total_pages": 50
  }
}
```

---

### 24.3 获取系统统计概览

| 项目     | 说明                                  |
| -------- | ------------------------------------- |
| 接口     | `GET /api/v1/admin/system/stats`      |
| 描述     | 获取系统整体运行统计数据              |
| 权限     | **Admin**                             |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "users": {
      "total": 25,
      "students": 20,
      "teachers": 4,
      "admins": 1,
      "active": 22,
      "disabled": 3
    },
    "today": {
      "active_users": 15,
      "new_todos": 30,
      "completed_todos": 20,
      "new_tasks": 5,
      "ai_calls": 150,
      "ai_calls_failed": 2,
      "files_uploaded": 8,
      "study_time_total_minutes": 1800
    },
    "storage": {
      "files_count": 200,
      "files_size_bytes": 5368709120,
      "files_size_display": "5.0 GB",
      "knowledge_docs": 50,
      "knowledge_chunks": 1250
    },
    "system": {
      "uptime_hours": 720,
      "db_size_bytes": 1073741824,
      "db_size_display": "1.0 GB",
      "redis_memory_bytes": 134217728,
      "redis_memory_display": "128 MB",
      "scheduler_status": "running",
      "worker_status": "running"
    }
  }
}
```

---

### 24.4 获取/更新系统设置

| 项目     | 说明                                      |
| -------- | ----------------------------------------- |
| 接口     | `GET /api/v1/admin/system/settings`       |
| 描述     | 获取系统配置                              |
| 权限     | **Admin**                                 |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "platform_name": "AI 伴学平台",
    "registration_enabled": false,
    "max_file_size_mb": 50,
    "allowed_file_types": [".pdf", ".doc", ".docx", ".md", ".txt", ".jpg", ".png"],
    "heartbeat_interval_seconds": 60,
    "daily_review_cron": "0 0 * * *",
    "ai_daily_quota_per_student": 100,
    "ai_rate_limit_rpm": 10,
    "notification_channels": {
      "email_enabled": true,
      "webhook_enabled": false,
      "browser_push_enabled": true
    },
    "backup": {
      "auto_backup_enabled": true,
      "backup_cron": "0 3 * * *",
      "backup_retention_days": 30
    }
  }
}
```

---

| 项目     | 说明                                      |
| -------- | ----------------------------------------- |
| 接口     | `PUT /api/v1/admin/system/settings`       |
| 描述     | 更新系统配置                              |
| 权限     | **Admin**                                 |

**请求体：** 同获取响应中的 `data` 结构（所有字段可选）。

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "设置已更新",
  "data": { ... }
}
```

---

### 24.5 获取定时任务状态

| 项目     | 说明                                          |
| -------- | --------------------------------------------- |
| 接口     | `GET /api/v1/admin/system/scheduled-tasks`    |
| 描述     | 获取定时任务（如每日复盘）的执行状态          |
| 权限     | **Admin**                                     |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "tasks": [
      {
        "name": "daily_review",
        "display_name": "每日复盘生成",
        "cron": "0 0 * * *",
        "status": "idle",
        "last_run_at": "2026-06-02T00:00:05+08:00",
        "last_run_result": "success",
        "last_run_duration_seconds": 120,
        "next_run_at": "2026-06-03T00:00:00+08:00",
        "processed_students": 20,
        "failed_students": 0
      },
      {
        "name": "ai_quota_reset",
        "display_name": "AI 额度重置",
        "cron": "0 0 * * *",
        "status": "idle",
        "last_run_at": "2026-06-02T00:00:01+08:00",
        "last_run_result": "success",
        "next_run_at": "2026-06-03T00:00:00+08:00"
      }
    ]
  }
}
```

---

## 二十五、数据统计

> 基础路径：`/api/v1/stats`

### 25.1 学生统计数据

| 项目     | 说明                              |
| -------- | --------------------------------- |
| 接口     | `GET /api/v1/stats/student`       |
| 描述     | 获取学生个人统计数据              |
| 权限     | **Student**（本人）               |

**Query 参数：**

| 参数     | 类型     | 必填 | 说明                                       |
| -------- | -------- | ---- | ------------------------------------------ |
| `period` | `string` | 否   | 统计周期：`today` / `week` / `month` / `all` |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "study_time": {
      "today_minutes": 125,
      "week_minutes": 840,
      "month_minutes": 3600,
      "total_minutes": 18000
    },
    "todos": {
      "today_completed": 3,
      "today_total": 5,
      "week_completed": 20,
      "total_completed": 150,
      "completion_rate": 0.85
    },
    "tasks": {
      "pending": 2,
      "in_progress": 1,
      "completed": 15,
      "overdue": 1,
      "week_completion_rate": 0.85,
      "total_completion_rate": 0.90
    },
    "ai_chat": {
      "today_count": 5,
      "week_count": 30,
      "total_count": 200,
      "total_conversations": 15
    },
    "knowledge": {
      "today_views": 2,
      "week_views": 10,
      "total_views": 80,
      "documents_uploaded": 5
    },
    "bilibili": {
      "today_minutes": 30,
      "week_minutes": 120,
      "total_minutes": 600,
      "resources_watched": 10
    },
    "streak": {
      "current_days": 15,
      "max_days": 30,
      "total_active_days": 120
    },
    "files": {
      "uploaded_count": 15,
      "total_size_display": "120 MB"
    }
  }
}
```

---

### 25.2 老师统计数据

| 项目     | 说明                              |
| -------- | --------------------------------- |
| 接口     | `GET /api/v1/stats/teacher`       |
| 描述     | 获取老师端统计数据                |
| 权限     | **Teacher**                       |

**Query 参数：**

| 参数     | 类型     | 必填 | 说明                                       |
| -------- | -------- | ---- | ------------------------------------------ |
| `period` | `string` | 否   | 统计周期：`today` / `week` / `month` / `all` |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "students": {
      "total": 20,
      "active_today": 15,
      "active_week": 18,
      "inactive_3_days": 2
    },
    "tasks": {
      "total_created": 30,
      "active": 10,
      "completion_rate": 0.78,
      "overdue_count": 3,
      "avg_completion_days": 5.2
    },
    "announcements": {
      "total_published": 15,
      "avg_read_rate": 0.82
    },
    "study_time_ranking": [
      { "rank": 1, "user_id": "u_001", "display_name": "张三", "week_minutes": 840 },
      { "rank": 2, "user_id": "u_002", "display_name": "李四", "week_minutes": 720 }
    ],
    "concern_students": [
      {
        "user_id": "u_010",
        "display_name": "钱七",
        "reason": "连续3天未登录",
        "last_active_at": "2026-05-30T15:00:00+08:00"
      }
    ],
    "knowledge_usage": {
      "total_documents": 50,
      "week_views": 80,
      "most_viewed_doc": {
        "id": "doc_001",
        "title": "Transformer 论文笔记",
        "view_count": 25
      }
    },
    "review_stats": {
      "generated_today": 18,
      "failed_today": 2,
      "total_generated": 360
    }
  }
}
```

---

### 25.3 管理员统计数据

| 项目     | 说明                              |
| -------- | --------------------------------- |
| 接口     | `GET /api/v1/stats/admin`         |
| 描述     | 获取管理员端系统统计数据          |
| 权限     | **Admin**                         |

**Query 参数：**

| 参数     | 类型     | 必填 | 说明                                       |
| -------- | -------- | ---- | ------------------------------------------ |
| `period` | `string` | 否   | 统计周期：`today` / `week` / `month` / `all` |

**成功响应 (200)：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "users": {
      "total": 25,
      "students": 20,
      "teachers": 4,
      "admins": 1,
      "active_today": 15,
      "new_this_week": 2
    },
    "content": {
      "total_files": 200,
      "total_storage_display": "5.0 GB",
      "knowledge_documents": 50,
      "knowledge_chunks": 1250,
      "total_tasks": 30,
      "total_announcements": 15
    },
    "ai": {
      "total_calls_today": 150,
      "total_calls_week": 1050,
      "failed_calls_today": 2,
      "total_tokens_today": 120000,
      "avg_latency_ms": 800,
      "by_provider": [
        {
          "provider_name": "siliconflow",
          "calls_today": 145,
          "tokens_today": 115000,
          "failed_today": 1
        }
      ],
      "by_task_type": [
        { "task_type": "student_chat", "calls_today": 100 },
        { "task_type": "daily_review", "calls_today": 20 },
        { "task_type": "knowledge_qa", "calls_today": 15 }
      ]
    },
    "system": {
      "uptime_display": "30 天 0 小时",
      "db_size_display": "1.0 GB",
      "redis_memory_display": "128 MB",
      "scheduler_status": "running",
      "worker_status": "running",
      "last_backup_at": "2026-06-02T03:00:00+08:00"
    },
    "trends": {
      "daily_active_users_7d": [
        { "date": "2026-05-27", "count": 12 },
        { "date": "2026-05-28", "count": 14 },
        { "date": "2026-05-29", "count": 13 },
        { "date": "2026-05-30", "count": 16 },
        { "date": "2026-05-31", "count": 11 },
        { "date": "2026-06-01", "count": 15 },
        { "date": "2026-06-02", "count": 15 }
      ],
      "ai_calls_7d": [
        { "date": "2026-05-27", "count": 120 },
        { "date": "2026-05-28", "count": 150 },
        { "date": "2026-05-29", "count": 140 },
        { "date": "2026-05-30", "count": 160 },
        { "date": "2026-05-31", "count": 100 },
        { "date": "2026-06-01", "count": 155 },
        { "date": "2026-06-02", "count": 150 }
      ]
    }
  }
}
```

---

### 25.4 获取学生学习详情（老师/管理员视角）

| 项目     | 说明                                          |
| -------- | --------------------------------------------- |
| 接口     | `GET /api/v1/stats/student/{student_id}`      |
| 描述     | 获取指定学生的详细学习统计                    |
| 权限     | **Teacher**（关联学生）；**Admin**            |

**Query 参数：**

| 参数     | 类型     | 必填 | 说明         |
| -------- | -------- | ---- | ------------ |
| `period` | `string` | 否   | 统计周期     |

**成功响应 (200)：** 结构同学生统计数据（25.1），额外包含学生基本信息。

---

## 附录：接口总览

### 认证模块 `/api/v1/auth`

| 方法   | 路径                        | 说明               | 权限          |
| ------ | --------------------------- | ------------------ | ------------- |
| POST   | `/auth/login`               | 用户登录           | 无需认证      |
| POST   | `/auth/logout`              | 用户退出           | 所有用户      |
| POST   | `/auth/refresh`             | 刷新 Token         | 无需认证      |
| PUT    | `/auth/password`            | 修改密码           | 所有用户      |
| GET    | `/auth/me`                  | 获取当前用户信息   | 所有用户      |

### 用户管理 `/api/v1/users`

| 方法   | 路径                              | 说明             | 权限          |
| ------ | --------------------------------- | ---------------- | ------------- |
| POST   | `/users`                          | 创建用户         | Admin         |
| GET    | `/users`                          | 获取用户列表     | Admin/Teacher |
| GET    | `/users/{user_id}`                | 获取用户详情     | Admin/Teacher/本人 |
| PUT    | `/users/{user_id}`                | 更新用户信息     | Admin/本人    |
| PATCH  | `/users/{user_id}/status`         | 启用/禁用账号    | Admin         |
| POST   | `/users/{user_id}/reset-password` | 重置密码         | Admin         |
| DELETE | `/users/{user_id}`                | 删除用户         | Admin         |
| POST   | `/users/batch`                    | 批量创建用户     | Admin         |

### 学生档案 `/api/v1/students`

| 方法   | 路径                                  | 说明             | 权限                |
| ------ | ------------------------------------- | ---------------- | ------------------- |
| GET    | `/students`                           | 获取学生列表     | Admin/Teacher       |
| GET    | `/students/{student_id}/profile`      | 获取学生档案     | Admin/Teacher/本人  |
| PUT    | `/students/{student_id}/profile`      | 更新学生档案     | Admin/本人          |

### 仪表盘 `/api/v1/dashboard`

| 方法   | 路径                         | 说明               | 权限      |
| ------ | ---------------------------- | ------------------ | --------- |
| GET    | `/dashboard/layout`          | 获取布局配置       | Student   |
| PUT    | `/dashboard/layout`          | 保存布局配置       | Student   |
| POST   | `/dashboard/layout/reset`    | 重置布局           | Student   |
| GET    | `/dashboard/data`            | 获取聚合数据       | Student   |

### TODO `/api/v1/todos`

| 方法   | 路径                          | 说明             | 权限      |
| ------ | ----------------------------- | ---------------- | --------- |
| POST   | `/todos`                      | 创建 TODO        | Student   |
| GET    | `/todos`                      | 获取列表         | Student   |
| GET    | `/todos/{todo_id}`            | 获取详情         | Student   |
| PUT    | `/todos/{todo_id}`            | 更新 TODO        | Student   |
| PATCH  | `/todos/{todo_id}/status`     | 标记完成/未完成  | Student   |
| DELETE | `/todos/{todo_id}`            | 删除 TODO        | Student   |

### 便签 `/api/v1/notes`

| 方法   | 路径                          | 说明             | 权限      |
| ------ | ----------------------------- | ---------------- | --------- |
| POST   | `/notes`                      | 创建便签         | Student   |
| GET    | `/notes`                      | 获取列表         | Student   |
| PUT    | `/notes/{note_id}`            | 更新便签         | Student   |
| PATCH  | `/notes/{note_id}/pin`        | 置顶/取消置顶    | Student   |
| DELETE | `/notes/{note_id}`            | 删除便签         | Student   |

### 倒数日 `/api/v1/countdowns`

| 方法   | 路径                                | 说明             | 权限      |
| ------ | ----------------------------------- | ---------------- | --------- |
| POST   | `/countdowns`                       | 创建倒数日       | Student   |
| GET    | `/countdowns`                       | 获取列表         | Student   |
| PUT    | `/countdowns/{countdown_id}`        | 更新倒数日       | Student   |
| DELETE | `/countdowns/{countdown_id}`        | 删除倒数日       | Student   |

### 书签 `/api/v1/bookmarks`

| 方法   | 路径                                    | 说明             | 权限      |
| ------ | --------------------------------------- | ---------------- | --------- |
| POST   | `/bookmarks`                            | 创建书签         | Student   |
| GET    | `/bookmarks`                            | 获取列表         | Student   |
| PUT    | `/bookmarks/{bookmark_id}`              | 更新书签         | Student   |
| DELETE | `/bookmarks/{bookmark_id}`              | 删除书签         | Student   |
| POST   | `/bookmarks/{bookmark_id}/visit`        | 记录访问         | Student   |
| GET    | `/bookmarks/categories`                 | 获取分类列表     | Student   |

### 公告 `/api/v1/announcements`

| 方法   | 路径                                              | 说明             | 权限           |
| ------ | ------------------------------------------------- | ---------------- | -------------- |
| POST   | `/announcements`                                  | 创建公告         | Admin/Teacher  |
| GET    | `/announcements`                                  | 获取列表         | 所有用户       |
| GET    | `/announcements/{id}`                             | 获取详情         | 所有用户       |
| PUT    | `/announcements/{id}`                             | 更新公告         | Admin/创建者   |
| DELETE | `/announcements/{id}`                             | 删除公告         | Admin/创建者   |
| POST   | `/announcements/{id}/publish`                     | 发布草稿         | Admin/创建者   |
| POST   | `/announcements/{id}/read`                        | 标记已读         | 所有用户       |
| GET    | `/announcements/{id}/read-stats`                  | 阅读统计         | Admin/创建者   |

### 任务 `/api/v1/tasks`

| 方法   | 路径                                | 说明             | 权限             |
| ------ | ----------------------------------- | ---------------- | ---------------- |
| POST   | `/tasks`                            | 创建任务         | Admin/Teacher    |
| GET    | `/tasks`                            | 获取列表         | 所有用户         |
| GET    | `/tasks/{task_id}`                  | 获取详情         | 相关用户         |
| PUT    | `/tasks/{task_id}`                  | 更新任务         | Admin/创建者     |
| DELETE | `/tasks/{task_id}`                  | 删除任务         | Admin/创建者     |
| POST   | `/tasks/{task_id}/submit`           | 提交任务         | Student          |
| POST   | `/tasks/{task_id}/review`           | 审核任务         | Admin/Teacher    |
| GET    | `/tasks/{task_id}/submissions`      | 获取提交记录     | Admin/Teacher/Student |
| GET    | `/tasks/stats`                      | 任务统计         | Admin/Teacher    |

### 日历计划 `/api/v1/calendar`

| 方法   | 路径                                      | 说明             | 权限               |
| ------ | ----------------------------------------- | ---------------- | ------------------ |
| POST   | `/calendar/events`                        | 创建事件         | Student/Teacher    |
| GET    | `/calendar/events`                        | 获取事件列表     | Student/Teacher/Admin |
| PUT    | `/calendar/events/{event_id}`             | 更新事件         | 创建者/Admin       |
| PATCH  | `/calendar/events/{event_id}/status`      | 更新事件状态     | 创建者/Admin       |
| DELETE | `/calendar/events/{event_id}`             | 删除事件         | 创建者/Admin       |

### 学习时长 `/api/v1/study-time`

| 方法   | 路径                           | 说明               | 权限               |
| ------ | ------------------------------ | ------------------ | ------------------ |
| POST   | `/study-time/heartbeat`        | 上报心跳           | Student            |
| GET    | `/study-time/stats`            | 获取统计           | Student/Teacher/Admin |
| GET    | `/study-time/ranking`          | 学习时长排行       | Teacher/Admin      |

### 行为日志 `/api/v1/behavior-logs`

| 方法   | 路径                           | 说明             | 权限             |
| ------ | ------------------------------ | ---------------- | ---------------- |
| POST   | `/behavior-logs`               | 记录行为         | 所有用户         |
| POST   | `/behavior-logs/batch`         | 批量记录         | 所有用户         |
| GET    | `/behavior-logs`               | 查询日志         | Admin/Teacher    |

### 学习热力图 `/api/v1/heatmap`

| 方法   | 路径                       | 说明             | 权限               |
| ------ | -------------------------- | ---------------- | ------------------ |
| GET    | `/heatmap`                 | 获取热力图数据   | Student/Teacher/Admin |
| GET    | `/heatmap/overview`        | 全体概览         | Admin              |

### B站资源 `/api/v1/bilibili`

| 方法   | 路径                                          | 说明             | 权限              |
| ------ | --------------------------------------------- | ---------------- | ----------------- |
| POST   | `/bilibili/resources`                         | 添加资源         | 所有用户          |
| GET    | `/bilibili/resources`                         | 获取列表         | 所有用户          |
| GET    | `/bilibili/resources/{id}`                    | 获取详情         | 所有用户          |
| PUT    | `/bilibili/resources/{id}`                    | 更新资源         | 添加者/Admin      |
| DELETE | `/bilibili/resources/{id}`                    | 删除资源         | 添加者/Admin      |
| POST   | `/bilibili/resources/{id}/watch`              | 记录观看         | Student           |

### 文件上传 `/api/v1/files`

| 方法   | 路径                               | 说明             | 权限              |
| ------ | ---------------------------------- | ---------------- | ----------------- |
| POST   | `/files/upload`                    | 上传文件         | 所有用户          |
| GET    | `/files`                           | 获取列表         | Student/Teacher/Admin |
| GET    | `/files/{file_id}`                 | 获取详情         | 所有用户          |
| GET    | `/files/{file_id}/download`        | 下载文件         | 所有用户          |
| DELETE | `/files/{file_id}`                 | 删除文件         | 上传者/Admin      |

### 知识库 `/api/v1/knowledge`

| 方法   | 路径                                  | 说明             | 权限              |
| ------ | ------------------------------------- | ---------------- | ----------------- |
| POST   | `/knowledge/documents`                | 上传文档         | 所有用户          |
| GET    | `/knowledge/documents`                | 获取列表         | 所有用户          |
| GET    | `/knowledge/documents/{doc_id}`       | 获取详情         | 所有用户          |
| PUT    | `/knowledge/documents/{doc_id}`       | 更新文档         | 上传者/Admin      |
| DELETE | `/knowledge/documents/{doc_id}`       | 删除文档         | 上传者/Admin      |
| POST   | `/knowledge/search`                   | 语义搜索         | 所有用户          |
| POST   | `/knowledge/qa`                       | 知识库问答       | 所有用户          |
| GET    | `/knowledge/categories`               | 获取分类         | 所有用户          |

### AI 对话 `/api/v1/ai/chat`

| 方法   | 路径                                                  | 说明             | 权限      |
| ------ | ----------------------------------------------------- | ---------------- | --------- |
| POST   | `/ai/chat/conversations`                              | 创建对话         | Student   |
| GET    | `/ai/chat/conversations`                              | 获取对话列表     | Student   |
| GET    | `/ai/chat/conversations/{id}/messages`                | 获取历史消息     | Student   |
| POST   | `/ai/chat/conversations/{id}/messages`                | 发送消息(SSE)    | Student   |
| PATCH  | `/ai/chat/conversations/{id}`                         | 更新对话标题     | Student   |
| DELETE | `/ai/chat/conversations/{id}`                         | 删除对话         | Student   |

### Memory `/api/v1/ai/memory`

| 方法   | 路径                                             | 说明             | 权限                |
| ------ | ------------------------------------------------ | ---------------- | ------------------- |
| GET    | `/ai/memory/{student_id}`                        | 获取 Memory      | Student/Teacher/Admin |
| DELETE | `/ai/memory/{student_id}/{memory_id}`            | 申请删除 Memory  | Student/Admin       |
| GET    | `/ai/memory/{student_id}/update-logs`            | 更新日志         | Student/Admin       |

### 每日复盘 `/api/v1/reviews`

| 方法   | 路径                       | 说明             | 权限                |
| ------ | -------------------------- | ---------------- | ------------------- |
| GET    | `/reviews/{date}`          | 获取每日复盘     | Student/Teacher/Admin |
| GET    | `/reviews`                 | 获取复盘列表     | Student/Teacher/Admin |
| POST   | `/reviews/generate`        | 手动触发复盘     | Admin               |

### 通知 `/api/v1/notifications`

| 方法   | 路径                                     | 说明             | 权限         |
| ------ | ---------------------------------------- | ---------------- | ------------ |
| GET    | `/notifications`                         | 获取通知列表     | 所有用户     |
| GET    | `/notifications/unread-count`            | 未读数量         | 所有用户     |
| PATCH  | `/notifications/{id}/read`               | 标记已读         | 所有用户     |
| POST   | `/notifications/read-all`                | 全部标记已读     | 所有用户     |
| DELETE | `/notifications/{id}`                    | 删除通知         | 所有用户     |

### 模型配置 `/api/v1/admin/llm-configs`

| 方法   | 路径                                          | 说明             | 权限   |
| ------ | --------------------------------------------- | ---------------- | ------ |
| POST   | `/admin/llm-configs`                          | 创建配置         | Admin  |
| GET    | `/admin/llm-configs`                          | 获取列表         | Admin  |
| PUT    | `/admin/llm-configs/{id}`                     | 更新配置         | Admin  |
| DELETE | `/admin/llm-configs/{id}`                     | 删除配置         | Admin  |
| POST   | `/admin/llm-configs/{id}/test`                | 测试连接         | Admin  |
| POST   | `/admin/llm-configs/{id}/reset-usage`         | 重置用量         | Admin  |

### 系统管理 `/api/v1/admin/system`

| 方法   | 路径                                   | 说明             | 权限   |
| ------ | -------------------------------------- | ---------------- | ------ |
| GET    | `/admin/system/logs`                   | 系统日志         | Admin  |
| GET    | `/admin/system/ai-logs`               | AI 调用日志      | Admin  |
| GET    | `/admin/system/stats`                  | 系统统计         | Admin  |
| GET    | `/admin/system/settings`               | 获取系统设置     | Admin  |
| PUT    | `/admin/system/settings`               | 更新系统设置     | Admin  |
| GET    | `/admin/system/scheduled-tasks`        | 定时任务状态     | Admin  |

### 数据统计 `/api/v1/stats`

| 方法   | 路径                                | 说明             | 权限            |
| ------ | ----------------------------------- | ---------------- | --------------- |
| GET    | `/stats/student`                    | 学生统计         | Student         |
| GET    | `/stats/teacher`                    | 老师统计         | Teacher         |
| GET    | `/stats/admin`                      | 管理员统计       | Admin           |
| GET    | `/stats/student/{student_id}`       | 指定学生统计     | Teacher/Admin   |

### WebSocket

| 协议 | 路径                              | 说明             | 权限         |
| ---- | --------------------------------- | ---------------- | ------------ |
| WS   | `/api/v1/ws/notifications`        | 实时通知推送     | 所有用户     |

---

> 本文档定义了平台所有前后端交互接口。开发过程中如有新增或调整，请同步更新本文档。后端基于 FastAPI 开发，可通过 Swagger UI（`/docs`）和 ReDoc（`/redoc`）自动生成交互式 API 文档。
