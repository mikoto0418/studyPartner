"""从标准 JSON / 压缩包导入试卷（不走 AI 拆题）。

包格式：

    paper-import.zip
    ├── paper.json     { paper: {...}, questions: [...] }
    └── assets/        题目图片，JSON 里用 "assets/xxx" 相对路径引用

也接受单独的 paper.json（图片用外链 url）。导入后试卷为 awaiting_review，
由教师人工校对；图片落进对象存储，题干里的 [[IMG:n]] 占位符原样保留。
"""
from __future__ import annotations

import asyncio
import io
import json
import re
import zipfile
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.models.assessment import AssessmentPaper, AssessmentQuestion
from app.services import question_parser as question_parser_module
from app.services.minio_service import MinioService

IMAGE_EXTS = {"png", "jpg", "jpeg", "gif", "webp", "bmp"}


def _read_package(file_bytes: bytes, filename: str) -> Tuple[Dict[str, Any], Dict[str, bytes]]:
    """返回 (JSON 内容, {包内相对路径: 图片字节})。ZIP 与纯 JSON 都接受。"""
    lower = (filename or "").lower()
    if lower.endswith(".zip") or file_bytes[:2] == b"PK":
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as archive:
                names = [n for n in archive.namelist() if not n.endswith("/")]
                json_names = [n for n in names if n.lower().endswith(".json")]
                # 优先取根目录的 paper.json，其次任意 json
                json_name = next(
                    (n for n in json_names if "/" not in n.strip("/")), None
                ) or (json_names[0] if json_names else None)
                if not json_name:
                    raise ValidationError("压缩包里没有找到 paper.json")
                payload = json.loads(archive.read(json_name).decode("utf-8-sig"))
                # Windows 压缩工具会把条目名写成 assets\image-1.jpg（反斜杠），
                # 而 JSON 里按规范写的是 assets/image-1.jpg。不归一化就一张图都对不上，
                # 而且会静默丢图 —— 所以这里统一转成正斜杠再建索引。
                assets = {
                    n.replace("\\", "/"): archive.read(n)
                    for n in names
                    if n.rsplit(".", 1)[-1].lower() in IMAGE_EXTS
                }
        except zipfile.BadZipFile as exc:
            raise ValidationError(f"压缩包无法解析：{exc}")
        except (UnicodeDecodeError, ValueError) as exc:
            raise ValidationError(f"包内 JSON 解析失败：{exc}")
    else:
        try:
            payload = json.loads(file_bytes.decode("utf-8-sig"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise ValidationError(f"JSON 解析失败：{exc}")
        assets = {}

    if not isinstance(payload, dict):
        raise ValidationError("JSON 顶层必须是对象（形如 { paper, questions }）")
    return payload, assets


def _optional_score(raw: Any) -> Optional[float]:
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _image_index(image: dict, asset: Optional[str], fallback: int) -> int:
    """[[IMG:n]] 里的 n 必须和这里的 index 对上。

    前端（RichStem）是按 index 建映射、再把占位符换成图片的；缺了这个字段，
    题干里的 [[IMG:1]] 就会显示成「[图片缺失]」。优先用显式 index，其次从文件名
    里的数字推（image-1.jpg → 1），最后退回数组顺序。
    """
    raw = image.get("index")
    if raw is not None:
        try:
            return int(raw)
        except (TypeError, ValueError):
            pass
    if asset:
        digits = re.search(r"(\d+)", asset.rsplit("/", 1)[-1])
        if digits:
            return int(digits.group(1))
    return fallback


def _resolve_images(
    raw_images: Any, asset_meta: Dict[str, Dict[str, str]]
) -> Optional[List[dict]]:
    """把包内相对路径（asset）或外链（url）统一成 [{index, object_name, url}]。"""
    out: List[dict] = []
    for position, image in enumerate(raw_images or [], start=1):
        if not isinstance(image, dict):
            continue
        asset = image.get("asset")
        meta = asset_meta.get(asset) if asset else None
        url = image.get("url") or (meta or {}).get("url")
        if not url:
            continue
        object_name = image.get("object_name") or (meta or {}).get("object_name")
        out.append({
            "index": _image_index(image, asset, position),
            "object_name": object_name,
            "url": url,
        })
    return out or None


async def import_paper_from_package(
    db: AsyncSession,
    file_id: UUID,
    teacher_id: UUID,
    title_override: Optional[str] = None,
) -> AssessmentPaper:
    row = (
        await db.execute(
            text(
                "select original_name, storage_path from files "
                "where id = :i and deleted_at is null"
            ),
            {"i": str(file_id)},
        )
    ).first()
    if not row:
        raise ValidationError("导入文件不存在")

    file_bytes = await asyncio.to_thread(MinioService.download_file, row[1])
    payload, assets = _read_package(file_bytes, row[0])

    questions_in = payload.get("questions") or []
    if not isinstance(questions_in, list) or not questions_in:
        raise ValidationError("JSON 里没有题目（questions 为空）")

    # 包内图片先落对象存储，再在题目里换成可访问的地址；取不到字节的整条跳过
    asset_meta: Dict[str, Dict[str, str]] = {}
    for relative, blob in assets.items():
        if not blob:
            continue
        ext = relative.rsplit(".", 1)[-1].lower() if "." in relative else "png"
        object_name = f"assessment/imported/{file_id}/{relative.replace('/', '_')}"
        await asyncio.to_thread(
            MinioService.upload_file,
            object_name,
            io.BytesIO(blob),
            len(blob),
            f"image/{ext}",
        )
        url = await asyncio.to_thread(
            MinioService.get_download_url, object_name, 7 * 24 * 3600
        )
        asset_meta[relative] = {"object_name": object_name, "url": url}

    paper_meta = payload.get("paper") or {}
    title = (
        title_override
        or (paper_meta.get("title") if isinstance(paper_meta, dict) else None)
        or (row[0].rsplit(".", 1)[0] if row[0] else "")
        or "导入试卷"
    ).strip()

    total_score = 0.0
    has_unknown_score = False
    normalized: List[Dict[str, Any]] = []
    for index, item in enumerate(questions_in):
        if not isinstance(item, dict):
            continue
        stem = str(item.get("stem") or "").strip()
        if not stem:
            continue
        question_type = str(item.get("question_type") or "short").strip()
        is_code = question_type == "code"
        score = _optional_score(item.get("score"))
        if score is None:
            has_unknown_score = True
        else:
            total_score += score
        normalized.append({
            "order_index": int(item.get("order_index") if item.get("order_index") is not None else index),
            "question_type": question_type,
            "stem": stem,
            "stem_images": _resolve_images(item.get("images") or item.get("stem_images"), asset_meta),
            "options": question_parser_module.normalize_options(item.get("options")),
            "answer": item.get("answer"),
            "analysis": item.get("analysis"),
            "language": (
                question_parser_module.normalize_code_language(item.get("language"))
                if is_code
                else None
            ),
            "test_cases": (
                question_parser_module.normalize_test_cases(item.get("test_cases"))
                if is_code
                else None
            ),
            "starter_code": (item.get("starter_code") or None) if is_code else None,
            "score": score,
            "difficulty": item.get("difficulty"),
            "tags": item.get("tags") or None,
        })

    if not normalized:
        raise ValidationError("JSON 里的题目都缺少题干（stem），无法导入")

    paper = AssessmentPaper(
        creator_id=teacher_id,
        title=title,
        description=(paper_meta.get("description") if isinstance(paper_meta, dict) else None),
        source_file_id=file_id,
        parse_status="awaiting_review",
        question_count=len(normalized),
        # 有题没填分值时整卷满分未知，存 null，与其它入口口径一致
        total_score=None if has_unknown_score else round(total_score, 2),
    )
    db.add(paper)
    await db.flush()

    for item in normalized:
        db.add(
            AssessmentQuestion(
                paper_id=paper.id,
                order_index=item["order_index"],
                question_type=item["question_type"],
                stem=item["stem"],
                stem_images=item["stem_images"],
                options=item["options"],
                answer=item["answer"],
                analysis=item["analysis"],
                language=item["language"],
                test_cases=item["test_cases"],
                starter_code=item["starter_code"],
                score=item["score"],
                difficulty=item["difficulty"],
                tags=item["tags"],
            )
        )

    await db.commit()
    await db.refresh(paper)
    return paper


async def build_paper_package(
    db: AsyncSession, paper_id: UUID, teacher_id: UUID
) -> Tuple[str, bytes]:
    """把一张卷导出成「标准包」：paper.json + assets/ 的 zip。

    这是 import_paper_from_package 的逆操作，两边共用同一套格式定义 —— 导出的包
    改完可以直接导回来。图片从对象存储取原始字节，不再二次压缩（无损）。
    """
    paper = (
        await db.execute(
            select(AssessmentPaper).where(
                AssessmentPaper.id == paper_id,
                AssessmentPaper.creator_id == teacher_id,
            )
        )
    ).scalars().first()
    if not paper:
        raise ValidationError("试卷不存在")

    rows = (
        await db.execute(
            select(AssessmentQuestion)
            .where(AssessmentQuestion.paper_id == paper_id)
            .order_by(AssessmentQuestion.order_index.asc())
        )
    ).scalars().all()

    questions: List[Dict[str, Any]] = []
    assets: List[Tuple[str, bytes]] = []
    for question in rows:
        images: List[dict] = []
        for image in question.stem_images or []:
            object_name = image.get("object_name") if isinstance(image, dict) else None
            if not object_name:
                continue
            try:
                blob = await asyncio.to_thread(MinioService.download_file, object_name)
            except Exception:
                # 图取不到就少这一张，不要因为一张图让整包导不出来
                continue
            if not blob:
                continue
            relative = f"assets/{object_name.rsplit('/', 1)[-1]}"
            assets.append((relative, blob))
            # 带上 index，导出的包再导回来时 [[IMG:n]] 才对得上
            entry: Dict[str, Any] = {"asset": relative}
            if isinstance(image, dict) and image.get("index") is not None:
                entry["index"] = image["index"]
            images.append(entry)
        questions.append({
            "order_index": question.order_index,
            "question_type": question.question_type,
            "stem": question.stem,
            "images": images or None,
            "options": question.options,
            "answer": question.answer,
            "analysis": question.analysis,
            "score": question.score,
            "language": question.language,
            "test_cases": question.test_cases,
            "starter_code": question.starter_code,
            "difficulty": question.difficulty,
            "tags": question.tags,
        })

    payload = {
        "paper": {"title": paper.title, "description": paper.description},
        "questions": questions,
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("paper.json", json.dumps(payload, ensure_ascii=False, indent=2))
        for relative, blob in assets:
            archive.writestr(relative, blob)

    safe = "".join(ch for ch in (paper.title or "试卷") if ch not in '\\/:*?"<>|').strip()
    return f"{safe or '试卷'}-题目包.zip", buffer.getvalue()