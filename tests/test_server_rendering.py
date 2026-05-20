import unittest

from aetherflux.server import render_index


class ServerRenderingTests(unittest.TestCase):
    def test_index_renders_decision_dashboard_shell(self):
        html = render_index()

        self.assertIn("阳朔旅游情报决策台", html)
        self.assertIn("app.js", html)
        self.assertIn("styles.css", html)
        self.assertNotIn("游客攻略", html)


if __name__ == "__main__":
    unittest.main()
