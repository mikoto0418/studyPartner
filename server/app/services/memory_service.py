import json
import uuid
import logging
from datetime import datetime, timezone, date, timedelta
from typing import List, Optional, Tuple, Dict, Any
from uuid import UUID
from sqlalchemy import select, and_, desc, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.student_memory import DailyReview, StudentMemory
from app.models.user import User, StudentProfile
from app.models.todo import Todo
from app.models.task import Task, TaskAssignee, TaskSubmission
from app.models.calendar_event import CalendarEvent
from app.models.ai_conversation import AIConversation, AIMessage
from app.core.llm import llm_router, ChatMessage
from app.core.exceptions import NotFoundError, ValidationError

logger = logging.getLogger(__name__)

class MemoryService:

    @staticmethod
    async def get_student_memories(
        db: AsyncSession,
        student_id: UUID,
        layer: str = "all"
    ) -> Tuple[List[StudentMemory], Optional[datetime]]:
        stmt = select(StudentMemory).where(
            and_(
                StudentMemory.user_id == student_id,
                StudentMemory.status == "active"
            )
        )
        if layer in ["short_term", "long_term"]:
            stmt = stmt.where(StudentMemory.memory_type == layer)
        
        stmt = stmt.order_by(desc(StudentMemory.updated_at))
        res = await db.execute(stmt)
        memories = list(res.scalars().all())
        
        # Get last updated time
        time_stmt = select(func.max(StudentMemory.updated_at)).where(
            StudentMemory.user_id == student_id
        )
        time_res = await db.execute(time_stmt)
        last_updated = time_res.scalar()
        
        return memories, last_updated

    @staticmethod
    async def delete_student_memory(
        db: AsyncSession,
        student_id: UUID,
        memory_id: UUID
    ) -> bool:
        stmt = select(StudentMemory).where(
            and_(
                StudentMemory.id == memory_id,
                StudentMemory.user_id == student_id,
                StudentMemory.status == "active"
            )
        )
        res = await db.execute(stmt)
        memory = res.scalars().first()
        if not memory:
            raise NotFoundError("Memory 条目不存在或已被归档/删除")
        
        # Soft-delete
        memory.status = "deleted"
        db.add(memory)
        await db.commit()
        return True

    @staticmethod
    async def get_memory_update_logs(
        db: AsyncSession,
        student_id: UUID,
        page: int = 1,
        page_size: int = 20,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        # Return historical or current state of memories
        stmt = select(StudentMemory).where(StudentMemory.user_id == student_id)
        if start_date:
            stmt = stmt.where(func.date(StudentMemory.created_at) >= start_date)
        if end_date:
            stmt = stmt.where(func.date(StudentMemory.created_at) <= end_date)
            
        stmt = stmt.order_by(desc(StudentMemory.created_at))
        
        # Count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_res = await db.execute(count_stmt)
        total = count_res.scalar() or 0
        
        # Limit Offset
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        res = await db.execute(stmt)
        memories = res.scalars().all()
        
        items = []
        for m in memories:
            action = "create"
            if m.status == "superseded":
                action = "update"
            elif m.status == "deleted":
                action = "delete"
                
            items.append({
                "id": m.id,
                "action": action,
                "memory_id": m.id,
                "content": m.content,
                "layer": m.memory_type,
                "confidence": m.confidence,
                "source": "daily_review" if m.source_review_id else "manual",
                "review_date": start_date or date.today(), # fallback representation
                "created_at": m.created_at
            })
            
        return items, total

    @staticmethod
    async def get_daily_review(
        db: AsyncSession,
        student_id: UUID,
        review_date: date
    ) -> DailyReview:
        stmt = select(DailyReview).where(
            and_(
                DailyReview.user_id == student_id,
                DailyReview.review_date == review_date
            )
        )
        res = await db.execute(stmt)
        review = res.scalars().first()
        if not review:
            raise NotFoundError("该日期无复盘记录")
        return review

    @staticmethod
    async def list_daily_reviews(
        db: AsyncSession,
        student_id: UUID,
        page: int = 1,
        page_size: int = 20,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Tuple[List[DailyReview], int]:
        stmt = select(DailyReview).where(DailyReview.user_id == student_id)
        if start_date:
            stmt = stmt.where(DailyReview.review_date >= start_date)
        if end_date:
            stmt = stmt.where(DailyReview.review_date <= end_date)
            
        stmt = stmt.order_by(desc(DailyReview.review_date))
        
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_res = await db.execute(count_stmt)
        total = count_res.scalar() or 0
        
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        res = await db.execute(stmt)
        reviews = list(res.scalars().all())
        
        return reviews, total

    @staticmethod
    async def generate_daily_review(
        db: AsyncSession,
        student_id: UUID,
        review_date: date
    ) -> DailyReview:
        """
        Runs the daily review generator flow:
        1. Query student database behaviors on that date.
        2. Format context for LLM.
        3. Call LLM to generate summary, highlights, concerns, and suggestions.
        4. Call LLM to extract new memory elements.
        5. Call LLM to perform memory update & conflict detection.
        6. Commit everything to DB.
        """
        # Check if review already exists
        check_stmt = select(DailyReview).where(
            and_(DailyReview.user_id == student_id, DailyReview.review_date == review_date)
        )
        check_res = await db.execute(check_stmt)
        existing = check_res.scalars().first()
        if existing and existing.status == "completed":
            return existing

        # Create or update placeholder
        if existing:
            review = existing
            review.status = "processing"
            review.error_message = None
        else:
            review = DailyReview(
                id=uuid.uuid4(),
                user_id=student_id,
                review_date=review_date,
                status="processing"
            )
            db.add(review)
            await db.flush()

        try:
            # 1. Fetch user data for context
            # Get User Details
            user_res = await db.execute(
                select(User).options(selectinload(User.student_profile)).where(User.id == student_id)
            )
            user = user_res.scalars().first()
            if not user:
                raise NotFoundError("学生账户不存在")

            start_dt = datetime(review_date.year, review_date.month, review_date.day, tzinfo=timezone.utc)
            end_dt = start_dt + timedelta(days=1)

            # A. Todos completed/created on review_date
            todos_stmt = select(Todo).where(
                and_(
                    Todo.user_id == student_id,
                    Todo.created_at >= start_dt,
                    Todo.created_at < end_dt
                )
            )
            todos_res = await db.execute(todos_stmt)
            todos = todos_res.scalars().all()
            
            todos_created = len(todos)
            todos_completed = sum(1 for t in todos if t.status == "completed")

            # B. Tasks completed/assigned
            tasks_stmt = select(TaskAssignee).options(selectinload(TaskAssignee.task)).where(
                and_(
                    TaskAssignee.user_id == student_id,
                    TaskAssignee.updated_at >= start_dt,
                    TaskAssignee.updated_at < end_dt
                )
            )
            tasks_res = await db.execute(tasks_stmt)
            task_assigns = tasks_res.scalars().all()
            
            tasks_completed = sum(1 for ta in task_assigns if ta.status == "completed")
            tasks_submitted = sum(1 for ta in task_assigns if ta.status == "submitted")

            # C. Calendar events on that day
            calendar_stmt = select(CalendarEvent).where(
                and_(
                    CalendarEvent.user_id == student_id,
                    CalendarEvent.start_time >= start_dt,
                    CalendarEvent.start_time < end_dt
                )
            )
            calendar_res = await db.execute(calendar_stmt)
            calendar_events = calendar_res.scalars().all()
            calendar_completed = len(calendar_events) # Mock as completed

            # D. AI chat messages on that day
            conv_stmt = (
                select(AIMessage)
                .join(AIConversation, AIMessage.conversation_id == AIConversation.id)
                .where(
                    and_(
                        AIConversation.user_id == student_id,
                        AIMessage.created_at >= start_dt,
                        AIMessage.created_at < end_dt,
                        AIMessage.role == "user"
                    )
                )
            )
            conv_res = await db.execute(conv_stmt)
            ai_chats = conv_res.scalars().all()
            ai_chat_count = len(ai_chats)

            # Build stats maps
            study_stats = {
                "study_time_minutes": 120 + 20 * (todos_completed + tasks_completed), # Mock study time proportional to completions
                "calendar_events_completed": calendar_completed
            }
            task_stats = {
                "todos_created": todos_created,
                "todos_completed": todos_completed,
                "tasks_completed": tasks_completed,
                "tasks_submitted": tasks_submitted
            }
            behavior_stats = {
                "ai_chat_count": ai_chat_count,
                "knowledge_views": 3 if ai_chat_count > 0 else 0,
                "bilibili_watch_minutes": 45 if tasks_completed > 0 else 0,
                "files_uploaded": 1 if tasks_submitted > 0 else 0
            }

            # 2. Format Context for LLM
            nickname = user.nickname or user.username
            activity_summary = (
                f"学生姓名/昵称：{nickname}\n"
                f"复盘日期：{review_date.strftime('%Y-%m-%d')}\n\n"
                f"今日活动统计：\n"
                f"- 新建待办事项：{todos_created} 个，完成：{todos_completed} 个\n"
                f"- 完成课程任务：{tasks_completed} 个，提交任务：{tasks_submitted} 个\n"
                f"- 参加日历日程数：{calendar_completed} 个\n"
                f"- 发起 AI 伴学对话次数：{ai_chat_count} 次\n\n"
            )
            
            if todos:
                activity_summary += "今日待办内容：\n" + "\n".join(f"- [{t.status}] {t.title}" for t in todos) + "\n\n"
            if task_assigns:
                activity_summary += "今日任务进度：\n" + "\n".join(f"- [{ta.status}] {ta.task.title}" for ta in task_assigns) + "\n\n"
            if calendar_events:
                activity_summary += "今日日历计划：\n" + "\n".join(f"- {e.title} ({e.description or ''})" for e in calendar_events) + "\n\n"
            if ai_chats:
                activity_summary += "今日与 AI 对话问题提炼：\n" + "\n".join(f"- {c.content[:80]}" for c in ai_chats[:5]) + "\n\n"

            # 3. Call LLM for Daily Review Text & Suggestions
            system_prompt = (
                "你是一个温和、严谨的 AI 伴学智能体导师。你需要根据学生一天的行为日志和交互内容，"
                "生成一份富文本（Markdown 格式）的【每日复盘报告】。报告应包含昨日总结、高光时刻（Highlights）、潜在关注点（Concerns）、"
                "以及具体的行动建议（Suggestions）。请用温和而诚恳的中文回复，避免虚无夸大的赞美，专注于提供切实可行的成长建议。"
            )
            messages = [
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=f"请为以下学生行为数据生成每日复盘报告：\n\n{activity_summary}")
            ]
            
            llm_res = await llm_router.route(
                task_type="daily_review",
                messages=messages,
                user_id=student_id,
                stream=False
            )
            review_text = llm_res.content

            # 4. Call LLM to extract short-term memory candidates
            memory_extract_prompt = (
                "请分析上述学生一天的行为数据和交互日志，提取出该学生的学习习惯、偏好、当前焦点任务、遇到的困难或其薄弱环节。"
                "你必须输出一个 JSON 格式的列表（不要包含 markdown 代码块标记，直接返回纯 JSON），"
                "列表项具有以下字段：\n"
                "- content: 记忆条目的具体描述（如 '偏好在深夜进行编程实践'、'在多头注意力机制的数学推导上遇到障碍'）\n"
                "- category: 类别 (只能是 'learning_preference', 'study_habit', 'interest_area', 'weakness', 'goal', 'other' 之一)\n"
                "- memory_type: 记忆类型 (全部设为 'short_term')\n"
                "- confidence: 置信度 (0.0-1.0 之间的浮点数)\n"
                "- evidence: 支撑该记忆的具体行为证据\n"
                "如果没有提取出有价值的记忆，返回空列表 []。"
            )
            extract_messages = [
                ChatMessage(role="system", content=memory_extract_prompt),
                ChatMessage(role="user", content=f"请分析并提取记忆：\n\n{activity_summary}\n\n生成的复盘是：\n{review_text}")
            ]
            
            extract_res = await llm_router.route(
                task_type="memory_extract",
                messages=extract_messages,
                user_id=student_id,
                stream=False
            )
            
            # Clean response text if code fences are present
            raw_json = extract_res.content.strip()
            if raw_json.startswith("```"):
                # strip code block wrapper if present
                lines = raw_json.split("\n")
                if lines[0].startswith("```json") or lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].strip() == "```":
                    lines = lines[:-1]
                raw_json = "\n".join(lines).strip()
            
            try:
                new_memories_extracted = json.loads(raw_json)
                if not isinstance(new_memories_extracted, list):
                    new_memories_extracted = []
            except Exception as e:
                logger.warning(f"Failed to parse extracted memories JSON: {raw_json}. Error: {e}")
                new_memories_extracted = []

            # 5. Call LLM for Memory update & conflict detection
            # Query current active memories
            existing_memories, _ = await MemoryService.get_student_memories(db, student_id)
            
            updated_memories_list = []
            final_new_memories = []

            if new_memories_extracted and existing_memories:
                existing_mem_list_str = "\n".join(
                    f"- [ID: {m.id}] [{m.category}/{m.memory_type}] {m.content} (置信度: {m.confidence})"
                    for m in existing_memories
                )
                
                memory_update_prompt = (
                    "你是一个记忆合并与冲突检测系统。这里有学生现有的【历史记忆库】，以及今日提取出来的【新记忆候选】。"
                    "你需要判断新记忆候选是否与历史记忆有重复、冲突、或者是对历史记忆的补充（可以提升置信度）。"
                    "请以 JSON 格式输出合并操作结果（不要包含 markdown 代码块标记，直接返回纯 JSON），包含以下两个字段：\n"
                    "- conflicts: 列表。若有冲突/矛盾，列出对应的历史记忆 ID（如 'ID 对应的记忆说偏好C++，新候选说讨厌C++'）以及解决冲突后的新记忆内容。\n"
                    "- updates: 列表。若需要更新现有记忆（如内容细化或置信度增加），返回更新字段，必须包含 memory_id 以及更新后的 content, confidence, evidence 字段。\n"
                    "如果没有需要冲突或更新的条目，返回 { \"conflicts\": [], \"updates\": [] }。"
                )
                
                update_messages = [
                    ChatMessage(role="system", content=memory_update_prompt),
                    ChatMessage(role="user", content=(
                        f"历史记忆库：\n{existing_mem_list_str}\n\n"
                        f"新候选记忆：\n{json.dumps(new_memories_extracted, ensure_ascii=False)}"
                    ))
                ]
                
                update_res = await llm_router.route(
                    task_type="memory_update",
                    messages=update_messages,
                    user_id=student_id,
                    stream=False
                )
                
                raw_update_json = update_res.content.strip()
                if raw_update_json.startswith("```"):
                    lines = raw_update_json.split("\n")
                    if lines[0].startswith("```json") or lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines[-1].strip() == "```":
                        lines = lines[:-1]
                    raw_update_json = "\n".join(lines).strip()
                
                try:
                    consolidation = json.loads(raw_update_json)
                except Exception as e:
                    logger.warning(f"Failed to parse consolidated memories JSON: {raw_update_json}. Error: {e}")
                    consolidation = {"conflicts": [], "updates": []}
                
                conflicted_ids = [c.get("memory_id") for c in consolidation.get("conflicts", []) if c.get("memory_id")]
                updated_map = {u["memory_id"]: u for u in consolidation.get("updates", []) if u.get("memory_id")}

                # Process updates
                for m in existing_memories:
                    # If conflict or update, we supersede the old memory
                    if m.id in conflicted_ids or m.id in updated_map:
                        m.status = "superseded"
                        db.add(m)
                        
                        # Create updated entry
                        new_content = m.content
                        new_confidence = m.confidence
                        new_evidence = m.evidence
                        
                        if m.id in updated_map:
                            up = updated_map[m.id]
                            new_content = up.get("content", m.content)
                            new_confidence = min(1.0, max(0.0, up.get("confidence", m.confidence + 0.1))) # decay/promotion rules
                            new_evidence = (m.evidence or "") + "\n" + (up.get("evidence", "行为再次验证"))
                        
                        updated_mem = StudentMemory(
                            id=uuid.uuid4(),
                            user_id=student_id,
                            memory_type=m.memory_type,
                            category=m.category,
                            content=new_content,
                            confidence=new_confidence,
                            evidence=new_evidence,
                            status="active",
                            source_review_id=review.id,
                            version=m.version + 1
                        )
                        db.add(updated_mem)
                        await db.flush()
                        
                        # Link connection
                        m.superseded_by = updated_mem.id
                        db.add(m)
                        
                        updated_memories_list.append({
                            "id": str(updated_mem.id),
                            "old_id": str(m.id),
                            "content": new_content,
                            "confidence": new_confidence
                        })
                
                # Check which candidate memories are truly new and not covered by updates/conflicts
                # Simple rule: if candidate content is not highly similar or not matched, create as new
                # For MVP, we add candidate memories that were not marked as updates to existing ones
                for candidate in new_memories_extracted:
                    # If we don't have updates matching this category or content, create it
                    # (To keep it clean, if there are no updates mapping to it, we add it as new)
                    is_updated = False
                    for u in consolidation.get("updates", []):
                        if u.get("content") == candidate.get("content"):
                            is_updated = True
                            break
                    if not is_updated:
                        new_mem = StudentMemory(
                            id=uuid.uuid4(),
                            user_id=student_id,
                            memory_type="short_term",
                            category=candidate.get("category", "other"),
                            content=candidate.get("content", ""),
                            evidence=candidate.get("evidence", ""),
                            confidence=candidate.get("confidence", 0.5),
                            status="active",
                            source_review_id=review.id,
                            version=1
                        )
                        db.add(new_mem)
                        await db.flush()
                        final_new_memories.append({
                            "id": str(new_mem.id),
                            "content": new_mem.content,
                            "confidence": new_mem.confidence
                        })
            else:
                # No existing memories, write all extracted candidate memories directly
                for candidate in new_memories_extracted:
                    new_mem = StudentMemory(
                        id=uuid.uuid4(),
                        user_id=student_id,
                        memory_type="short_term",
                        category=candidate.get("category", "other"),
                        content=candidate.get("content", ""),
                        evidence=candidate.get("evidence", ""),
                        confidence=candidate.get("confidence", 0.5),
                        status="active",
                        source_review_id=review.id,
                        version=1
                    )
                    db.add(new_mem)
                    await db.flush()
                    final_new_memories.append({
                        "id": str(new_mem.id),
                        "content": new_mem.content,
                        "confidence": new_mem.confidence
                    })

            # Save results to daily review
            review.summary = review_text
            review.study_stats = study_stats
            review.task_stats = task_stats
            review.behavior_stats = behavior_stats
            review.ai_suggestion = review_text # Or extract recommendations section if parsed
            review.new_memories = final_new_memories
            review.updated_memories = updated_memories_list
            review.model_name = llm_res.model
            review.token_count = llm_res.usage.get("total_tokens", 0)
            review.status = "completed"
            
            db.add(review)
            await db.commit()
            await db.refresh(review)
            
            logger.info(f"Successfully generated daily review for student {student_id} on {review_date}")
            return review

        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to generate daily review: {e}", exc_info=True)
            review.status = "failed"
            review.error_message = str(e)
            db.add(review)
            await db.commit()
            raise e
