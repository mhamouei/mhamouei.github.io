"""Publication data utilities. Python 3.11+; no third-party packages."""
from __future__ import annotations
import copy
import hashlib
import json
import os
import re
import tempfile
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, unquote

ROOT = Path(__file__).resolve().parents[1]

def load_json(path: Path) -> Any:
    with path.open(encoding='utf-8') as stream:
        return json.load(stream)

def atomic_json(path: Path, data: Any) -> None:
    """Do not replace the previous cache unless serialization and write succeed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(data, ensure_ascii=False, indent=2) + '\n'
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent,
                                     suffix='.tmp', delete=False) as stream:
        temp = Path(stream.name)
        stream.write(serialized)
    try:
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)

def normalized_title(title: str) -> str:
    value = unicodedata.normalize('NFKD', title).casefold()
    return ''.join(c for c in value if c.isalnum())

def normalized_doi(doi: str) -> str:
    return re.sub(r'^https?://(?:dx\.)?doi\.org/', '', doi.strip(), flags=re.I).lower()

def matches(a: dict, b: dict) -> bool:
    if a.get('scholar_id') and a.get('scholar_id') == b.get('scholar_id'):
        return True
    if a.get('id') and a.get('id') == b.get('id'):
        return True
    if a.get('doi') and b.get('doi'):
        # Different known DOIs represent different records even with equal titles.
        return normalized_doi(a['doi']) == normalized_doi(b['doi'])
    return bool(a.get('title') and b.get('title') and
                normalized_title(a['title']) == normalized_title(b['title']))

def record_id(record: dict) -> str:
    raw = record.get('scholar_id') or record.get('doi') or normalized_title(record['title'])
    return 'paper-' + hashlib.sha256(raw.encode()).hexdigest()[:14]

def validate_record(record: dict) -> None:
    if not isinstance(record, dict) or not isinstance(record.get('title'), str) or not record['title'].strip():
        raise ValueError('Every publication needs a nonempty title.')
    if not isinstance(record.get('authors'), list) or not record['authors'] or not all(isinstance(a, str) and a.strip() for a in record['authors']):
        raise ValueError('Every publication needs a nonempty authors array.')
    year = record.get('year')
    if year is not None and (isinstance(year, bool) or not isinstance(year, int) or not 1500 <= year <= 2200):
        raise ValueError('Year must be an integer in 1500–2200, or null.')
    if record.get('id') and not re.fullmatch(r'[a-z0-9][a-z0-9-]*', record['id']):
        raise ValueError('IDs must use lowercase letters, numbers, and hyphens.')
    for key in ('title','venue','doi','scholar_id','abstract','summary'):
        if key in record and not isinstance(record[key], str):
            raise ValueError(f'{key} must be a string.')
    for key in ('featured', 'hidden'):
        if key in record and not isinstance(record[key], bool):
            raise ValueError(f'{key} must be a boolean.')

def merge_records(existing: list[dict], incoming: list[dict]) -> list[dict]:
    """Keep old entries; deduplicate by ID, DOI, or exact normalized title.

    No fuzzy title matching: similar titles can legitimately identify different papers.
    A missing Scholar entry is not a command to delete an old publication.
    """
    result = copy.deepcopy(existing)
    for new in incoming:
        validate_record(new)
        found = [i for i, old in enumerate(result) if matches(old, new)]
        if len(found) > 1:
            raise ValueError('Ambiguous publication match; curate duplicate records before syncing.')
        if found:
            idx = found[0]
            stable_id = result[idx].get('id') or record_id(result[idx])
            merged = dict(result[idx])
            for key, value in new.items():
                if value is not None and value != '' and value != []:
                    # Preserve known full author lists if an overview is abbreviated.
                    if key == 'authors' and new.get('authors_incomplete') and not merged.get('authors_incomplete'):
                        continue
                    if key == 'authors_incomplete' and value and not merged.get('authors_incomplete'):
                        continue
                    merged[key] = copy.deepcopy(value)
            merged['id'] = stable_id
            result[idx] = merged
        else:
            copied = copy.deepcopy(new)
            copied.setdefault('id', record_id(copied))
            result.append(copied)
    for record in result:
        validate_record(record)
    return result

def override_matches(paper: dict, override: dict) -> bool:
    if override.get('id') == paper.get('id'):
        return True
    aliases = override.get('match', {})
    if paper.get('scholar_id') in aliases.get('scholar_ids', []):
        return True
    if paper.get('doi') and normalized_doi(paper['doi']) in {normalized_doi(d) for d in aliases.get('dois', [])}:
        return True
    return normalized_title(paper['title']) in {normalized_title(t) for t in aliases.get('titles', [])}

def publications(root: Path = ROOT) -> tuple[dict, list[dict]]:
    cache = load_json(root/'data/scholar_cache.json')
    manual = load_json(root/'data/manual_publications.json')['records']
    base = merge_records(cache['records'], manual)
    overrides = load_json(root/'data/publication_overrides.json')['papers']
    output = []
    for paper in base:
        found = [o for o in overrides if override_matches(paper, o)]
        if len(found) > 1:
            raise ValueError('Multiple overrides match the same publication.')
        if found:
            # A renamed Scholar record can be rejoined to its stable local URL.
            paper.update({k: copy.deepcopy(v) for k,v in found[0].items() if k != 'match'})
        paper.setdefault('id', record_id(paper))
        paper.setdefault('type', 'other')
        validate_record(paper)
        if not paper.get('hidden', False):
            output.append(paper)
    ids = [p['id'] for p in output]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate output IDs; merge or hide the duplicate records explicitly.')
    for override in overrides:
        if not any(override_matches(p, override) for p in base):
            print(f"Warning: unmatched override {override.get('id', '(no ID)')}.")
    return cache, sorted(output, key=lambda p: (-(p.get('year') or 0), not p.get('featured',False), p['title'].casefold()))

def safe_url(value: str, public_root: Path | None = None) -> str:
    """Accept HTTPS, HTTP, mailto, or checked root-relative local asset paths."""
    if not isinstance(value, str) or not value or re.search(r'[\x00-\x20\\]', value):
        raise ValueError('Invalid URL; encode spaces and remove control characters.')
    parts = urlsplit(value)
    if parts.scheme in ('https', 'http') and parts.hostname and not parts.username:
        return value
    if parts.scheme == 'mailto' and '@' in parts.path:
        return value
    if value.startswith('/') and not value.startswith('//'):
        decoded = unquote(parts.path)
        if '\\' in decoded or any(part == '..' for part in decoded.split('/')):
            raise ValueError('Unsafe local URL.')
        if public_root:
            target = (public_root / decoded.lstrip('/')).resolve()
            if not target.is_relative_to(public_root.resolve()) or not target.is_file():
                raise ValueError(f'Missing local file: {value}. Add it under public/ first.')
        return value
    raise ValueError('Only http(s), mailto, and root-relative local URLs are supported.')
