import unittest

from aetherflux.review import create_review_draft


class ReviewTests(unittest.TestCase):
    def test_create_review_draft_requires_human_approval(self):
        candidates = [
            {
                "id": "cand-foreign-risk",
                "title": "Foreign visitors confused by Yulong River ticketing",
                "summary": "Several foreign travelers report unclear queue and ticket instructions.",
                "score": 82,
                "category": "foreign_signal",
                "signals": ["外国游客信号", "风险预警"],
                "language": "en",
                "platform": "tripadvisor",
                "evidence": [{"url": "https://example.com/a", "source": "Tripadvisor Forum"}],
            },
            {
                "id": "cand-low",
                "title": "普通风景打卡",
                "summary": "一条低互动普通打卡。",
                "score": 35,
                "category": "general",
                "signals": [],
                "language": "zh",
                "platform": "xiaohongshu",
                "evidence": [{"url": "https://example.com/b", "source": "小红书"}],
            },
        ]

        draft = create_review_draft(candidates, top_n=3)

        self.assertEqual(draft["status"], "draft")
        self.assertFalse(draft["auto_publish"])
        self.assertEqual(draft["selected"][0]["id"], "cand-foreign-risk")
        self.assertIn("chief_editor", draft["role_assessments"])
        self.assertIn("foreign_traveler", draft["role_assessments"])
        self.assertIn("risk", draft["role_assessments"])
        self.assertGreaterEqual(len(draft["questions_for_human"]), 1)


if __name__ == "__main__":
    unittest.main()
