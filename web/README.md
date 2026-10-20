# MemoryPath 学迹 · Web 前端

Vue 3 + TypeScript + Vite 构建的前端应用，覆盖学生端、教师端与管理员端界面，品牌名为 **MemoryPath 学迹**（AI 伴学与智能体协同平台）。

## 开发

```bash
npm install
npm run dev
```

默认访问 http://localhost:5173，`/api` 请求代理到 `http://127.0.0.1:8000`（可通过 `VITE_API_PROXY_TARGET` 覆盖）。

## 构建

```bash
npm run build
```

构建产物输出到 `dist/`。
