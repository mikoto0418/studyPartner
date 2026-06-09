from typing import Optional


def user_display_name(nickname: Optional[str]) -> str:
    return nickname.strip() if nickname and nickname.strip() else "未设置姓名"
