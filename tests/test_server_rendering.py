import unittest

from aetherflux.server import render_index


class ServerRenderingTests(unittest.TestCase):
    def test_index_renders_decision_dashboard_shell(self):
        html = render_index()

        self.assertIn("阳朔旅游情报决策台", html)
        self.assertIn("以太通量", html)
        self.assertIn("DeepSeek V4 智库层", html)
        self.assertIn("交叉验证中心", html)
        self.assertIn("GEO 疑似度", html)
        self.assertIn("小红书首采", html)
        self.assertIn("中文待 DeepSeek 翻译", html)
        self.assertIn("app.js", html)
        self.assertIn("styles.css", html)
        self.assertIn("国内外差异", html)
        self.assertNotIn("PC 负责采集清洗", html)
        self.assertNotIn("游客攻略", html)


if __name__ == "__main__":
    unittest.main()
