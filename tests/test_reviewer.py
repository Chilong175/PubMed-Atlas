from unittest import TestCase
from unittest.mock import Mock, patch

from app.services.pubmed_client import PubMedArticle
from app.services.reviewer import build_review_context, build_review_prompt, generate_review, validate_review, review_length


VALID_REVIEW = '\n'.join(f'{i}. ' + '本测试摘要仅讨论标志物与响应的相关性，不支持因果结论。' * 4 + ' [PMID:1]' for i in range(1,5))


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
        self.assertIn("综述暂未生成", result["review"])
        self.assertNotIn("免疫微环境", result["review"])
        self.assertEqual(result['source_pmids'], ['1'])

    @patch("app.services.reviewer.requests.post")
    def test_generate_review_parses_deepseek_response(self, mock_post: Mock) -> None:
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": VALID_REVIEW
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
        self.assertEqual(result['review'], VALID_REVIEW)
        self.assertTrue(400 <= result['body_length'] <= 650)
        self.assertEqual(result['source_pmids'], ['1'])
        self.assertEqual(mock_post.call_args.kwargs["json"]["model"], "deepseek-flash")
        self.assertEqual(mock_post.call_args.kwargs["json"]["thinking"], {"type": "disabled"})

    def test_context_budget_counts_separators_and_deduplicates(self):
        articles = [PubMedArticle(str(i), 'Title', 'A' * 1000, 2025, 'Journal', []) for i in range(100)]
        context = build_review_context(articles + articles, max_context_chars=500)
        self.assertLessEqual(len(context.text), 500)
        self.assertEqual(context.eligible_count, 100)
        context = build_review_context(articles + articles)
        self.assertEqual(len({s.pmid for s in context.sources}), len(context.sources))
        self.assertLessEqual(len(context.sources), 20)
        self.assertLessEqual(len(context.text), 12000)

    def test_invalid_length_and_fabricated_citations_are_rejected(self):
        context = build_review_context([PubMedArticle('1', 'Title', 'Abstract', 2025, 'Journal', [])])
        self.assertEqual(validate_review(VALID_REVIEW, context), [])
        self.assertTrue(validate_review('1. Too short [PMID:1]', context))
        self.assertTrue(validate_review(VALID_REVIEW.replace('PMID:1', 'PMID:999'), context))
        self.assertTrue(validate_review(VALID_REVIEW.replace('[PMID:1]', ''), context))

    @patch('app.services.reviewer._call_deepseek')
    def test_one_repair_then_clear_failure_instead_of_fabricated_review(self, call):
        articles = [PubMedArticle('1', 'Title', 'Abstract', 2025, 'Journal', [])]
        call.side_effect = ['Too short', VALID_REVIEW]
        result = generate_review(articles, api_key='test')
        self.assertFalse(result['used_fallback'])
        self.assertEqual(call.call_count, 2)
        call.reset_mock(side_effect=True)
        call.return_value = 'Too short'
        result = generate_review(articles, api_key='test')
        self.assertTrue(result['used_fallback'])
        self.assertIn('校验', result['failure_reason'])
        self.assertEqual(call.call_count, 2)
