# Validation report

Prepared September 11, 2026.

## Automated offline tests

Command: `python -m unittest discover -s tests -v`

Result: **25 tests passed** using Python 3.13. Tests cover normalized matching, stable IDs, distinct DOIs, preservation of complete author lists, separate manual overrides, safe local/remote URLs, BibTeX escaping, pagination boundaries, detail validation, preprint classification, missing-key behavior, failure preserving saved data, generated internal links and unique HTML IDs, HTML escaping, optional CV links, local PDF links/metadata, and preservation of a good build after malformed input.

PDF-related unit tests use explicitly labeled temporary header fixtures. These are not research papers and are not included in the delivered website.

The `add_preprint.py` command was also checked in an isolated temporary copy: attaching a header fixture created the expected local file and override; a subsequent build generated the download link. The fixture and temporary copy were removed. This checks file/link handling, not the rendering of a real manuscript.

## Browser checks

Generated HTML was rendered in Chromium at desktop width 1440 px and mobile/tablet widths 320, 375, 390, and 768 px. No horizontal overflow was found in the tested homepage/publication layouts.

Checked behaviors: publication text search, year/type filters, full-text availability filter, empty-state feedback, individual paper page content, scholarly metadata, BibTeX copy feedback, and the existence/attributes of downloadable BibTeX links. No uncaught JavaScript errors occurred in these checks. Publication content and native BibTeX disclosure remained readable with JavaScript disabled.

The browser loaded generated HTML with its local stylesheet and script inlined for this test, rather than accessing a live HTTP server. Consequently, these checks do not assert that hosted routes, external links, actual HTTP downloads, or production GitHub Pages deployment have been exercised. The delivered website uses normal external local CSS and a deferred local script.

The screenshot previews show the locally rendered implementation, not image-generation mockups. Desktop homepage, publications, and mobile homepage screenshots were visually reviewed.

## Build and archive checks

`python scripts/build.py` generated a homepage, publication index, four individual paper pages, a 404 page, CSS/JavaScript, individual and combined BibTeX files, a sitemap, and robots.txt. The ZIP was extracted into a fresh temporary directory, where the offline tests and static build were run again.

## Not tested or not supplied

No authenticated SerpApi request or actual Scholar import was run. The linked Scholar page returned HTTP 429 during research. The initial cache therefore contains four independently verified curated records and has no successful-sync timestamp.

No repository write or GitHub Actions deployment was executed. API quota availability, third-party uptime, repository secrets, branch protection, and Pages environment permissions require verification in the user's accounts. Existing blog/modal pages were not migrated.

No actual local preprint PDFs, CV, or portrait were supplied. The optional resource controls were tested using temporary fixtures; no nonexistent resource is presented as a working public download.

These checks are not a comprehensive accessibility certification, security audit, cross-browser certification, or guarantee of search-engine indexing. Review the biography, teaching entries, and publication metadata before publishing.
