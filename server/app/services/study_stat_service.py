import uuid
import logging
from datetime import datetime, timezone, date, timedelta
from typing import List, Dict, Any, Tuple, Optional
from uuid import UUID
from sqlalchemy import select, and_, desc, func, or_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.bilibili import StudyTimeLog, BilibiliResource, BilibiliWatchLog
from app.models.todo import Todo
from app.models.task import TaskSubmission
from app.models.ai_conversation import AIMessage, AIConversation
from app.schemas.bilibili import BilibiliResourceCreate, BilibiliWatchLogCreate, StudyTimeHeartbeatReq
from app.core.exceptions import NotFoundError, ValidationError

logger = logging.getLogger(__name__)

class BilibiliService:

    @staticmethod
    async def add_resource(
        db: AsyncSession,
        creator_id: UUID,
        res_in: BilibiliResourceCreate
    ) -> BilibiliResource:
        # Check if already exists for this creator
        stmt = select(BilibiliResource).where(
            and_(BilibiliResource.bvid == res_in.bvid, BilibiliResource.creator_id == creator_id)
        )
        existing = (await db.execute(stmt)).scalars().first()
        if existing:
            # Update existing one or return it
            for k, v in res_in.dict().items():
                setattr(existing, k, v)
            existing.deleted_at = None
            db.add(existing)
            await db.commit()
            await db.refresh(existing)
            return existing
            
        db_res = BilibiliResource(
            id=uuid.uuid4(),
            creator_id=creator_id,
            bvid=res_in.bvid,
            title=res_in.title,
            description=res_in.description,
            cover_url=res_in.cover_url,
            author_name=res_in.author_name,
            total_episodes=res_in.total_episodes,
            total_duration=res_in.total_duration,
            category=res_in.category or "other",
            episodes_info=res_in.episodes_info,
            is_shared=res_in.is_shared
        )
        db.add(db_res)
        await db.commit()
        await db.refresh(db_res)
        return db_res

    @staticmethod
    async def list_resources(
        db: AsyncSession,
        user_id: UUID,
        keyword: Optional[str] = None
    ) -> List[BilibiliResource]:
        # Student sees their own uploaded OR public shared ones
        stmt = select(BilibiliResource).where(
            and_(
                BilibiliResource.deleted_at.is_(None),
                or_(BilibiliResource.creator_id == user_id, BilibiliResource.is_shared == True)
            )
        )
        if keyword:
            stmt = stmt.where(BilibiliResource.title.ilike(f"%{keyword}%"))
            
        stmt = stmt.order_by(desc(BilibiliResource.created_at))
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def delete_resource(db: AsyncSession, resource_id: UUID, user_id: UUID) -> bool:
        stmt = select(BilibiliResource).where(
            and_(BilibiliResource.id == resource_id, BilibiliResource.deleted_at.is_(None))
        )
        res = await db.execute(stmt)
        item = res.scalars().first()
        if not item:
            raise NotFoundError("资源不存在或已被删除")
            
        if item.creator_id != user_id:
            raise ValidationError("只有上传者可以删除该视频资源")
            
        item.deleted_at = datetime.now(timezone.utc)
        db.add(item)
        await db.commit()
        return True

    @staticmethod
    async def log_watch_event(
        db: AsyncSession,
        user_id: UUID,
        event_in: BilibiliWatchLogCreate
    ) -> BilibiliWatchLog:
        # Verify resource exists
        stmt = select(BilibiliResource).where(
            and_(BilibiliResource.id == event_in.resource_id, BilibiliResource.deleted_at.is_(None))
        )
        res = await db.execute(stmt)
        resource = res.scalars().first()
        if not resource:
            raise NotFoundError("关联B站视频资源不存在")
            
        log = BilibiliWatchLog(
            id=uuid.uuid4(),
            user_id=user_id,
            resource_id=event_in.resource_id,
            event_type=event_in.event_type,
            episode_number=event_in.episode_number,
            watch_duration=event_in.watch_duration,
            is_completed=event_in.is_completed
        )
        db.add(log)
        
        # If watch_duration increment is positive, also record platform-wide study time heartbeat
        if event_in.watch_duration > 0:
            # We construct a session_id based on user and resource so heartbeats cluster properly
            watch_session_id = f"bwatch_{user_id.hex[:10]}_{event_in.resource_id.hex[:10]}"
            heartbeat_data = StudyTimeHeartbeatReq(
                session_id=watch_session_id,
                duration_seconds=event_in.watch_duration,
                source="bilibili"
            )
            await StudyTimeService.heartbeat(db, user_id, heartbeat_data)
            
        await db.commit()
        await db.refresh(log)
        return log


