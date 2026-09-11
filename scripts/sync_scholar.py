#!/usr/bin/env python3
"""Cache Google Scholar publication metadata through the third-party SerpApi API.

No Scholar credentials, CAPTCHA bypass, browser scraping, or browser-side secrets.
Failures never overwrite the previous cache. Requires SERPAPI_KEY to sync.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone, timedelta
import html
import json
import os
import re
import sys
from pathlib import Path
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
try:
    from .common import ROOT, load_json, atomic_json, merge_records, validate_record, normalized_title
except ImportError:
    from common import ROOT, load_json, atomic_json, merge_records, validate_record, normalized_title

class SyncError(RuntimeError):
    pass

def plain(value) -> str:
    return html.unescape(re.sub(r'<[^>]+>', '', str(value or ''))).strip()

def api_request(params: dict, key: str) -> dict:
    url = 'https://serpapi.com/search.json?' + urlencode({**params, 'api_key': key})
    try:
        request = Request(url, headers={'User-Agent': 'AcademicSitePublicationSync/1.0'})
        with urlopen(request, timeout=60) as response:
            raw = response.read(8_000_001)
        if len(raw) > 8_000_000:
            raise SyncError('Provider response exceeds the safety limit.')
        payload = json.loads(raw)
    except HTTPError as error:
        # Do not print exception objects or full URLs: these can contain the key.
        raise SyncError(f'Provider HTTP error {error.code}; previous cache retained.') from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise SyncError('Provider connection or JSON failure; previous cache retained.') from None
    if not isinstance(payload, dict) or payload.get('error') or payload.get('search_metadata', {}).get('status') not in (None,'Success'):
        raise SyncError('Provider returned an error/incomplete response; previous cache retained.')
    return payload

def parse_article(article: dict, author_id: str) -> dict:
    sid = plain(article.get('citation_id'))
    if not sid.startswith(author_id + ':'):
        raise SyncError('Missing or unexpected Scholar citation identifier.')
    author_text = plain(article.get('authors'))
    authors = [name.strip() for name in author_text.split(',') if name.strip() and name.strip() not in ('...', '…')]
    year_text = plain(article.get('year'))
    if year_text and not re.fullmatch(r'\d{4}', year_text):
        raise SyncError('Unexpected publication year; previous cache retained.')
    result = {'scholar_id':sid, 'title':plain(article.get('title')), 'authors':authors,
              'authors_incomplete':bool('...' in author_text or '…' in author_text or 'et al' in author_text.lower()),
              'year':int(year_text) if year_text else None, 'venue':plain(article.get('publication')),
              'scholar_url':'https://scholar.google.com/citations?' + urlencode({'view_op':'view_citation','user':author_id,'citation_for_view':sid,'hl':'en'})}
    count = article.get('cited_by', {}).get('value')
    if isinstance(count, int) and not isinstance(count,bool) and count >= 0:
        result['citations'] = count
    validate_record(result)
    return result

def enrich(paper: dict, response: dict) -> dict:
    citation = response.get('citation')
    if not isinstance(citation, dict) or not citation.get('title'):
        raise SyncError('Missing citation detail; previous cache retained.')
    # A mismatch usually indicates an upstream API or stale-data error.
    if normalized_title(plain(citation['title'])) != normalized_title(paper['title']):
        raise SyncError('Citation detail title does not match the requested article.')
    text = plain(citation.get('authors'))
    if text:
        paper['authors'] = [a.strip() for a in text.split(',') if a.strip() and a.strip() not in ('...','…')]
        paper['authors_incomplete'] = '...' in text or '…' in text or 'et al' in text.lower()
    venue = plain(citation.get('journal') or citation.get('conference') or citation.get('book'))
    if venue:
        paper['venue'] = venue
    # Scholar sometimes places repository preprints in its 'journal' field.
    if re.search(r'\b(?:arxiv|biorxiv|medrxiv|preprints?)\b', venue, re.I):
        paper['type'] = 'preprint'
    elif citation.get('journal'):
        paper['type'] = 'journal'
    elif citation.get('conference'):
        paper['type'] = 'conference'
    date = plain(citation.get('publication_date'))
    if re.match(r'^\d{4}(?:/\d{1,2}(?:/\d{1,2})?)?$', date):
        paper['year'] = int(date[:4])
        paper['publication_date'] = date.replace('/', '-')
    for field in ('volume', 'issue', 'pages'):
        if citation.get(field):
            paper['number' if field == 'issue' else field] = plain(citation[field])
    if citation.get('description'):
        paper['abstract'] = plain(citation['description'])
    paper['details_fetched_at'] = datetime.now(timezone.utc).isoformat()
    # Do not automatically label any resource as a preprint or copy its PDF.
    # Publisher links can refer to paywalled/final versions. Owner adds links manually.
    validate_record(paper)
    return paper

def retrieve(author_id: str, key: str, config: dict, old: list[dict], request=api_request) -> list[dict]:
    size = int(config.get('page_size',100))
    max_pages = int(config.get('max_pages',10))
    detail_limit = int(config.get('max_detail_requests',40))
    if not 1 <= size <= 100 or not 1 <= max_pages <= 100 or not 0 <= detail_limit <= 1000:
        raise SyncError('Invalid sync limits.')
    previous = {p.get('scholar_id'):p for p in old if p.get('scholar_id')}
    incoming, seen = [], set()
    for page in range(max_pages):
        result = request({'engine':'google_scholar_author','author_id':author_id,'hl':'en',
                          'sort':'pubdate','num':size,'start':page*size}, key)
        rows = result.get('articles')
        if not isinstance(rows, list) or (page == 0 and not rows):
            raise SyncError('Missing or empty publications list; previous cache retained.')
        for raw in rows:
            record = parse_article(raw, author_id)
            if record['scholar_id'] in seen:
                raise SyncError('Repeated article across pages; refusing a possibly partial sync.')
            seen.add(record['scholar_id'])
            incoming.append(record)
        has_next = bool(result.get('serpapi_pagination', {}).get('next'))
        # If next is absent but a page is full, request one more page for safety.
        if not has_next and len(rows) < size:
            break
    else:
        raise SyncError('Pagination limit reached; raise max_pages before syncing.')
    used_details = 0
    for record in incoming:
        old_record = previous.get(record['scholar_id'])
        needs_details = not old_record or any(old_record.get(k) != record.get(k) for k in ('title','year'))
        if old_record and old_record.get('details_fetched_at'):
            try:
                stale = datetime.fromisoformat(old_record['details_fetched_at']) < datetime.now(timezone.utc)-timedelta(days=90)
                needs_details = needs_details or stale
            except (ValueError, TypeError):
                needs_details = True
        else:
            needs_details = True
        if config.get('fetch_details',True) and needs_details and used_details < detail_limit:
            detail = request({'engine':'google_scholar_author','author_id':author_id,'hl':'en',
                              'view_op':'view_citation','citation_id':record['scholar_id']}, key)
            enrich(record, detail)
            used_details += 1
        elif old_record and old_record.get('details_fetched_at'):
            # Keep rich detail fields rather than overwriting them with the overview.
            for field in ('authors','authors_incomplete','venue','type','volume','number','pages','year','publication_date'):
                if field in old_record:
                    record[field] = old_record[field]
    return incoming

def run(root: Path = ROOT) -> int:
    key = os.environ.get('SERPAPI_KEY', '').strip()
    if not key:
        print('SERPAPI_KEY is not set. No sync performed; the site can build from the saved publications.')
        return 0
    profile = load_json(root/'data/profile.json')
    path = root/'data/scholar_cache.json'
    cache = load_json(path)
    if cache.get('profile_id') != profile['scholar_id']:
        raise SyncError('Profile ID differs from the cache. Review/reset the cache before changing authors.')
    incoming = retrieve(profile['scholar_id'], key, load_json(root/'data/sync_config.json'), cache['records'])
    updated = {**cache,'source':'Google Scholar via SerpApi','last_successful_sync':datetime.now(timezone.utc).isoformat(),
               'records':merge_records(cache['records'], incoming)}
    # Exactly one atomic write; override and manual files are never opened for writing.
    atomic_json(path, updated)
    print(f"Synced {len(incoming)} Scholar records; cached {len(updated['records'])} publications.")
    return 0

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        sys.exit(run(args.root.resolve()))
    except (SyncError, ValueError, KeyError, TypeError, OSError):
        print('Scholar sync failed validation or could not complete. Previous publications are unchanged. Check the API account, profile, and configuration.', file=sys.stderr)
        sys.exit(1)
