import asyncio
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.core.database import engine, SessionLocal
from app.models import Base
from app.models.user import User, Role, UserRole, StudentProfile
from app.models.todo import Todo
from app.models.note import Note
from app.models.announcement import Announcement, AnnouncementReceiver
from app.models.task import Task, TaskAssignee
from app.models.calendar_event import CalendarEvent
from app.models.notification import Notification
from app.core.security import get_password_hash

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("db_seeder")

async def get_or_create_user(db: AsyncSession, username: str, email: str, role_code: str, nickname: str, password_plain: str) -> User:
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalars().first()
    
    if not user:
        user = User(
            username=username,
            email=email,
            nickname=nickname,
            status="active",
            password_hash=get_password_hash(password_plain)
        )
        db.add(user)
        await db.flush()
        
        # Link role
        role_result = await db.execute(select(Role).where(Role.code == role_code))
        role = role_result.scalars().first()
        if role:
            user_role = UserRole(user_id=user.id, role_id=role.id)
            db.add(user_role)
            
        # Create student profile if role is student
        if role_code == "student":
            student_profile = StudentProfile(
                user_id=user.id,
                student_id="SP20260001",
                grade="2026级",
                major="计算机科学与技术",
                research_direction="人工智能与多智能体协同"
            )
            db.add(student_profile)
            
        await db.commit()
        logger.info(f"Seeded user: {username} ({role_code}) with password: {password_plain}")
    else:
        logger.info(f"User already exists: {username}")
        
    return user

