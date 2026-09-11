"""Offline unit tests: no API key, account, or network access needed."""
from __future__ import annotations
import copy
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit, unquote

from scripts.common import ROOT, publications, merge_records, safe_url, normalized_title
from scripts.build import Site, bibtex
from scripts.sync_scholar import SyncError, retrieve, run, enrich


def article(sid='AUTHOR:a', title='An Example Paper', year='2026'):
    return {'citation_id':sid,'title':title,'authors':'Ada Lovelace, Alan Turing','year':year,
            'publication':'A Journal','cited_by':{'value':3}}

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if tag in ('a','script','link','img'):
            self.links += [attrs[k] for k in ('href','src') if k in attrs]

class DataTests(unittest.TestCase):
    def setUp(self):
        self.base = {'id':'stable-id','title':'An Example: Paper!','authors':['Ada Lovelace'],'year':2025,'doi':'10.1/test'}
    def test_normalized_title(self):
        self.assertEqual(normalized_title('Paper: Test!'), normalized_title('paper test'))
    def test_stable_ids_survive_update(self):
        new = {**self.base,'id':'another-id','year':2026}
        data = merge_records([self.base],[new])
        self.assertEqual(len(data),1)
        self.assertEqual(data[0]['id'],'stable-id')
        self.assertEqual(data[0]['year'],2026)
    def test_missing_remote_record_not_deleted(self):
        self.assertEqual(merge_records([self.base],[]),[self.base])
    def test_different_dois_not_merged(self):
        self.assertEqual(len(merge_records([self.base],[{**self.base,'id':'different','doi':'10.1/different'}])),2)
    def test_full_authors_preserved(self):
        old = {**self.base,'authors':['Ada Lovelace','Alan Turing']}
        new = {**self.base,'authors':['Ada Lovelace'],'authors_incomplete':True}
        self.assertEqual(merge_records([old],[new])[0]['authors'],old['authors'])
    def test_overrides_and_manual_are_separate(self):
        files = [ROOT/'data/publication_overrides.json',ROOT/'data/manual_publications.json']
        before = [p.read_bytes() for p in files]
        _, papers = publications()
        self.assertTrue(any(p.get('code') for p in papers))
        self.assertEqual(before,[p.read_bytes() for p in files])
    def test_unsafe_urls_rejected(self):
        for value in ['javascript:alert(1)','//evil.com/x','/../data/profile.json','/%2e%2e/secrets','data:text/html,hi','/x\\y.pdf','https://user:pass@example.com/']:
            with self.subTest(value=value),self.assertRaises(ValueError):
                safe_url(value,ROOT/'public')
    def test_missing_pdf_rejected(self):
        with self.assertRaises(ValueError):
            safe_url('/papers/missing.pdf',ROOT/'public')
    def test_safe_external_url(self):
        self.assertEqual(safe_url('https://arxiv.org/pdf/123'), 'https://arxiv.org/pdf/123')
    def test_bibtex_special_characters(self):
        result = bibtex({**self.base,'title':'A & B: 100% {test}'})
        self.assertIn(r'\&', result)
        self.assertIn(r'\%', result)
        self.assertIn(r'\{test\}', result)

