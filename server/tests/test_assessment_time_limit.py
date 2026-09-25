import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.core.exceptions import ValidationError
from app.services.assessment_service import AssessmentService


def paper_with(**target):
    return SimpleNamespace(publish_target=target)


def attempt_started(minutes_ago: int):
    return SimpleNamespace(started_at=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago))


class TimeLimitTests(unittest.TestCase):
    def test_blank_means_no_limit(self):
        self.assertIsNone(AssessmentService._normalize_time_limit(None))
        self.assertIsNone(AssessmentService._normalize_time_limit(""))

    def test_rejects_out_of_range_and_non_integers(self):
        for raw in (0, 1441, -5, "九十分", True):
            with self.subTest(raw=raw):
                with self.assertRaises(ValidationError):
                    AssessmentService._normalize_time_limit(raw)

    def test_accepts_a_normal_duration(self):
        self.assertEqual(AssessmentService._normalize_time_limit("90"), 90)

    def test_earlier_of_deadline_and_duration_wins(self):
        started = datetime(2026, 9, 26, 1, 0, tzinfo=timezone.utc)
        paper = paper_with(
            due_at="2026-09-26T03:00:00+00:00",
            time_limit_minutes=60,
        )
        attempt = SimpleNamespace(started_at=started)
        self.assertEqual(
            AssessmentService._effective_deadline(paper, attempt),
            started + timedelta(minutes=60),
        )

    def test_duration_without_a_start_does_not_invent_a_deadline(self):
        paper = paper_with(time_limit_minutes=30)
        self.assertIsNone(AssessmentService._effective_deadline(paper, SimpleNamespace(started_at=None)))

    def test_dirty_stored_limit_is_ignored(self):
        paper = paper_with(time_limit_minutes="soon")
        attempt = attempt_started(10)
        self.assertIsNone(AssessmentService._time_limit_end(paper, attempt))


if __name__ == "__main__":
    unittest.main()
