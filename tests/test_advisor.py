import os
import tempfile
import unittest
from unittest.mock import patch

from aetherflux.advisor import AdvisorService, apply_fallback_advisor
from aetherflux.deepseek import DeepSeekConfig, load_dotenv_values, parse_json_content


class FakeAdvisorClient:
    def advise_candidates(self, candidates):
        return {
            "items": [
                {
                    "id": candidates[0]["id"],
                    "display": {
                        "title_zh": "阳朔骑行路线在外网获得关注",
                        "title_en": "Yangshuo cycling route gets attention",
                        "summary_zh": "外网游客关注遇龙河骑行路线和竹筏票务指引。",
                        "summary_en": "Foreign travelers are asking about cycling routes and raft ticket guidance.",
                    },
                    "translation_status": "translated",
                    "advisor_notes": {
                        "confidence": 0.78,
                        "summary": "值得进入人工审阅，主要价值在外国游客动线和票务困惑。",
                        "opportunities": ["做一篇英文友好型遇龙河路线解释内容"],
                        "risks": ["单平台来源，需继续交叉验证"],
                        "human_questions": ["是否需要补充官方票务来源？"],
                    },
                    "cross_check": {
                        "status": "needs_more_sources",
                        "supporting_sources": [],
                        "conflicting_sources": [],
                        "needs_more_sources": True,
                        "reasoning": "目前只有外网讨论样本，缺少官方和国内评论验证。",
                    },
                    "geo_risk": {
                        "probability": 0.32,
                        "level": "medium",
                        "reasons": ["单一圈层来源", "存在路线推荐商业化可能"],
                    },
                }
            ]
        }


class AdvisorTests(unittest.TestCase):
    def test_fallback_adds_display_cross_check_and_geo_risk_without_model(self):
        candidate = {
            "id": "cand-1",
            "title": "Yangshuo cycling route gets attention",
            "summary": "Foreign travelers ask about the Yulong River route.",
            "language": "en",
            "signals": ["外国游客信号"],
        }

        enriched = apply_fallback_advisor([candidate])[0]

        self.assertEqual(enriched["display"]["title_en"], candidate["title"])
        self.assertEqual(enriched["display"]["summary_en"], candidate["summary"])
        self.assertEqual(enriched["translation_status"], "untranslated")
        self.assertEqual(enriched["cross_check"]["status"], "unverified")
        self.assertIn("probability", enriched["geo_risk"])
        self.assertEqual(enriched["advisor_notes"]["status"], "disabled")

    def test_advisor_service_merges_deepseek_structured_response(self):
        candidate = {
            "id": "cand-1",
            "title": "Yangshuo cycling route gets attention",
            "summary": "Foreign travelers ask about the Yulong River route.",
            "language": "en",
            "signals": ["外国游客信号"],
        }
        service = AdvisorService(client=FakeAdvisorClient())

        enriched = service.enrich_candidates([candidate])[0]

        self.assertEqual(enriched["display"]["title_zh"], "阳朔骑行路线在外网获得关注")
        self.assertEqual(enriched["translation_status"], "translated")
        self.assertEqual(enriched["cross_check"]["status"], "needs_more_sources")
        self.assertEqual(enriched["geo_risk"]["level"], "medium")
        self.assertEqual(enriched["advisor_notes"]["confidence"], 0.78)

    def test_deepseek_config_uses_environment_without_hardcoded_key(self):
        with patch.dict(
            os.environ,
            {
                "DEEPSEEK_API_KEY": "test-key",
                "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
                "DEEPSEEK_MODEL_ADVISOR": "deepseek-v4-pro",
            },
            clear=True,
        ):
            config = DeepSeekConfig.from_env()

        self.assertTrue(config.enabled)
        self.assertEqual(config.api_key, "test-key")
        self.assertEqual(config.base_url, "https://api.deepseek.com")
        self.assertEqual(config.model, "deepseek-v4-pro")

    def test_parse_json_content_strips_markdown_fences(self):
        payload = parse_json_content('```json\n{"items": [{"id": "cand-1"}]}\n```')

        self.assertEqual(payload["items"][0]["id"], "cand-1")

    def test_load_dotenv_values_reads_local_key_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = os.path.join(temp_dir, ".env")
            with open(env_path, "w", encoding="utf-8") as handle:
                handle.write("DEEPSEEK_API_KEY=local-key\n")
                handle.write("DEEPSEEK_MODEL_ADVISOR=deepseek-v4-pro\n")

            values = load_dotenv_values(env_path)

        self.assertEqual(values["DEEPSEEK_API_KEY"], "local-key")
        self.assertEqual(values["DEEPSEEK_MODEL_ADVISOR"], "deepseek-v4-pro")

    def test_deepseek_config_uses_dotenv_when_env_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = os.path.join(temp_dir, ".env")
            with open(env_path, "w", encoding="utf-8") as handle:
                handle.write("DEEPSEEK_API_KEY=local-key\n")
            with patch.dict(os.environ, {}, clear=True):
                config = DeepSeekConfig.from_env(dotenv_path=env_path)

        self.assertTrue(config.enabled)
        self.assertEqual(config.api_key, "local-key")


if __name__ == "__main__":
    unittest.main()
