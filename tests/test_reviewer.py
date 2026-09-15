from unittest import TestCase
from unittest.mock import Mock, patch

from app.services.pubmed_client import PubMedArticle
from app.services.reviewer import build_review_context, build_review_prompt, generate_review


class ReviewerTest(TestCase):
    def test_build_review_context_filters_and_limits_abstracts(self) -> None:
        articles = [
            PubMedArticle(
                pmid="1",
                title="High impact immunotherapy study",
                abstract="A" * 120,
                year=2025,
                journal="Cancer Cell",
                authors=[],
                doi=None,
            ),
            PubMedArticle(
                pmid="2",
                title="Missing abstract",
                abstract="",
                year=2024,
                journal="Clinical Cancer Research",
                authors=[],
                doi=None,
            ),
        ]
        setattr(articles[0], "impact_factor", 50.3)

        context = build_review_context(
            articles,
            max_articles=5,
            max_abstract_chars=20,
            max_context_chars=500,
        )

        self.assertEqual(len(context.sources), 1)
        self.assertIn("High impact immunotherapy study", context.text)
        self.assertIn("摘要：" + "A" * 20, context.text)
        self.assertNotIn("Missing abstract", context.text)

    def test_build_review_prompt_contains_output_constraints(self) -> None:
        article = PubMedArticle(
            pmid="1",
            title="Immunotherapy biomarkers",
            abstract="Biomarkers are associated with response.",
            year=2025,
            journal="Cancer Cell",
            authors=[],
            doi=None,
        )

        prompt = build_review_prompt(build_review_context([article]))

        self.assertIn("中文输出", prompt)
        self.assertIn("约 500 字", prompt)
        self.assertIn("不要编造", prompt)
        self.assertIn("Immunotherapy biomarkers", prompt)

    def test_generate_review_uses_fallback_without_api_key(self) -> None:
        article = PubMedArticle(
            pmid="1",
            title="Immunotherapy biomarkers",
            abstract="Biomarkers are associated with response.",
            year=2025,
            journal="Cancer Cell",
            authors=[],
            doi=None,
        )

        result = generate_review([article], api_key="", use_mock_on_error=True)

        self.assertTrue(result["used_fallback"])
        self.assertEqual(result["source_count"], 1)
        self.assertIn("兜底综述", result["review"])

    @patch("app.services.reviewer.requests.post")
    def test_generate_review_parses_deepseek_response(self, mock_post: Mock) -> None:
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "1. 这是中文综述。\n2. 研究集中在免疫治疗。"
                    }
                }
            ]
        }
        mock_post.return_value = response
        article = PubMedArticle(
            pmid="1",
            title="Immunotherapy biomarkers",
            abstract="Biomarkers are associated with response.",
            year=2025,
            journal="Cancer Cell",
            authors=[],
            doi=None,
        )

        result = generate_review([article], api_key="test-key", model="deepseek-flash")

        self.assertFalse(result["used_fallback"])
        self.assertIn("中文综述", result["review"])
        self.assertEqual(mock_post.call_args.kwargs["json"]["model"], "deepseek-flash")

