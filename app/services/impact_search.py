"""Search by descending journal JIF, independent of the visible results page."""
from datetime import date
import time

from app.services.analyzer import enrich_articles, top_impact_articles
from app.services.pubmed_client import PubMedClient, PubMedClientError


def search_top_impact(keyword, metrics, client: PubMedClient, *, today=None, pause=time.sleep):
    today = today or date.today()
    first_year = today.year - 4
    rows = metrics.dropna(subset=['impact_factor']).sort_values('impact_factor', ascending=False, kind='stable')
    selected, seen = [], set()
    inspected = 0
    checked = 0
    unresolved = 0
    truncated = False
    for _, row in rows.iterrows():
        checked += 1
        # Quoted exact journal names/identifiers, not fuzzy title similarity.
        terms = [row['journal_name'], *str(row.get('journal_alias', '')).split(';')]
        identifiers = [str(row.get(column, '')) for column in ('issn', 'eissn') if row.get(column)]
        names = ' OR '.join(f'"{term.replace(chr(34), " ")}"[Journal]' for term in dict.fromkeys(terms) if term)
        ids = ' OR '.join(f'"{term}"[ISSN]' for term in dict.fromkeys(identifiers))
        journals = f'({names})' + (f' OR ({ids})' if ids else '')
        query = f'({keyword}) AND ({journals}) AND ("{first_year}/01/01"[Date - Publication] : "{today:%Y/%m/%d}"[Date - Publication])'
        offset = 0
        while True:
            pause(.35)
            total, pmids = client.esearch(query, 100, retstart=offset, sort='pub_date')
            if not pmids:
                if offset < total:
                    raise PubMedClientError('PubMed returned an incomplete ranking page')
                break
            pause(.35)
            articles = client.efetch(pmids)
            inspected += len(pmids)
            unresolved += len(set(pmids) - {article.pmid for article in articles})
            for article in enrich_articles(articles, metrics):
                if article.pmid in seen:
                    continue
                seen.add(article.pmid)
                if article.impact_factor is None or article.impact_factor != float(row['impact_factor']):
                    unresolved += 1
                    continue
                if article.year is None or not first_year <= article.year <= today.year:
                    unresolved += 1
                    continue
                selected.append(article)
            # Lower JIF journals cannot displace 100 already selected papers.
            # Ties at the cutoff may be any equally ranked papers, not all tied papers.
            if len(selected) >= 100:
                break
            offset += len(pmids)
            if offset >= total:
                break
            if offset >= 10000:
                truncated = True
                break
        if len(selected) >= 100:
            break
    return {
        'articles': top_impact_articles(selected, current_year=today.year, limit=100),
        'scope': 'covered_journals', 'global_complete': False,
        'ranking_complete_within_table': not truncated and unresolved == 0,
        'start_date': f'{first_year}-01-01', 'end_date': today.isoformat(),
        'journal_count': len(rows), 'journals_checked': checked,
        'records_inspected': inspected, 'unresolved_records': unresolved,
        'truncated': truncated, 'source_years': sorted(int(y) for y in metrics['source_year'].dropna().unique()),
    }