class SyncTests(unittest.TestCase):
    def test_no_key_keeps_cache(self):
        path = ROOT/'data/scholar_cache.json'
        before = path.read_bytes()
        with patch.dict(os.environ, {'SERPAPI_KEY':''}):
            self.assertEqual(run(),0)
        self.assertEqual(before,path.read_bytes())
    def test_pagination_collects_all_pages(self):
        calls = []
        def fake(params,key):
            calls.append(params['start'])
            return {'articles':[article('AUTHOR:a' if params['start']==0 else 'AUTHOR:b',title='First' if params['start']==0 else 'Second')]} if params['start']<2 else {'articles':[]}
        items = retrieve('AUTHOR','test-key',{'page_size':1,'max_pages':4,'fetch_details':False},[],fake)
        self.assertEqual(len(items),2)
        self.assertEqual(calls,[0,1,2])
    def test_empty_first_page_rejected(self):
        with self.assertRaises(SyncError):
            retrieve('AUTHOR','test',{},[],lambda *args:{'articles':[]})
    def test_duplicate_pages_rejected(self):
        with self.assertRaises(SyncError):
            retrieve('AUTHOR','test',{'page_size':1,'max_pages':3,'fetch_details':False},[],lambda *args:{'articles':[article()]})
    def test_max_pages_is_not_silently_partial(self):
        with self.assertRaises(SyncError):
            retrieve('AUTHOR','test',{'page_size':1,'max_pages':1,'fetch_details':False},[],lambda *args:{'articles':[article()]})
    def test_wrong_author_rejected(self):
        with self.assertRaises(SyncError):
            retrieve('OTHER','test',{},[],lambda *args:{'articles':[article()]})
    def test_citation_enrichment(self):
        record = {'title':'An Example Paper','authors':['A Lovelace'],'year':2026}
        result = enrich(record,{'citation':{'title':'An Example Paper','authors':'Ada Lovelace, Alan Turing','journal':'Journal','publication_date':'2026/8','volume':'3'}})
        self.assertEqual(result['authors'],['Ada Lovelace','Alan Turing'])
        self.assertEqual(result['type'],'journal')
    def test_preprint_repository_not_labeled_as_journal(self):
        record = {'title':'An Example Paper','authors':['Ada Lovelace'],'year':2026}
        result = enrich(record,{'citation':{'title':'An Example Paper','journal':'arXiv preprint arXiv:2601.12345'}})
        self.assertEqual(result['type'],'preprint')
    def test_mismatch_detail_rejected(self):
        with self.assertRaises(SyncError):
            enrich({'title':'First'},{'citation':{'title':'Second'}})
    def test_failed_sync_preserves_every_data_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT/'data',root/'data')
            paths = list((root/'data').glob('*.json'))
            before = [p.read_bytes() for p in paths]
            with patch.dict(os.environ,{'SERPAPI_KEY':'not-a-real-key'}),patch('scripts.sync_scholar.retrieve',side_effect=SyncError('Offline test')):
                with self.assertRaises(SyncError):
                    run(root)
            self.assertEqual(before,[p.read_bytes() for p in paths])

class BuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for folder in ['data','public','templates']:
            shutil.copytree(ROOT/folder,self.root/folder)
    def tearDown(self):
        self.temp.cleanup()
    def test_full_build_links_and_unique_ids(self):
        out = Site(self.root).write()
        files = list(out.rglob('*.html'))
        self.assertEqual(len(files),len(Site(self.root).papers)+3)
        for page in files:
            parser = Links()
            parser.feed(page.read_text(encoding='utf8'))
            self.assertEqual(len(parser.ids),len(set(parser.ids)))
            for href in parser.links:
                path = urlsplit(href)
                if path.scheme or path.netloc or not path.path:
                    continue
                target = (out/path.path.lstrip('/')) if path.path.startswith('/') else (page.parent/unquote(path.path))
                if href.split('#')[0].endswith('/'):
                    target /= 'index.html'
                self.assertTrue(target.is_file(), f'{page}: missing {href}')
    def test_html_escapes_remote_titles(self):
        data_path = self.root/'data/manual_publications.json'
        data_path.write_text(json.dumps({'records':[{'id':'unsafe-title','title':'<script>alert(1)</script>','authors':['<b>Test</b>'],'year':2026}]}))
        site = Site(self.root)
        html = site.publication_list()
        self.assertNotIn('<script>alert(1)</script>',html)
        self.assertIn('&lt;script&gt;',html)
    def test_no_fake_cv_link(self):
        site = Site(self.root)
        site.profile['cv'] = ''
        self.assertNotIn('>CV</a>',site.home())
    def test_pdf_addition_creates_links_and_metadata(self):
        (self.root/'public/papers/test.pdf').write_bytes(b'%PDF-test-placeholder-for-unit-test-only')
        path = self.root/'data/publication_overrides.json'
        data = json.loads(path.read_text())
        data['papers'][0]['preprint']='/papers/test.pdf'
        path.write_text(json.dumps(data))
        site = Site(self.root)
        paper = next(p for p in site.papers if p['id']==data['papers'][0]['id'])
        html = site.paper_page(paper)
        self.assertIn('citation_pdf_url',html)
        self.assertIn('download>Download PDF',html)
        self.assertTrue((site.write()/'papers/test.pdf').exists())
    def test_missing_pdf_does_not_replace_good_build(self):
        out = Site(self.root).write()
        before = (out/'index.html').read_bytes()
        path = self.root/'data/publication_overrides.json'
        data = json.loads(path.read_text())
        data['papers'][0]['preprint']='/papers/missing.pdf'
        path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            Site(self.root).write()
        self.assertEqual(before,(out/'index.html').read_bytes())

if __name__ == '__main__':
    unittest.main()