class StudyTimeService:

    @staticmethod
    async def heartbeat(
        db: AsyncSession,
        user_id: UUID,
        heartbeat_in: StudyTimeHeartbeatReq
    ) -> StudyTimeLog:
        now = datetime.now(timezone.utc)
        
        # Check for active session in past 5 minutes (to handle loose timeouts)
        stmt = select(StudyTimeLog).where(
            and_(
                StudyTimeLog.session_id == heartbeat_in.session_id,
                StudyTimeLog.user_id == user_id,
                StudyTimeLog.status == "active"
            )
        ).order_by(desc(StudyTimeLog.created_at)).limit(1)
        
        res = await db.execute(stmt)
        active_log = res.scalars().first()
        
        if active_log:
            # Session exists, append heartbeat duration
            active_log.end_time = now
            active_log.duration_seconds = (active_log.duration_seconds or 0) + heartbeat_in.duration_seconds
            db.add(active_log)
            await db.flush()
            return active_log
        else:
            # Create a brand new study session log
            start_t = now - timedelta(seconds=heartbeat_in.duration_seconds)
            new_log = StudyTimeLog(
                id=uuid.uuid4(),
                user_id=user_id,
                session_id=heartbeat_in.session_id,
                status="active",
                start_time=start_t,
                end_time=now,
                duration_seconds=heartbeat_in.duration_seconds,
                source=heartbeat_in.source
            )
            db.add(new_log)
            await db.flush()
            return new_log


class HeatmapService:

    @staticmethod
    async def get_heatmap_data(
        db: AsyncSession,
        user_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        # Default start date is 365 days ago, end date is today
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=364)
            
        start_dt = datetime(start_date.year, start_date.month, start_date.day, tzinfo=timezone.utc)
        end_dt = datetime(end_date.year, end_date.month, end_date.day, tzinfo=timezone.utc) + timedelta(days=1)
        
        # 1. Fetch completed TODOs by date
        todo_stmt = select(
            func.date(Todo.completed_at).label("event_date"),
            func.count(Todo.id).label("cnt")
        ).where(
            and_(
                Todo.user_id == user_id,
                Todo.status == "completed",
                Todo.completed_at >= start_dt,
                Todo.completed_at < end_dt
            )
        ).group_by(func.date(Todo.completed_at))
        
        todos_res = (await db.execute(todo_stmt)).all()
        
        # 2. Fetch completed Task submissions
        task_stmt = select(
            func.date(TaskSubmission.created_at).label("event_date"),
            func.count(TaskSubmission.id).label("cnt")
        ).where(
            and_(
                TaskSubmission.user_id == user_id,
                TaskSubmission.created_at >= start_dt,
                TaskSubmission.created_at < end_dt
            )
        ).group_by(func.date(TaskSubmission.created_at))
        
        tasks_res = (await db.execute(task_stmt)).all()
        
        # 3. Fetch active study session times (grouped by day)
        study_stmt = select(
            func.date(StudyTimeLog.start_time).label("event_date"),
            func.sum(StudyTimeLog.duration_seconds).label("seconds")
        ).where(
            and_(
                StudyTimeLog.user_id == user_id,
                StudyTimeLog.start_time >= start_dt,
                StudyTimeLog.start_time < end_dt
            )
        ).group_by(func.date(StudyTimeLog.start_time))
        
        study_res = (await db.execute(study_stmt)).all()

        # 4. Fetch AI companion chats sent
        chat_stmt = select(
            func.date(AIMessage.created_at).label("event_date"),
            func.count(AIMessage.id).label("cnt")
        ).join(AIConversation, AIMessage.conversation_id == AIConversation.id).where(
            and_(
                AIConversation.user_id == user_id,
                AIMessage.role == "user",
                AIMessage.created_at >= start_dt,
                AIMessage.created_at < end_dt
            )
        ).group_by(func.date(AIMessage.created_at))
        
        chats_res = (await db.execute(chat_stmt)).all()

        # Build day-by-day counts dictionary
        # Points mapping:
        # completed TODO: 2 pts each
        # submitted Task: 5 pts each
        # AI message sent: 1 pt each
        # Study duration: 1 pt for every 5 minutes (300 seconds)
        scores_by_date: Dict[date, int] = {}
        
        # Loop over dates in range to initialize
        curr = start_date
        while curr <= end_date:
            scores_by_date[curr] = 0
            curr += timedelta(days=1)
            
        # Accumulate
        for r_date, cnt in todos_res:
            if r_date in scores_by_date:
                scores_by_date[r_date] += cnt * 2
                
        for r_date, cnt in tasks_res:
            if r_date in scores_by_date:
                scores_by_date[r_date] += cnt * 5
                
        for r_date, cnt in chats_res:
            if r_date in scores_by_date:
                scores_by_date[r_date] += cnt * 1
                
        for r_date, secs in study_res:
            if r_date in scores_by_date and secs:
                scores_by_date[r_date] += int(secs) // 300
                
        # Return format sorted chronologically
        points_list = []
        for d, score in sorted(scores_by_date.items()):
            points_list.append({
                "date": d.strftime("%Y-%m-%d"),
                "count": score
            })
            
        return points_list