async def seed_data():
    logger.info("Connecting to database and creating tables...")
    
    # 1. Automatically create all tables registered under Base.metadata
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Tables created successfully.")

    async with SessionLocal() as db:
        # 2. Seed Roles if they do not exist
        roles_to_seed = [
            {"code": "admin", "name": "管理员", "description": "系统全局管理员，负责配置和运维。"},
            {"code": "teacher", "name": "教师", "description": "指导教师，负责发布任务和监控学情。"},
            {"code": "student", "name": "学生", "description": "平台主要使用者，使用仪表盘和伴学智能体。"}
        ]
        
        logger.info("Checking and seeding default system roles...")
        for r_data in roles_to_seed:
            result = await db.execute(select(Role).where(Role.code == r_data["code"]))
            role = result.scalars().first()
            if not role:
                role = Role(code=r_data["code"], name=r_data["name"], description=r_data["description"])
                db.add(role)
                logger.info(f"Seeded role: {r_data['code']}")
            else:
                logger.info(f"Role already exists: {r_data['code']}")
        await db.commit()

        # 3. Seed Users
        admin = await get_or_create_user(db, "admin", "admin@example.com", "admin", "系统管理员", "admin123")
        teacher = await get_or_create_user(db, "teacher", "teacher@example.com", "teacher", "张教授", "teacher123")
        student = await get_or_create_user(db, "student", "student@example.com", "student", "李自学", "student123")

        # 4. Seed Mock TODOs for the Student user
        logger.info("Checking and seeding mock TODOs...")
        todo_result = await db.execute(select(Todo).where(Todo.user_id == student.id))
        existing_todos = todo_result.scalars().all()
        
        if not existing_todos:
            mock_todos = [
                Todo(
                    user_id=student.id,
                    title="阅读关于 AI Agent Memory 的最新论文",
                    description="精读 Linear 和 Notion 的智能体记忆实现机制，做思维导图总结",
                    priority="high",
                    status="pending",
                    due_date=datetime.now(timezone.utc) + timedelta(days=3),
                    sort_order=1
                ),
                Todo(
                    user_id=student.id,
                    title="提交下周学习计划草案给指导老师",
                    description="将整理出的 4 个阶段计划发送给张教授审核",
                    priority="medium",
                    status="completed",
                    due_date=datetime.now(timezone.utc) - timedelta(days=1),
                    completed_at=datetime.now(timezone.utc) - timedelta(hours=2),
                    sort_order=2
                ),
                Todo(
                    user_id=student.id,
                    title="完成 Qdrant 向量检索接口的本地测试",
                    description="完成 Python SDK 客户端的 CRUD 连接测试，编写单元测试用例",
                    priority="high",
                    status="pending",
                    due_date=datetime.now(timezone.utc) + timedelta(days=5),
                    sort_order=3
                ),
                Todo(
                    user_id=student.id,
                    title="整理 B站 课程《动手学深度学习》第 3 节笔记",
                    description="记录多层感知机的反向传播求导推导过程",
                    priority="low",
                    status="pending",
                    due_date=datetime.now(timezone.utc) + timedelta(days=10),
                    sort_order=4
                )
            ]
            db.add_all(mock_todos)
            logger.info("Mock TODOs seeded successfully.")
        else:
            logger.info("Student already has TODOs. Skipping.")

        # 5. Seed Mock Notes for the Student user
        logger.info("Checking and seeding mock Notes...")
        note_result = await db.execute(select(Note).where(Note.user_id == student.id))
        existing_notes = note_result.scalars().all()
        
        if not existing_notes:
            mock_notes = [
                Note(
                    user_id=student.id,
                    title="DP 转移方程",
                    content="动态规划状态转移方程推导：\ndp[i] = max(dp[i-1], dp[i-2] + val)",
                    color="bg-amber-50/50 border-amber-200 text-amber-800",
                    is_pinned=True,
                    sort_order=1
                ),
                Note(
                    user_id=student.id,
                    title="组会大纲",
                    content="本周组会汇报重点：\n1. AI Memory 四层设计\n2. SQLite/PostgreSQL 混合存储对比",
                    color="bg-emerald-50/50 border-emerald-200 text-emerald-800",
                    is_pinned=False,
                    sort_order=2
                )
            ]
            db.add_all(mock_notes)
            logger.info("Mock Notes seeded successfully.")
        else:
            logger.info("Student already has Notes. Skipping.")
            
        # 6. Seed Announcements
        logger.info("Checking and seeding announcements...")
        ann_result = await db.execute(select(Announcement))
        existing_anns = ann_result.scalars().all()
        if not existing_anns:
            ann1 = Announcement(
                title="系统例行维护公告",
                content="为了提供更流畅的伴学体验，系统将于今晚 23:00 至次日凌晨 01:00 进行系统升级与算法优化。届时部分 AI 服务可能出现短暂延迟，请提前保存对话，谢谢您的配合。",
                status="published",
                target_type="all",
                is_pinned=True,
                creator_id=admin.id
            )
            ann2 = Announcement(
                title="关于加强学术规范与大纲撰写的通知",
                content="本学期期末论文大纲审核已开始。请各位同学按照各自指导老师发布的任务，在截止日期前提交详细的研究背景、算法路线及验证指标。",
                status="published",
                target_type="all_students",
                is_pinned=False,
                creator_id=teacher.id
            )
            db.add_all([ann1, ann2])
            await db.flush()
            
            # Add receivers for student
            recv1 = AnnouncementReceiver(announcement_id=ann1.id, user_id=student.id)
            recv2 = AnnouncementReceiver(announcement_id=ann2.id, user_id=student.id)
            db.add_all([recv1, recv2])
            logger.info("Announcements seeded successfully.")
        else:
            logger.info("Announcements already seeded. Skipping.")

        # 7. Seed Tasks
        logger.info("Checking and seeding teaching tasks...")
        task_result = await db.execute(select(Task))
        existing_tasks = task_result.scalars().all()
        if not existing_tasks:
            task1 = Task(
                creator_id=teacher.id,
                title="文献阅读与研究方法梳理",
                description="请深入阅读《Attention is All You Need》并梳理其核心架构。要求写出Transformer模型结构、多头注意力求导及主要贡献。",
                priority="high",
                status="in_progress",
                start_date=datetime.now(timezone.utc),
                due_date=datetime.now(timezone.utc) + timedelta(days=3),
                attachment_ids=[]
            )
            task2 = Task(
                creator_id=teacher.id,
                title="毕业论文大纲草拟",
                description="拟定毕业设计技术路线并说明主要系统组件功能。请详细描述RAG知识检索以及Memory模块的数据交互流向。",
                priority="medium",
                status="in_progress",
                start_date=datetime.now(timezone.utc),
                due_date=datetime.now(timezone.utc) + timedelta(days=7),
                attachment_ids=[]
            )
            db.add_all([task1, task2])
            await db.flush()

            # Assign to student
            assignee1 = TaskAssignee(
                task_id=task1.id,
                user_id=student.id,
                status="in_progress",
                assigned_at=datetime.now(timezone.utc)
            )
            assignee2 = TaskAssignee(
                task_id=task2.id,
                user_id=student.id,
                status="in_progress",
                assigned_at=datetime.now(timezone.utc)
            )
            db.add_all([assignee1, assignee2])
            logger.info("Tasks seeded successfully.")
        else:
            logger.info("Tasks already seeded. Skipping.")

        # 8. Seed Calendar Events
        logger.info("Checking and seeding calendar events...")
        cal_result = await db.execute(select(CalendarEvent))
        existing_cals = cal_result.scalars().all()
        if not existing_cals:
            cal1 = CalendarEvent(
                user_id=student.id,
                created_by=student.id,
                title="每日英语听力训练",
                description="听写一期 BBC Learning English，记录重点生词",
                event_type="personal",
                status="completed",
                start_time=datetime.now(timezone.utc).replace(hour=9, minute=0, second=0, microsecond=0),
                end_time=datetime.now(timezone.utc).replace(hour=10, minute=0, second=0, microsecond=0),
                all_day=False,
                color="#10b981"
            )
            cal2 = CalendarEvent(
                user_id=student.id,
                created_by=teacher.id,
                title="编译原理大作业提交",
                description="提交第一阶段AST抽象语法树构建代码",
                event_type="task",
                status="planned",
                start_time=datetime.now(timezone.utc) + timedelta(days=2),
                end_time=datetime.now(timezone.utc) + timedelta(days=2, hours=2),
                all_day=False,
                color="#f59e0b"
            )
            db.add_all([cal1, cal2])
            logger.info("Calendar events seeded successfully.")
        else:
            logger.info("Calendar events already seeded. Skipping.")

        # 9. Seed Notifications
        logger.info("Checking and seeding notifications...")
        notif_result = await db.execute(select(Notification))
        existing_notifs = notif_result.scalars().all()
        if not existing_notifs:
            notif1 = Notification(
                user_id=student.id,
                title="新任务下达",
                content="指导教师张教授给你下发了「期末研究报告大纲提交」教学指导任务，请在截止日前提交作业。",
                notification_type="task"
            )
            notif2 = Notification(
                user_id=student.id,
                title="AI 建议就绪",
                content="根据你昨天的学习时间与任务表现，AI 伴学助手已为你生成今日学习规划，请前往仪表盘查看。",
                notification_type="system"
            )
            db.add_all([notif1, notif2])
            logger.info("Notifications seeded successfully.")
        else:
            logger.info("Notifications already seeded. Skipping.")

        await db.commit()

async def main():
    try:
        await seed_data()
        logger.info("Database seeding completed successfully.")
    except Exception as e:
        logger.error(f"Error occurred during database seeding: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())
