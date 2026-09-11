#!/usr/bin/env python3
"""Attach your own PDF to an existing publication; no HTML edits required."""
from __future__ import annotations
import argparse
from pathlib import Path
import shutil
try:
    from .common import ROOT, load_json, atomic_json, publications, override_matches
except ImportError:
    from common import ROOT, load_json, atomic_json, publications, override_matches

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paper_id', nargs='?')
    parser.add_argument('pdf', nargs='?', type=Path)
    parser.add_argument('--list', action='store_true', help='List publication IDs and titles')
    parser.add_argument('--label', default='Preprint PDF', help='For example: Accepted manuscript PDF')
    args = parser.parse_args()
    _, papers = publications()
    if args.list:
        for p in papers:
            print(f"{p['id']}\t{p['title']}")
        return
    if not args.paper_id or not args.pdf:
        parser.error('Supply a paper ID and PDF path, or use --list.')
    paper = next((p for p in papers if p['id'] == args.paper_id), None)
    if not paper:
        parser.error('Unknown paper ID. Run with --list to see valid IDs.')
    source = args.pdf.expanduser().resolve()
    if not source.is_file() or source.suffix.casefold() != '.pdf':
        parser.error('The source must be an existing .pdf file.')
    with source.open('rb') as stream:
        if not stream.read(1024).lstrip().startswith(b'%PDF-'):
            parser.error('The source does not have a PDF header.')
    path = ROOT/'data/publication_overrides.json'
    data = load_json(path)
    matches = [o for o in data['papers'] if override_matches(paper,o)]
    if len(matches) > 1:
        parser.error('Multiple overrides match this paper. Resolve the duplicates first.')
    if matches:
        entry = matches[0]
    else:
        entry = {'id':paper['id'],'match':{'titles':[paper['title']],
                 'scholar_ids':[paper['scholar_id']] if paper.get('scholar_id') else [],
                 'dois':[paper['doi']] if paper.get('doi') else []}}
        data['papers'].append(entry)
    destination = ROOT/'public/papers'/f"{paper['id']}.pdf"
    destination.parent.mkdir(parents=True,exist_ok=True)
    if source != destination.resolve():
        shutil.copy2(source,destination)
    entry['preprint'] = '/papers/'+destination.name
    entry['preprint_label'] = args.label
    atomic_json(path,data)
    print(f"Added {entry['preprint']} to {paper['title']}.")
    print('Run python scripts/build.py to preview; then commit the PDF and override file to publish.')

if __name__ == '__main__':
    main()
