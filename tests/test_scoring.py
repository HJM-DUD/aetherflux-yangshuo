import unittest

from aetherflux.scoring import build_candidate, make_dedupe_key


class ScoringTests(unittest.TestCase):
    def test_build_candidate_scores_foreign_social_signal_without_llm(self):
        raw_item = {
            "title": "Yangshuo was beautiful but the Yulong River queue was confusing",
            "body": "Tripadvisor users mention long waits, unclear bamboo raft tickets, and great cycling routes.",
            "source": "Tripadvisor Forum",
            "platform": "tripadvisor",
            "url": "https://example.com/yangshuo-yulong-queue",
            "published_at": "2026-05-20T08:10:00Z",
            "engagement": {"likes": 120, "comments": 18, "shares": 6},
        }
        directions = {
            "places": ["遇龙河", "Yulong River", "西街", "兴坪", "Yangshuo"],
            "themes": [
                {"id": "foreign_signal", "label": "外国游客信号", "keywords": ["yangshuo", "tripadvisor", "foreigner"], "weight": 18},
                {"id": "risk", "label": "风险预警", "keywords": ["queue", "confusing", "complaint", "scam", "宰客"], "weight": 15},
                {"id": "opportunity", "label": "项目机会", "keywords": ["cycling", "route", "旅拍", "itinerary"], "weight": 12},
            ],
            "platform_weights": {"tripadvisor": 14, "xiaohongshu": 12, "douyin": 11},
        }

        candidate = build_candidate(raw_item, directions)

        self.assertEqual(candidate["language"], "en")
        self.assertEqual(candidate["category"], "foreign_signal")
        self.assertIn("外国游客信号", candidate["signals"])
        self.assertIn("风险预警", candidate["signals"])
        self.assertGreaterEqual(candidate["score"], 60)
        self.assertEqual(candidate["evidence"][0]["url"], raw_item["url"])

    def test_make_dedupe_key_groups_same_place_and_topic(self):
        first = {
            "title": "遇龙河竹筏排队很久，游客吐槽票务不清楚",
            "body": "今天很多人说遇龙河排队。",
            "platform": "xiaohongshu",
            "url": "https://example.com/a",
        }
        second = {
            "title": "游客反馈：遇龙河竹筏排队久，票务指引混乱",
            "body": "同一个问题在不同平台出现。",
            "platform": "douyin",
            "url": "https://example.com/b",
        }

        self.assertEqual(make_dedupe_key(first), make_dedupe_key(second))


if __name__ == "__main__":
    unittest.main()
