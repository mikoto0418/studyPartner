from app.models.base import Base, BaseModel
from app.models.user import User, Role, UserRole, StudentProfile
from app.models.todo import Todo
from app.models.note import Note
from app.models.announcement import Announcement, AnnouncementReceiver, AnnouncementRead
from app.models.task import Task, TaskAssignee, TaskSubmission
from app.models.calendar_event import CalendarEvent
from app.models.notification import Notification
from app.models.llm import LLMProviderConfig, LLMUsageLog
from app.models.ai_conversation import AIConversation, AIMessage
from app.models.student_memory import DailyReview, StudentMemory
from app.models.knowledge import FileModel, KnowledgeDocument, KnowledgeChunk
from app.models.bilibili import StudyTimeLog, BilibiliResource, BilibiliWatchLog

# Explicitly export so metadata registers them
__all__ = [
    "Base", "BaseModel", "User", "Role", "UserRole", "StudentProfile", "Todo", "Note",
    "Announcement", "AnnouncementReceiver", "AnnouncementRead",
    "Task", "TaskAssignee", "TaskSubmission",
    "CalendarEvent", "Notification",
    "LLMProviderConfig", "LLMUsageLog",
    "AIConversation", "AIMessage",
    "DailyReview", "StudentMemory",
    "FileModel", "KnowledgeDocument", "KnowledgeChunk",
    "StudyTimeLog", "BilibiliResource", "BilibiliWatchLog"
]
