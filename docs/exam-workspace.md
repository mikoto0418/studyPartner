# 编程考试工作台

学生打开编程题后，桌面使用左题面、右代码与下方自测结果。两侧独立滚动，可拖动中间分隔条调宽；窄屏切换“题目内容 / 代码与自测”。顶部保留题号、倒计时、服务器保存状态和整卷交卷，考试中隐藏主站导航。

## 编辑与运行

- CodeMirror 6 编辑器随前端本地构建，运行时不依赖 CDN。支持 Python、Java、C、C++ 语法高亮、行号、折叠、括号配对。
- Tab / Shift+Tab 缩进和反缩进，默认 4 空格；Enter 自动缩进。Ctrl+Z 撤销，Ctrl+Y / Ctrl+Shift+Z 重做，Ctrl+F 查找，Ctrl+S 保存。
- 切题保留各题的代码、语言、光标、滚动和撤销状态；刷新恢复服务器保存内容及本机未同步草稿，内存中的撤销历史不跨刷新保留。
- 可以选择、复制、剪切自己代码，在本场页面内复制的原文本可重新粘贴。自测输入允许粘贴样例。外部文本粘贴/拖入代码仍被拦截并记录；输入法、缩进、补括号、查找和撤销不是违规。
- “运行自测”只验证输入与输出，不交卷、不更新考试成绩。改动代码、语言或输入后，旧运行结果标记为已过期；运行中的响应始终归属原题。
- 整卷交卷期间冻结作答控件。请求失败会核对服务器状态：确已收卷则显示结果，尚未收卷才恢复编辑。

## 全屏与记录

要求全屏的考试，在退出全屏后显示浏览器原生模态遮罩，页面只能选择“继续答题”。刷新、后退、主页直链均先核对服务器上的未交卷考试并返回该考试；收卷后解除限制。确认状态失败时展示重试，不把网络失败视为已交卷。

同次窗口失焦/隐藏归并为一次离开，离开和全屏遮罩期间不累计有效题目停留。浏览器缩放、窗口内外尺寸、`debugger` 探针不再用于判断作弊。记录是待复核信号，不等于教师已确认违规。教师可选“累计退出全屏 3 次自动交卷”，默认关闭；到时收卷不受此开关影响。

事件附带稳定 ID，重试和并发重复上报幂等；未送达事件暂存本机以便刷新后重试。本机存储不可用、清理浏览器数据或长期断线仍可能丢失未送达内容。未同步代码无法被教师读取；截止后以服务器已收到的内容为准。

浏览器全屏只能限制本网页交互，不能禁止系统切换应用、关闭浏览器或在其他设备访问资料。

## 从 GitHub 更新已有部署

建议在考试结束后更新。保留当前 `.env.interview` 和 Docker 数据卷；不重新初始化考试或覆盖题目。

在项目根目录执行：

```powershell
git switch client
git pull --ff-only origin client
docker compose --env-file .env.interview -f docker-compose.interview.yml build backend frontend judge
docker compose --env-file .env.interview -f docker-compose.interview.yml run --rm --no-deps backend alembic upgrade head
docker compose --env-file .env.interview -f docker-compose.interview.yml up -d --no-build
```

源码更新需要在可联网环境预先安装依赖并构建镜像，构建好后可继续用于无互联网的局域网考试。本次不提供新的增量 ZIP。已有离线镜像包不会因 Git 拉取自动更新，请勿用旧镜像覆盖新构建。

本轮监考修复复用现有事件主键，不新增数据库列；上面迁移命令用于兼容更早版本的教师班级关联。不要执行 `down -v`、删除数据库或运行重建考试脚本。正式部署前保留数据库备份；若本地源码有修改，先合并后再构建。

## 开源依赖

本项目保留现有 Apache-2.0 许可。编辑器使用 MIT 许可的 [CodeMirror](https://codemirror.net/)，依赖版本锁定于 `web/package-lock.json`，相关许可见 [third-party-notices.md](third-party-notices.md)。

## 本次验证（2026-10-27）

- `web`：`npm test` 19 项通过，`npm run build` 类型检查与生产构建通过。
- 在生产构建预览服务上运行 `web/tests/verify_exam_workspace.py` 和 `web/tests/verify_exam_monitoring.py`，两套真实 Chrome 回归通过。覆盖左右与窄屏布局、四语言编辑、切题历史、复制粘贴规则、保存、旧运行结果、交卷期间只读、全屏遮罩与刷新导航限制、交卷解锁、教师代码读取与轮询。
- 后端在独立 PostgreSQL 测试库运行 `python -m pytest tests -q --tb=short --disable-warnings`：83 项通过，2 项真实 go-judge 集成测试跳过。覆盖重复/并发上报幂等、权限、草稿与空题、定时收卷和全屏自动收卷开关。
- 本机 Docker 当日无法启动，本轮未重跑真实判题容器与完整离线部署联调。具备运行环境后可设 `RUN_JUDGE_INTEGRATION=1` 复跑，并运行 `server/tests/verify_offline_session.py`。

浏览器回归使用模拟 API，不访问正式数据。后端测试需要 `INTERVIEW_TEST_DATABASE_URL` 指向以 `_test` 结尾的独立数据库，测试会重建该库内的数据表。不得指向正式考试数据库。
