"""成绩单：只汇总教师已经保存的分数，并渲染成 PDF。"""
from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List, Optional, Tuple

OBJECTIVE_TYPES = {"single", "multiple", "judge", "fill"}
# 编程题由教师确认给分（判题全通过时自动满分），计入主观分一列
SUBJECTIVE_TYPES = {"short", "essay", "code"}

STATUS_LABELS = {
    "in_progress": "作答中",
    "pending_review": "待批改",
    "submitted": "已交卷",
}


def summarize_saved_scores(
    status: Optional[str],
    answers: Iterable[Tuple[str, Optional[float], bool]],
) -> Dict[str, Any]:
    """客观分、主观分、总分。

    未批改的主观题不按 0 分计入。总分只在全部已保存且状态为已交卷时给出。
    这个函数不读取 AI 建议分，调用方也不该把建议分传进来。
    """
    if status in (None, "", "in_progress"):
        return {
            "objective_score": None,
            "subjective_score": None,
            "total_score": None,
            "pending": False,
        }

    objective = 0.0
    subjective = 0.0
    has_subjective = False
    pending = status == "pending_review"
    for question_type, score, graded in answers:
        if question_type in SUBJECTIVE_TYPES:
            has_subjective = True
            if graded:
                subjective += float(score or 0.0)
            else:
                pending = True
        elif question_type in OBJECTIVE_TYPES and graded:
            objective += float(score or 0.0)
        elif question_type in OBJECTIVE_TYPES and not graded:
            pending = True

    objective = round(objective, 2)
    subjective_score = round(subjective, 2) if has_subjective and not pending else None
    if has_subjective and pending:
        subjective_score = None
    total = None
    if status == "submitted" and not pending:
        total = round(objective + (subjective if has_subjective else 0.0), 2)
    return {
        "objective_score": objective,
        "subjective_score": subjective_score,
        "total_score": total,
        "pending": pending,
    }


def score_sheet_filename(title: str) -> str:
    cleaned = "".join(ch for ch in (title or "成绩单") if ch not in '\\/:*?"<>|').strip()
    return f"{cleaned or '成绩单'}-成绩单.pdf"


def find_cjk_font() -> str:
    candidates = [
        os.environ.get("SCORE_SHEET_FONT"),
        r"C:\Windows\Fonts\STSONG.TTF",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    raise FileNotFoundError("没有找到可用于成绩单的中文字体")


def render_score_sheet_pdf(sheet: Dict[str, Any]) -> bytes:
    from fpdf import FPDF

    font_path = find_cjk_font()
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_font("sheet", "", font_path)
    pdf.add_page()
    pdf.set_font("sheet", size=16)
    pdf.cell(0, 10, f"成绩单  {sheet.get('title') or ''}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("sheet", size=9)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(
        0,
        6,
        "只含教师已保存的分数。未批完的主观题留空，不记为 0 分，也不含 AI 建议分。",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(2)
    pdf.set_text_color(0, 0, 0)

    columns = [
        ("姓名", 36),
        ("账号", 36),
        ("状态", 24),
        ("客观分", 28),
        ("主观分", 28),
        ("总分", 24),
        ("待批", 22),
    ]
    pdf.set_font("sheet", size=10)
    pdf.set_fill_color(235, 240, 246)
    for label, width in columns:
        pdf.cell(width, 8, label, border=1, fill=True, align="C")
    pdf.ln()

    pdf.set_font("sheet", size=9)
    for row in sheet.get("rows") or []:
        values = [
            str(row.get("student_name") or ""),
            str(row.get("username") or ""),
            STATUS_LABELS.get(row.get("status") or "", "未作答"),
            _num(row.get("objective_score")),
            _num(row.get("subjective_score")),
            _num(row.get("total_score")),
            "是" if row.get("pending") else "否",
        ]
        for value, (_, width) in zip(values, columns):
            pdf.cell(width, 8, value, border=1)
        pdf.ln()
    return bytes(pdf.output())


def _num(value: Any) -> str:
    if value is None:
        return "—"
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.1f}"
