import unittest
from types import SimpleNamespace

from app.services.assessment_service import AssessmentService as A


class RequireFullscreenTests(unittest.TestCase):
    def test_missing_setting_defaults_to_required(self):
        # 老数据没有这个字段，必须按「要求全屏」处理，否则升级后旧卷会静默放宽
        paper = SimpleNamespace(publish_target={"type": "class", "ids": ["x"]})
        self.assertTrue(A.require_fullscreen_of(paper))

    def test_explicit_false_is_respected(self):
        paper = SimpleNamespace(publish_target={"require_fullscreen": False})
        self.assertFalse(A.require_fullscreen_of(paper))

    def test_explicit_true_is_respected(self):
        paper = SimpleNamespace(publish_target={"require_fullscreen": True})
        self.assertTrue(A.require_fullscreen_of(paper))

    def test_dirty_jsonb_does_not_raise(self):
        for target in ("oops", 3, [], None):
            paper = SimpleNamespace(publish_target=target)
            self.assertTrue(A.require_fullscreen_of(paper))

    def test_missing_paper_is_required(self):
        self.assertTrue(A.require_fullscreen_of(None))

    def test_string_false_from_legacy_data_is_read_as_false(self):
        paper = SimpleNamespace(publish_target={"require_fullscreen": "false"})
        self.assertFalse(A.require_fullscreen_of(paper))


if __name__ == "__main__":
    unittest.main()
