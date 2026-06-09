import asyncio
import os
import sys
import uuid

import pytest

sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "server"))

from app.api.v1.reviews import resolve_review_student_id
from app.core.exceptions import PermissionDenied, ValidationError


class _User:
    def __init__(self, user_id, roles):
        self.id = user_id
        self.role_codes = roles


def test_student_review_generation_defaults_to_current_user():
    user_id = uuid.uuid4()
    user = _User(user_id, ["student"])

    resolved = asyncio.run(resolve_review_student_id(None, user, None))

    assert resolved == user_id


def test_student_review_generation_rejects_other_student_id():
    user = _User(uuid.uuid4(), ["student"])

    with pytest.raises(PermissionDenied):
        asyncio.run(resolve_review_student_id(None, user, uuid.uuid4()))


def test_staff_review_generation_requires_student_id():
    teacher = _User(uuid.uuid4(), ["teacher"])

    with pytest.raises(ValidationError):
        asyncio.run(resolve_review_student_id(None, teacher, None))
