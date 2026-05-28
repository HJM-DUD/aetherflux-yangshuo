import unittest

from aetherflux.live_collectors import (
    BrowserConnectionError,
    DouyinLiveCollector,
    FakeBrowserSession,
    XiaohongshuLiveCollector,
    collect_live_platform,
)


class LiveCollectorTests(unittest.TestCase):
    def test_xiaohongshu_live_collector_builds_search_url_and_normalizes_cards(self):
        session = FakeBrowserSession(
            cards=[
                {
                    "title": "阳朔遇龙河竹筏排队",
                    "body": "视频里提到排队和票务",
                    "url": "https://www.xiaohongshu.com/explore/abc123",
                    "author": "旅拍用户",
                    "likes": "12",
                    "comments": "3",
                    "has_video": True,
                    "cover_url": "https://sns-img.example/cover.jpg",
                    "comments_sample": [{"id": "c1", "text": "排队太久", "likes": 5}],
                }
            ],
            details_by_url={
                "https://www.xiaohongshu.com/explore/abc123": {
                    "body": "详情页补全文案，提到竹筏排队和价格",
                    "comments_sample": [{"id": "d1", "text": "价格有点贵", "likes": 7}],
                    "duration_seconds": 64,
                }
            },
        )

        collector = XiaohongshuLiveCollector(session)
        items = collector.search("阳朔 竹筏", "bamboo_rafting", max_items=5, detail_limit=1)

        self.assertIn("xiaohongshu.com/search_result", session.visited_urls[0])
        self.assertEqual(items[0]["platform"], "xiaohongshu")
        self.assertEqual(items[0]["content_type"], "video")
        self.assertEqual(items[0]["engagement"]["likes"], 12)
        self.assertIn("详情页补全文案", items[0]["body"])
        self.assertEqual(items[0]["comments"][0]["text"], "价格有点贵")
        self.assertEqual(items[0]["media"]["planned_keyframes"], [0, 15, 30, 32, 45, 60, 64])
        self.assertEqual(items[0]["media"]["cover_url"], "https://sns-img.example/cover.jpg")
        self.assertEqual(items[0]["quality_status"], "accepted")

    def test_douyin_live_collector_builds_search_url_and_normalizes_video_cards(self):
        session = FakeBrowserSession(
            cards=[
                {
                    "title": "阳朔西街夜游",
                    "body": "抖音视频文案",
                    "url": "https://www.douyin.com/video/712345",
                    "author": "本地向导",
                    "likes": 102,
                    "comments": 16,
                    "shares": 7,
                    "duration_seconds": 73,
                    "comments_sample": [{"id": "hot", "text": "这个路线不错", "likes": 9}],
                }
            ]
        )

        collector = DouyinLiveCollector(session)
        items = collector.search("阳朔 西街", "food_nightlife", max_items=5)

        self.assertIn("douyin.com/search", session.visited_urls[0])
        self.assertEqual(items[0]["platform"], "douyin")
        self.assertEqual(items[0]["content_type"], "video")
        self.assertEqual(items[0]["engagement"]["shares"], 7)
        self.assertEqual(items[0]["media"]["duration_seconds"], 73)
        self.assertEqual(items[0]["comments"][0]["id"], "hot")

    def test_live_collector_can_skip_seen_search_results(self):
        session = FakeBrowserSession(
            cards=[
                {"title": "第一条", "body": "第一条内容足够长", "url": "https://www.xiaohongshu.com/explore/one"},
                {"title": "第二条", "body": "第二条内容足够长", "url": "https://www.xiaohongshu.com/explore/two"},
            ]
        )

        collector = XiaohongshuLiveCollector(session)
        items = collector.search("阳朔 旅游", "tourism-live", max_items=1, detail_limit=0, skip_items=1)

        self.assertEqual(items[0]["title"], "第二条")

    def test_live_collector_marks_security_limit_pages_as_rejected(self):
        session = FakeBrowserSession(
            cards=[
                {
                    "title": "用户服务协议",
                    "body": "安全限制 访问链接异常 300017 我要反馈 返回首页",
                    "url": "https://www.douyin.com/agreements/",
                    "cover_url": "data:image/png;base64,abc",
                }
            ]
        )

        collector = DouyinLiveCollector(session)
        items = collector.search("阳朔 旅游", "tourism-live", max_items=1, detail_limit=0)

        self.assertEqual(items[0]["quality_status"], "rejected")
        self.assertIn("blocked_or_noise_page", items[0]["reject_reason"])

    def test_collect_live_platform_reports_actionable_error_when_cdp_is_missing(self):
        with self.assertRaises(BrowserConnectionError) as context:
            collect_live_platform("xiaohongshu", "阳朔", cdp_url="http://127.0.0.1:1")

        self.assertIn("Chrome remote debugging", str(context.exception))
        self.assertIn("9222", str(context.exception))


if __name__ == "__main__":
    unittest.main()
