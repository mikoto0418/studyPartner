"""1022 二面专用初始化及名单导出：python -m app.interview_1022 --help."""
import argparse
import asyncio
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import selectinload

from app.core.database import SessionLocal, engine
from app.core.security import get_password_hash
from app.models import Base
from app.models.learning_path import ClassGroup, ClassMember, ClassTeacher
from app.models.user import Role, StudentProfile, User, UserRole

CLASS_NAME = "1022二面"
CLASS_ID = uuid5(NAMESPACE_URL, "studypartner:interview:1022:class")
TEACHERS = [f"tea1022{i}" for i in range(1, 4)]
STUDENTS = [f"stu1022{i:02d}" for i in range(1, 41)]


def account_id(username):
    return uuid5(NAMESPACE_URL, f"studypartner:interview:1022:{username}")


async def seed_interview(db):
    """所有数据在调用方的单一事务内写入；发生冲突时整体回滚。"""
    # 防止两个初始化进程同时执行。
    await db.execute(text("SELECT pg_advisory_xact_lock(10221022)"))
    roles = {}
    for code, name in (("teacher", "教师"), ("student", "学生")):
        role = (await db.execute(select(Role).where(Role.code == code))).scalars().first()
        if role and role.deleted_at:
            raise ValueError(f"角色 {code} 已删除，请先修复角色配置")
        if not role:
            role = Role(code=code, name=name)
            db.add(role)
            await db.flush()
        roles[code] = role

    created = 0
    for username in TEACHERS + STUDENTS:
        code = "teacher" if username in TEACHERS else "student"
        user = (
            await db.execute(
                select(User).options(selectinload(User.roles), selectinload(User.student_profile))
                .where(User.username == username)
            )
        ).scalars().first()
        if user:
            if (
                user.id != account_id(username)
                or user.deleted_at
                or user.status != "active"
                or user.role_codes != [code]
            ):
                raise ValueError(f"账号 {username} 已存在但不属于本批次或状态异常；已停止，未覆盖")
            if code == "student" and (
                not user.student_profile
                or (user.student_profile.extra_info or {}).get("interview_batch") != "1022"
            ):
                raise ValueError(f"账号 {username} 的批次档案异常；已停止，未覆盖")
            continue
        user = User(
            id=account_id(username),
            username=username,
            email=f"{username}@interview.example.com",
            password_hash=get_password_hash(username),
            nickname=f"二面老师 {TEACHERS.index(username) + 1}" if code == "teacher" else None,
            status="active",
        )
        db.add(user)
        await db.flush()
        db.add(UserRole(user_id=user.id, role_id=roles[code].id))
        if code == "student":
            db.add(StudentProfile(
                user_id=user.id,
                student_id=username,
                extra_info={"interview_batch": "1022", "identity_required": True},
            ))
        created += 1
    await db.flush()

    group = await db.get(ClassGroup, CLASS_ID)
    if group:
        if group.name != CLASS_NAME or group.teacher_id != account_id(TEACHERS[0]) or group.deleted_at:
            raise ValueError("1022 班级数据异常，已停止，未覆盖")
    else:
        same_name = (await db.execute(
            select(ClassGroup.id).where(ClassGroup.name == CLASS_NAME, ClassGroup.deleted_at.is_(None))
        )).first()
        if same_name:
            raise ValueError("已有其他来源的同名班级，已停止，未覆盖")
        db.add(ClassGroup(
            id=CLASS_ID, teacher_id=account_id(TEACHERS[0]), name=CLASS_NAME,
            description="1022 二面专用班级，3 位老师共同管理 40 位学生。",
            status="active",
        ))
        await db.flush()

    for username in TEACHERS:
        key = (CLASS_ID, account_id(username))
        if not await db.get(ClassTeacher, key):
            db.add(ClassTeacher(class_id=key[0], teacher_id=key[1]))
    for username in STUDENTS:
        uid = account_id(username)
        member = (await db.execute(
            select(ClassMember).where(ClassMember.class_id == CLASS_ID, ClassMember.user_id == uid)
        )).scalars().first()
        if member:
            if member.status != "active" or member.deleted_at:
                raise ValueError(f"{username} 的班级成员状态异常，已停止，未覆盖")
        else:
            db.add(ClassMember(
                class_id=CLASS_ID, user_id=uid, role="student",
                joined_at=datetime.now(timezone.utc), status="active",
            ))
    await db.flush()
    return created


async def prepare_empty_database():
    async with engine.begin() as connection:
        tables = await connection.run_sync(lambda conn: inspect(conn).get_table_names())
        if not tables:
            # 旧 initial migration 引用实时 metadata，后续 add_column 不能重放到新库。
            # 新库直接按当前模型建表，再记录对应版本；已有库仍执行正式迁移。
            await connection.run_sync(Base.metadata.create_all)
            return True
        if "alembic_version" not in tables:
            raise ValueError("已有数据库缺少迁移记录，拒绝自动标记或覆盖；请先核验其结构")
        return False


async def export_roster(db, destination):
    users = (await db.execute(
        select(User).options(selectinload(User.roles), selectinload(User.student_profile))
        .where(User.id.in_([account_id(name) for name in TEACHERS + STUDENTS]))
        .order_by(User.username)
    )).scalars().all()
    stream = sys.stdout if destination == "-" else open(destination, "w", newline="", encoding="utf-8-sig")
    try:
        writer = csv.writer(stream)
        writer.writerow(["班级", "角色", "账号", "初始密码（仅新建时）", "姓名", "姓名已确认"])
        for user in users:
            name = user.nickname or ""
            # Excel 打开 CSV 时不将用户输入的姓名作为公式执行。
            if name.startswith(("=", "+", "-", "@", "\t", "\r")):
                name = "'" + name
            writer.writerow([
                CLASS_NAME, "老师" if "teacher" in user.role_codes else "学生",
                user.username, user.username, name,
                "否" if user.requires_identity_confirmation else "是",
            ])
    finally:
        if stream is not sys.stdout:
            stream.close()


async def run(args):
    try:
        async with SessionLocal() as db:
            if not args.roster_only:
                async with db.begin():
                    created = await seed_interview(db)
                print(f"{CLASS_NAME}：新增 {created} 个账号，3 位老师 / 40 位学生；已有姓名和密码保留。", file=sys.stderr)
                from app.exam_1022 import ensure_exam
                paper, created_paper = await ensure_exam(db)
                print(f"考试草稿：{paper.title}，{'新建' if created_paper else '保留现有内容'}，{paper.question_count} 题。", file=sys.stderr)
            if args.export:
                await export_roster(db, args.export)
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--init-db", action="store_true", help="空库建表，已有库执行迁移")
    parser.add_argument("--export", metavar="CSV", help="导出账号及当前姓名，- 表示标准输出")
    parser.add_argument("--roster-only", action="store_true", help="仅导出，不建号")
    args = parser.parse_args()
    if args.roster_only and (not args.export or args.init_db):
        parser.error("--roster-only 必须配合 --export，且不能使用 --init-db")
    if args.init_db:
        async def prepare():
            try:
                return await prepare_empty_database()
            finally:
                await engine.dispose()
        fresh = asyncio.run(prepare())
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
        if fresh:
            command.stamp(config, "head")
        else:
            command.upgrade(config, "head")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
