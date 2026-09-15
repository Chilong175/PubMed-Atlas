import xml.etree.ElementTree as ET
from unittest import TestCase

from app.services.pubmed_client import PubMedClient


PUBMED_ARTICLE_XML = """
<PubmedArticle>
  <MedlineCitation>
    <PMID>12345678</PMID>
    <Article>
      <Journal>
        <JournalIssue>
          <PubDate>
            <Year>2024</Year>
          </PubDate>
        </JournalIssue>
        <Title>Journal of Demo Medicine</Title>
        <ISOAbbreviation>J Demo Med</ISOAbbreviation>
      </Journal>
      <ArticleTitle>Demo PubMed parsing for immunotherapy.</ArticleTitle>
      <ELocationID EIdType="doi">10.1000/demo.2024.001</ELocationID>
      <Abstract>
        <AbstractText Label="BACKGROUND">Background sentence.</AbstractText>
        <AbstractText Label="METHODS">Methods sentence.</AbstractText>
      </Abstract>
      <AuthorList>
        <Author>
          <LastName>Zhang</LastName>
          <Initials>Y</Initials>
        </Author>
        <Author>
          <LastName>Li</LastName>
          <Initials>M</Initials>
        </Author>
      </AuthorList>
    </Article>
  </MedlineCitation>
  <PubmedData>
    <ArticleIdList>
      <ArticleId IdType="pubmed">12345678</ArticleId>
      <ArticleId IdType="doi">10.1000/demo.2024.001</ArticleId>
    </ArticleIdList>
  </PubmedData>
</PubmedArticle>
"""


class PubMedArticleParsingTest(TestCase):
    def test_parse_article_extracts_core_fields(self) -> None:
        node = ET.fromstring(PUBMED_ARTICLE_XML)

        article = PubMedClient()._parse_article(node)

        self.assertIsNotNone(article)
        assert article is not None
        self.assertEqual(article.pmid, "12345678")
        self.assertEqual(article.title, "Demo PubMed parsing for immunotherapy.")
        self.assertEqual(article.abstract, "Background sentence.\nMethods sentence.")
        self.assertEqual(article.year, 2024)
        self.assertEqual(article.journal, "Journal of Demo Medicine")
        self.assertEqual(article.authors, ["Zhang Y", "Li M"])
        self.assertEqual(article.doi, "10.1000/demo.2024.001")

