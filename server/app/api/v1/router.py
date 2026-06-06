from fastapi import APIRouter

from app.api.v1 import (
    ai_chat,
    announcements,
    auth,
    bilibili,
    calendar,
    files,
    heatmap,
    knowledge,
    learning_paths,
    memory,
    notes,
    notifications,
    reviews,
    study_time,
    tasks,
    todos,
    users,
    websocket,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["系统认证"])
api_router.include_router(users.router, prefix="/users", tags=["用户管理"])
api_router.include_router(todos.router, prefix="/todos", tags=["待办事项"])
api_router.include_router(notes.router, prefix="/notes", tags=["便签管理"])
api_router.include_router(announcements.router, prefix="/announcements", tags=["公告管理"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["教学任务"])
api_router.include_router(calendar.router, prefix="/calendar", tags=["日历日程"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["通知中心"])
api_router.include_router(ai_chat.router, prefix="/ai/chat", tags=["AI 对话"])
api_router.include_router(memory.router, prefix="/ai/memory", tags=["AI Memory"])
api_router.include_router(reviews.router, prefix="/reviews", tags=["每日复盘"])
api_router.include_router(files.router, prefix="/files", tags=["文件系统"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["知识库中心"])
api_router.include_router(bilibili.router, prefix="/bilibili", tags=["B站资源"])
api_router.include_router(study_time.router, prefix="/study-time", tags=["学习时长"])
api_router.include_router(heatmap.router, prefix="/heatmap", tags=["学习热力图"])
api_router.include_router(learning_paths.router, prefix="/learning-paths", tags=["学习路径任务"])
api_router.include_router(websocket.router, tags=["WebSocket 推送"])
