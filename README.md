# AI 伴学与智能体协同平台

面向多场景（自学、学校、培训、企业）的通用型 **AI 伴学与智能体协同平台**。系统核心采用“学习行为记录 + 自适应 Memory 机制 + 实验室共享知识库”，通过长周期陪伴与智能复盘，辅助学习者高效成长。

## 🎨 视觉与 UI 风格
本平台遵循**极简美学（Minimalist Chinese UI）**设计规范：
- 原生级淡色与暗色模式支持
- 统一侧边栏自适应布局（仅在主仪表盘详尽展现，其余子页面隐藏侧边栏，保障视觉高度专注）
- 界面融入了 Indigo/Violet 渐变暗色磨砂玻璃背景，配合精心设计的微动效，带来极其 premium 的用户体验

---

## 🏗️ 项目技术栈
- **前端 (web)**: Vue 3 + TypeScript + Vite + Pinia + Vue Router + Element Plus + Tailwind CSS
- **后端 (server)**: FastAPI (Python 3.11) + SQLAlchemy (Async) + PostgreSQL + Redis + Celery
- **AI 引擎**: 硅基流动 (SiliconFlow) 统一大模型 API (兼容 OpenAI SDK)
- **实时网络**: WebSocket 长连接 + ConnectionManager
- **邮件服务**: SMTP / SMTPS 验证码邮件派发

---

## ✨ 核心模块与工业级升级特性

### 1. ⚡ Celery 异步任务调度 (Module A)
- **任务分离**：为避免耗时的 AI 文本生成、每日复盘报告（0 点触发）和知识库切片 Embedding 任务阻塞 FastAPI 主线程，系统通过 Celery 将其分发至分布式 Worker 中异步处理。
- **定时调度 (Beat)**：每天午夜 0:00，Celery Beat 会自动触发所有活跃学生的“每日复盘与 Memory 提取”任务，并在处理完成后通过 Redis 进行持久化。
- **手动触发**：管理员可以通过 `/reviews/generate` 接口发送任务 ID，手动让 Celery 重新生成特定学生在指定日期的复盘报告。

### 2. 🔌 WebSocket 实时通知网关 (Module B)
- **双向连接**：提供客户端到服务端的长连接通道 `/api/v1/ws`，建立连接时采用 JWT Token 对用户身份进行严格的安全校验。
- **单播与推送**：后端提供全局 of `ConnectionManager` 连接管理器。当 `NotificationService` 生成新的系统通知时，会自动通过长连接将 payload 单播推送给特定的在线用户。
- **前端 Alert**：前端 Composable `useWebSocket.ts` 监听连接与心跳（每 30 秒进行 Ping-Pong 交互）。当接收到推送通知时，触发 Element Plus 的 `ElNotification` 实时通知浮窗，并分发 `new-notification` 全局事件。

### 3. ✉️ 邮箱自主注册与密码找回 (Module C)
- **验证码防刷机制**：系统生成 6 位随机数字验证码并存入 Redis 中，有效期 5 分钟，验证码一旦使用立即销毁（Delete-on-verify）。前端获取验证码时引入 60 秒倒计时防刷控制。
- **SMTP 异步派发**：通过内置 `smtplib` 配合 `asyncio.to_thread` 线程池包装，在不影响主线程运行的前提下异步投递 HTML 邮件。
- **接口集成**：新增注册接口 `/auth/register`、发码接口 `/auth/send-code` 以及重置密码接口 `/auth/reset-password`，极大提升了用户自主服务能力。

### 4. 📊 学习行为记录与热力图 (Phase 6 基础)
- **活跃度热力图**：在学生仪表盘动态展示。根据完成代办 (+2)、提交任务 (+5)、AI对话 (+1)、专注心跳 (每5分钟+1) 自动计分，支持日历小方格 `el-tooltip` 详情浮窗及连续活跃天数统计。
- **B站视频学习房**：导入 B站视频资源，沙箱限制（屏蔽广告和劫持），实现切集 (分P) 监听与专注会话心跳自动记录 (每30秒)，支持手动完成任务，自动增量上报时长。
- **全局时长心跳**：学生登录状态下，系统自动在后台每 30 秒执行一次活跃心跳上报，计入学生今日学习累积。

---

## 🚀 快速启动与部署指南

### 1. 生产环境一键部署 (推荐)
在生产环境中，平台通过前端 Nginx 统一代理静态资源与 `/api/` 路由，并关闭了辅助数据库的外网端口暴露以保障安全。生产环境使用 `docker-compose.prod.yml` 以优化资源占用，并配置了 Nginx 以支持流式响应（SSE）及长连接优化。

直接在项目根目录下运行一键部署脚本：
```bash
chmod +x deploy.sh
./deploy.sh
```
该脚本将自动执行以下操作：
1. 拷贝 `.env.example` 生成 `.env` 配置文件（请在此填入大模型 `SILICONFLOW_API_KEY` 以及 SMTP 发信邮箱配置）。
2. 使用 `docker-compose.prod.yml` 构建并拉起生产环境 Docker 容器镜像（包含 postgres, redis, minio, qdrant, backend, frontend, worker, beat 等八个微服务）。
3. 循环等待 PostgreSQL 数据库端口就绪。
4. 在后端容器内执行 `python -m app.seed` 自动创建数据表并填充初始化种子账户。

部署完成后：
- 网页访问入口：`http://localhost` (统一 80 端口网关，零跨域 CORS 问题)
- MinIO 控制台：`http://localhost:9001`

> **初始测试账户：**
> - **学生**: `student` / `student123`
> - **教师**: `teacher` / `teacher123`
> - **管理员**: `admin` / `admin123`

### 2. 开发环境容器部署 (Docker Compose)
在项目根目录下，直接执行以下命令拉起数据库、缓存及基础设施服务：
```bash
docker compose up -d
```
当容器就绪后，运行数据表初始化：
```bash
docker compose exec backend python -m app.seed
```

---

## 💻 本地开发环境调试

如果你需要在本地不通过 Docker 直接调试前后端：

### 1. 运行前端 (web)
```bash
cd web
npm install
npm run dev
```
前端开发服务器将默认运行在：`http://localhost:5173`。

### 2. 运行后端 (server)
1. 安装 Python 依赖：
   ```bash
   cd server
   pip install -r requirements.txt
   ```
2. 复制 `server/.env` 并按需配置本地连接。务必填写如下 SMTP 配置以支持注册功能：
   ```ini
   SMTP_HOST=smtp.qq.com
   SMTP_PORT=465
   SMTP_USER=your_email@qq.com
   SMTP_PASSWORD=your_smtp_authorization_code
   SMTP_FROM_EMAIL=your_email@qq.com
   ```
3. 确保本地装有 PostgreSQL 和 Redis，运行本地数据库迁移与种子数据录入：
   ```bash
   python -m app.seed
   ```
4. 启动 FastAPI 本地开发服务：
   ```bash
   uvicorn app.main:app --reload
   ```
   API 交互文档地址：`http://localhost:8000/api/docs`。

### 3. 运行 Celery 异步服务 (本地调试)
如果你在本地调试异步任务相关的逻辑，可以在 `server` 目录下打开两个新终端，分别启动 worker 和 scheduler：
* **启动 Worker 节点**：
  ```bash
  celery -A app.core.celery_app:celery_app worker --loglevel=info -P threads
  ```
* **启动 Beat 定时器**：
  ```bash
  celery -A app.core.celery_app:celery_app beat --loglevel=info
  ```
