#!/usr/bin/env python3
"""Build a static, accessible academic website. Standard library only."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
import re
import shutil
from string import Template
from urllib.parse import quote, urlsplit
try:
    from .common import ROOT, load_json, publications, safe_url
except ImportError:
    from common import ROOT, load_json, publications, safe_url

def e(value) -> str:
    return escape(str(value), quote=True)

def tex(value) -> str:
    mapping = {'\\':r'\textbackslash{}','{':r'\{','}':r'\}','&':r'\&','%':r'\%','$':r'\$','#':r'\#','_':r'\_','~':r'\textasciitilde{}','^':r'\textasciicircum{}'}
    return ''.join(mapping.get(c,c) for c in str(value))

def bibtex(paper: dict) -> str:
    if paper.get('bibtex'):
        return paper['bibtex'].strip() + '\n'
    kind = {'journal':'article','conference':'inproceedings'}.get(paper.get('type'), 'misc')
    authors = ' and '.join(paper['authors'])
    if paper.get('authors_incomplete'):
        authors += ' and others'
    fields = {'title':'{' + tex(paper['title']) + '}', 'author':tex(authors)}
    if paper.get('year'):
        fields['year'] = str(paper['year'])
    if paper.get('venue'):
        key = 'journal' if kind == 'article' else 'booktitle' if kind == 'inproceedings' else 'howpublished'
        fields[key] = tex(paper['venue'])
    for name in ('volume','number','pages','doi'):
        if paper.get(name):
            fields[name] = tex(paper[name])
    return '@' + kind + '{' + paper['id'].replace('-','') + ',\n' + ',\n'.join(f'  {key} = {{{val}}}' for key,val in fields.items()) + '\n}\n'

class Site:
    def __init__(self, root: Path):
        self.root = root
        self.profile = load_json(root/'data/profile.json')
        self.cache, self.papers = publications(root)
        self.template = Template((root/'templates/page.html').read_text(encoding='utf-8'))
        self.base = safe_url(self.profile['site_url']).rstrip('/')
        self.scholar = 'https://scholar.google.com/citations?user=' + quote(self.profile['scholar_id']) + '&hl=en'

    def url(self, raw: str, prefix: str = '') -> str:
        value = safe_url(raw, self.root/'public')
        return prefix + value.lstrip('/') if value.startswith('/') else value

    def link(self, raw: str, label: str, prefix: str = '', css: str = '') -> str:
        href = self.url(raw, prefix)
        return f'<a href="{e(href)}"' + (f' class="{e(css)}"' if css else '') + f'>{e(label)}</a>'

    def authors(self, paper: dict) -> str:
        aliases = {self.profile['name'].casefold(), 'm amouei', 'm. amouei', 'mh amouei', 'm. h. amouei'}
        names = [f'<strong>{e(name)}</strong>' if name.casefold() in aliases else e(name) for name in paper['authors']]
        return ', '.join(names) + (' et al.' if paper.get('authors_incomplete') else '')

    def citation(self, paper: dict, prefix: str, opened: bool = False) -> str:
        ident = 'bib-' + paper['id']
        return f'''<details class="citation-details"{' open' if opened else ''}>
          <summary>BibTeX</summary><pre id="{e(ident)}">{e(bibtex(paper))}</pre>
          <div class="copy-row"><button class="link-pill" type="button" data-copy="{e(ident)}" hidden>Copy BibTeX</button>
          <a class="link-pill" href="{prefix}citations/{e(paper['id'])}.bib" download>Download .bib</a></div></details>'''

    def links(self, paper: dict, prefix: str) -> str:
        items = []
        if paper.get('preprint'):
            raw = paper['preprint']
            href = self.url(raw,prefix)
            label = paper.get('preprint_label','Preprint PDF')
            items.append(f'<a class="link-pill primary" href="{e(href)}">{e(label)} <span aria-hidden="true">↗</span></a>')
            if raw.startswith('/'):
                items.append(f'<a class="link-pill" href="{e(href)}" download>Download PDF <span aria-hidden="true">↓</span></a>')
        if paper.get('doi'):
            items.append(self.link('https://doi.org/' + quote(paper['doi'],safe='/'), 'DOI ↗', prefix, 'link-pill'))
        for field,label in [('code','Code ↗'),('project','Project ↗'),('slides','Slides ↗'),('dataset','Data ↗'),('scholar_url','Scholar ↗')]:
            if paper.get(field):
                items.append(self.link(paper[field], label, prefix, 'link-pill'))
        return '<div class="pub-links">' + ''.join(items) + '</div>'

    def venue(self, paper: dict) -> str:
        badge = f'<span class="venue-short">{e(paper["venue_short"])}</span>' if paper.get('venue_short') else ''
        venue = e(paper.get('venue',''))
        if paper.get('status'):
            venue += ' · ' + e(paper['status'])
        if self.profile.get('show_citation_counts') and 'citations' in paper:
            venue += f' · {int(paper["citations"])} citations'
        return badge + venue

    def card(self, paper: dict, prefix: str) -> str:
        search = ' '.join([paper['title'], *paper['authors'], paper.get('venue',''), paper.get('summary','')])
        summary = f'<p class="pub-summary">{e(paper["summary"])}</p>' if paper.get('summary') else ''
        return f'''<article class="publication" data-publication data-type="{e(paper['type'])}" data-year="{e(paper.get('year') or '')}" data-pdf="{str(bool(paper.get('preprint'))).lower()}" data-search="{e(search)}">
        <div class="pub-year">{e(paper.get('year') or 'n.d.')}</div><div class="pub-content">
        <h3 class="pub-title"><a href="{prefix}publications/{e(paper['id'])}/">{e(paper['title'])}</a></h3>
        <p class="pub-authors">{self.authors(paper)}</p><p class="pub-venue">{self.venue(paper)}</p>
        {summary}{self.links(paper,prefix)}{self.citation(paper,prefix)}</div></article>'''

    def page(self, body: str, path: str, title: str, description: str = '', metadata: str = '') -> str:
        p = self.profile
        # A 404 can be served at any unknown path; its links must be absolute.
        prefix = self.base + '/' if path == '404.html' else '../' * (len(Path(path).parts)-1)
        nav = [('About',prefix+'index.html'),('Research',prefix+'index.html#research'),('Publications',prefix+'publications/'),('Teaching',prefix+'index.html#teaching')]
        if p.get('cv'):
            nav.append(('CV', self.url(p['cv'],prefix)))
        nav.append(('Contact',prefix+'index.html#contact'))
        active = 'Publications' if path.startswith('publications/') else 'About'
        navigation = ''.join(f'<a href="{e(href)}"' + (' aria-current="page"' if label==active else '') + f'>{label}</a>' for label,href in nav)
        canonical = self.base+'/' + path.removesuffix('index.html')
        return self.template.substitute(description=e(description or p['intro']),name=e(p['name']),title=e(title),canonical=e(canonical),prefix=prefix,metadata=metadata,navigation=navigation,body=body,short_name=e(p['short_name']),year=datetime.now(timezone.utc).year,email=e(p['email']))

    def home(self) -> str:
        p = self.profile
        first, _, last = p['name'].rpartition(' ')
        bio = ''.join(f'<p>{e(para)}</p>' for para in p['bio'])
        social = self.link('mailto:'+p['email'],'Email ↗') + self.link(self.scholar,'Google Scholar ↗') + self.link(p['github_url'],'GitHub ↗')
        if p.get('cv'):
            social += self.link(p['cv'], 'Curriculum vitae ↓')
        portrait = f'<img class="portrait" src="{e(self.url(p["portrait"]))}" alt="{e(p["name"])}" width="120" height="140">' if p.get('portrait') else ''
        research = ''.join(f'<article class="research-item"><span class="number">0{i+1}</span><h3>{e(r["title"])}</h3><p>{e(r["text"])}</p><p class="keywords">{e(r["tags"])}</p></article>' for i,r in enumerate(p['research']))
        featured = [r for r in self.papers if r.get('featured')][:p.get('featured_limit',4)]
        if not featured:
            featured = self.papers[:p.get('featured_limit',4)]
        cards = ''.join(self.card(r,'') for r in featured)
        education = ''.join(f'<div class="timeline-item"><h3>{e(r["degree"])}</h3><p>{e(r["institution"])}</p><small>{e(r["dates"])}</small></div>' for r in p['education'])
        teaching = ''.join(f'<div class="timeline-item"><h3>{e(r["title"])}</h3><p>{e(r["detail"])}</p></div>' for r in p['teaching'])
        body = f'''<section class="hero" id="about" aria-labelledby="name-heading">
          <div class="hero-main"><span class="eyebrow">{e(p['tagline'])}</span>
          <h1 id="name-heading">{e(first)}<span class="name-last">{e(last)}</span></h1>
          <p class="hero-subtitle">{e(p['role'])}<span> / </span>{e(p['university'])}</p>
          <p class="intro">{e(p['intro'])}</p><div class="bio">{bio}</div><div class="hero-links">{social}</div></div>
          <aside class="affiliation" aria-label="Academic affiliation"><div>{portrait}<span class="eyebrow">Affiliation</span>
          <h2>{self.link(p['university_url'],p['university'])}</h2><p>{e(p['department'])}</p></div>
          <div class="affiliation-lab"><div class="affiliation-rule"></div><span class="eyebrow">Research group</span>
          <p>{e(p['lab'])}</p>{self.link(p['lab_url'],'DMaS Lab ↗')}</div></aside></section>
          <section class="section" id="research"><div class="section-top"><h2>Research directions</h2></div><div class="research-grid">{research}</div></section>
          <section class="section" id="publications"><div class="section-top"><h2>Selected publications</h2><a href="publications/">All publications <span aria-hidden="true">↗</span></a></div><div>{cards}</div></section>
          <section class="section double-section" id="teaching"><div><h2>Teaching</h2>{teaching}</div><div><h2>Education</h2>{education}</div></section>
          <section class="contact-block" id="contact"><div><h2>Get in touch</h2><p>{e(p['contact_text'])}</p></div><a href="mailto:{e(p['email'])}">Send an email <span aria-hidden="true">↗</span></a></section>'''
        person = {'@context':'https://schema.org','@type':'Person','name':p['name'],'url':self.base,'jobTitle':p['role'],'affiliation':{'@type':'CollegeOrUniversity','name':p['university']},'sameAs':[self.scholar,p['github_url']]}
        meta = '<script type="application/ld+json">'+json.dumps(person,ensure_ascii=False).replace('<',r'\u003c')+'</script>'
        return self.page(body,'index.html', p['name']+' | Software Security & Machine Learning',metadata=meta)

    def publication_list(self) -> str:
        years = sorted({r['year'] for r in self.papers if r.get('year')}, reverse=True)
        types = sorted({r['type'] for r in self.papers})
        options = ''.join(f'<option value="{e(t)}">{e(t.title())}</option>' for t in types)
        year_options = ''.join(f'<option value="{year}">{year}</option>' for year in years)
        stamp = self.cache.get('last_successful_sync')
        note = f'Publication metadata last synchronized from Google Scholar: {e(stamp[:10])}. Links and selected details are curated separately.' if stamp else 'Publication details and full-text links are curated for this website.'
        body = f'''<section class="page-heading"><span class="eyebrow">Research output</span><h1>Publications</h1><p>Papers on binary analysis, program understanding, and software security.</p>
          <div class="inline-links">{self.link(self.scholar,'Google Scholar ↗','../')}<a href="../publications.bib" download>Download bibliography ↓</a></div></section>
          <form class="filter-panel" data-publication-filters hidden aria-label="Filter publications">
          <label class="filter-field search">Search publications<input type="search" name="q" placeholder="Search title, author, or venue…" aria-label="Search title, author, or venue"></label>
          <label class="filter-field">Type<select name="type"><option value="">All types</option>{options}</select></label>
          <label class="filter-field">Year<select name="year"><option value="">All years</option>{year_options}</select></label>
          <label class="checkbox-field"><input type="checkbox" name="pdf">With full-text PDF</label></form>
          <p class="results-note" id="result-count" role="status" aria-live="polite">{len(self.papers)} publications</p>
          <div class="publications-list">{''.join(self.card(r,'../') for r in self.papers)}</div>
          <p class="empty-state" id="empty-state" hidden>No publications match these filters. Try another search.</p><p class="sync-note">{note}</p>'''
        return self.page(body,'publications/index.html','Publications | '+self.profile['name'])

    def paper_page(self, r: dict) -> str:
        path = 'publications/'+r['id']+'/index.html'
        text = r.get('abstract') or r.get('summary') or ''
        heading = 'Abstract' if r.get('abstract') else 'Overview'
        body = f'''<article class="paper-page"><a class="back-link" href="../">← All publications</a>
          <span class="eyebrow">{e(r.get('type','Publication'))} · {e(r.get('year') or 'Undated')}</span>
          <h1>{e(r['title'])}</h1><p class="pub-authors">{self.authors(r)}</p><p class="pub-venue">{self.venue(r)}</p>
          {self.links(r,'../../')}{f'<h2>{heading}</h2><p class="abstract">{e(text)}</p>' if text else ''}
          {self.citation(r,'../../',True)}</article>'''
        tags = [('citation_title',r['title'])]
        tags += [('citation_author',a) for a in r['authors']]
        if r.get('year'):
            tags.append(('citation_publication_date',r.get('publication_date') or str(r['year'])))
        if r.get('doi'):
            tags.append(('citation_doi',r['doi']))
        if r.get('venue') and r['type'] in ('journal','conference'):
            tags.append(('citation_journal_title' if r['type']=='journal' else 'citation_conference_title',r['venue']))
        if r.get('preprint','').startswith('/'):
            self.url(r['preprint'])
            tags.append(('citation_pdf_url',self.base+r['preprint']))
        meta = '\n'.join(f'<meta name="{e(k)}" content="{e(v)}">' for k,v in tags)
        return self.page(body,path,r['title']+' | '+self.profile['short_name'],description=text or r['title'],metadata=meta)

    def write(self) -> Path:
        # Build in a staging directory so malformed content cannot erase good output.
        import tempfile
        out = self.root/'_site'
        with tempfile.TemporaryDirectory(prefix='academic-build-', dir=self.root) as tmp:
            stage = Path(tmp)
            shutil.copytree(self.root/'public',stage,dirs_exist_ok=True,
                            ignore=lambda _dir,names:[n for n in names if n.startswith('.') or n.endswith('.md')])
            (stage/'publications').mkdir(exist_ok=True)
            (stage/'citations').mkdir(exist_ok=True)
            (stage/'index.html').write_text(self.home(),encoding='utf-8')
            (stage/'publications/index.html').write_text(self.publication_list(),encoding='utf-8')
            for paper in self.papers:
                target = stage/'publications'/paper['id']
                target.mkdir(exist_ok=True)
                (target/'index.html').write_text(self.paper_page(paper),encoding='utf-8')
                (stage/'citations'/f'{paper["id"]}.bib').write_text(bibtex(paper),encoding='utf-8')
            (stage/'publications.bib').write_text('\n'.join(bibtex(p) for p in self.papers),encoding='utf-8')
            (stage/'.nojekyll').touch()
            urls = [self.base+'/',self.base+'/publications/'] + [self.base+'/publications/'+p['id']+'/' for p in self.papers]
            xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + ''.join('<url><loc>'+e(url)+'</loc></url>' for url in urls) + '</urlset>\n'
            (stage/'sitemap.xml').write_text(xml,encoding='utf-8')
            (stage/'robots.txt').write_text('User-agent: *\nAllow: /\nSitemap: '+self.base+'/sitemap.xml\n',encoding='utf-8')
            body = '<section class="page-heading"><h1>Page not found</h1><p>This page may have moved. <a href="'+e(self.base)+'/">Return to the homepage</a> or visit the <a href="'+e(self.base)+'/publications/">publication list</a>.</p></section>'
            # Absolute navigation and assets work at deeply nested unknown URLs.
            not_found = self.page(body,'404.html','Page not found | '+self.profile['short_name'])
            (stage/'404.html').write_text(not_found,encoding='utf-8')
            if out.exists():
                shutil.rmtree(out)
            shutil.copytree(stage,out)
        return out

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    args = parser.parse_args()
    site = Site(args.root.resolve())
    out = site.write()
    print(f'Built {len(site.papers)} publication pages and homepage in {out}.')

if __name__ == '__main__':
    main()
