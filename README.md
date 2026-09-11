# Mohammadhossein Amouei — Academic website

A text-first academic website for `mhamouei.github.io`. It includes a homepage, searchable publications, individual paper pages, downloadable BibTeX, manually managed preprint links, and an optional weekly Google Scholar sync through SerpApi.

**Important:** This package has not been pushed to your repository or deployed. The initial publication cache contains four curated records, not a successful Google Scholar import. The website works without an API key. Live Scholar synchronization requires a SerpApi account/key and a successful first run. No local paper PDFs or CV have been fabricated or bundled.

## 1. Preview locally

Requirements: Python 3.11 or newer. No `pip install`, Node.js, Jekyll, or database is needed.

Run in this folder:

```sh
python scripts/build.py
python -m http.server 8000 --directory _site
```

Open `http://localhost:8000`. On Windows, `py` can be used instead of `python`.

The `_site/` folder in this package already contains a built preview. Rebuild after editing content. Do not edit `_site/` directly: builds replace it.

## 2. Publish to the existing GitHub repository

1. Save a backup branch or download the current repository before replacing anything. The target is `mhamouei/mhamouei.github.io`, whose default branch was `master` when inspected.
2. Copy this package's contents into the repository root. Include the hidden `.github/` folder. Keep any existing `LICENSE` file. The workflow deploys **only `_site/`**, not the repository root. Old root-level `index.html`, `css/`, and `js/` files are no longer the published site.
3. To preserve old public URLs, copy the corresponding old files/folders into `public/` at the same relative paths before building. For example, an old `/img/example.png` becomes `public/img/example.png`. Old blog and modal content is not migrated or rewritten automatically. Move an existing `CNAME` into `public/CNAME` only when you use a custom domain, and update `site_url` accordingly.
4. In the repository, open **Settings → Pages → Build and deployment → Source → GitHub Actions**. Save the setting.
5. Commit the new files to the default branch. Under **Actions**, open **Build and deploy academic website** and verify the build and deployment complete. Repository/environment protection rules must permit deployment from the default branch.

The workflow supports either a `master` or `main` default branch, but never deploys from a non-default branch. Disable any older workflows that also deploy Pages to avoid competing deployments.

Example commands after copying the files into your existing local clone:

```sh
git add .
git commit -m "Redesign academic website"
git push
```

Keep secrets out of this commit. Review `git diff --cached` before committing. GitHub Actions' `contents: write` permission is used only to save refreshed publication metadata; deployment is performed explicitly in the same workflow rather than relying on a bot commit to trigger a second build.

## 3. Enable automatic Google Scholar updates

The preconfigured Scholar author ID is `1GTi1MMAAAAJ`, taken from the existing website's Scholar link. Change it in `data/profile.json` only if that is not the intended profile. Changing authors also requires reviewing/resetting the cache's `profile_id`; the synchronizer refuses to mix profiles accidentally.

Google Scholar does not provide a supported public publications API for this workflow. Its help pages state that bulk access is unavailable and that automated access must respect its robots policy. This implementation therefore does **not** scrape Scholar directly from GitHub Actions or visitors' browsers. It uses the independently operated **SerpApi Google Scholar Author API**. This is a third-party service, not an official Google API or an availability guarantee.

1. Obtain a SerpApi API key from your own account. Review its current terms, quotas, and pricing; using the provider may incur charges. No provider account has been created or billed by this package.
2. In GitHub, open **Settings → Secrets and variables → Actions → New repository secret**.
3. Name the secret exactly `SERPAPI_KEY` and paste the key into its value. Never put it in JSON, HTML, JavaScript, screenshots, or a committed `.env` file.
4. Open **Actions → Build and deploy academic website → Run workflow**, leave **Refresh publications** enabled, and run it on the default branch.
5. Inspect the sync step and `data/scholar_cache.json`. A non-null `last_successful_sync` confirms a completed import. A missing key is explicitly reported as “No sync performed.”

After setup, the workflow requests updates every Monday at 08:17 UTC. GitHub can delay scheduled jobs, and scheduled workflows in public repositories can be disabled after 60 days without repository activity. Check the Actions page if updates stop. This is a GitHub workflow, not a separately scheduled ChatGPT task.

### What is automatic

The script retrieves titles, authors, years, venues, Scholar links, and citation counts. Detailed records supply full author lists and abstracts when the provider returns them. Counts are saved but hidden on the site by default; enable `show_citation_counts` in the profile to show them. No citation metrics are invented in the seed cache.

Pagination supports more than 100 papers. By default a run uses 100 results per page, at most 10 pages, and at most 40 extra detail requests. New or changed papers and details older than 90 days are eligible for enrichment. Change those limits in `data/sync_config.json`. Quota use depends on the number of list/detail requests, not the number of site visitors. An exhausted detail-request allowance defers remaining detail enrichment to later runs.

The script never copies publication PDFs automatically and never assumes a publisher PDF is a preprint. DOI links are included when provided through the curated cache, manual records, or overrides; Scholar data does not reliably provide DOIs for every record.

### What happens on failure

A provider error, empty first page, unexpected author identifier, malformed record, or repeated/incomplete pagination prevents replacement of the cache. The previous valid publication data remains available. The workflow shows a warning and builds from that saved cache. A later content/build failure stops deployment rather than replacing the public site with broken output.

The synchronizer matches stable Scholar IDs, DOIs, or exact normalized titles. It deliberately does not make fuzzy guesses between similar titles. Missing remote records are retained, not automatically deleted. Scholar duplicates, renamed preprints versus published versions, and records removed from a profile may require curation. Use `hidden: true` in an override or reconcile IDs/titles explicitly. GitHub's branch protection may prevent the bot from committing cache updates; adjust the repository policy or adapt the workflow to a reviewed pull-request flow before enabling scheduled writes.

## 4. Add a downloadable preprint or accepted manuscript

### Easiest local method

List publication IDs:

```sh
python scripts/add_preprint.py --list
```

Attach your own PDF to LENA:

```sh
python scripts/add_preprint.py lena-2026 "/path/to/LENA-preprint.pdf"
```

Windows example:

```powershell
py scripts/add_preprint.py lena-2026 "C:\Users\YourName\Documents\LENA-preprint.pdf" --label "Accepted manuscript PDF"
```

This copies the file to `public/papers/lena-2026.pdf` and updates the corresponding manual override. It adds a full-text link and a separate **Download PDF** button. Rebuild to preview; then commit both the PDF and updated override file. Adding another PDF with the same publication ID replaces the linked local version deliberately.

### GitHub web-interface method

Upload the PDF under `public/papers/`, then edit the existing matching object in `data/publication_overrides.json`:

```json
{
  "id": "lena-2026",
  "preprint": "/papers/lena-2026.pdf",
  "preprint_label": "Accepted manuscript PDF"
}
```

The snippet above illustrates the fields to change; **do not replace the entire overrides file with it**, and keep the existing `match`, `code`, `summary`, and other fields. A path `/papers/lena-2026.pdf` maps to the repository file `public/papers/lena-2026.pdf`.

The builder checks that local files exist. A missing PDF is an error rather than a broken public button. Each locally hosted PDF also gets a `citation_pdf_url` on its paper's HTML page.

An externally hosted PDF can be linked by putting its HTTPS URL in `preprint`. For external URLs, the site provides a full-text link but does not claim it can force a browser download from another domain. The seed RAT record links to its existing author-posted arXiv PDF; the PDF is not copied into this package.

Post only a version you are entitled to share, and use an accurate label: “Preprint,” “Accepted manuscript,” or “Published version.” Follow the relevant publisher agreement and any required notices or embargo. A preprint and a final publisher PDF are not interchangeable labels.

## 5. Add work that is not yet on Scholar

Edit the `records` array in `data/manual_publications.json`. For example (replace **all** example values with real information):

```json
{
  "schema_version": 1,
  "records": [
    {
      "id": "my-new-preprint-2026",
      "title": "Your actual paper title",
      "authors": ["Mohammadhossein Amouei", "Actual coauthor name"],
      "year": 2026,
      "type": "preprint",
      "venue": "Preprint",
      "status": "Preprint",
      "summary": "Your description of this work.",
      "featured": true,
      "preprint": "/papers/my-new-preprint.pdf"
    }
  ]
}
```

Upload the referenced PDF first. Delete the `preprint` field when no PDF should be shown. Do not advertise work as accepted or published before that status is confirmed. Manual records take precedence over automatically retrieved data when they match the same record. Remove outdated manual metadata when the published record should take precedence instead.

## 6. Edit the profile, CV, and appearance

- **Biography, research themes, teaching, education, contact:** `data/profile.json`.
- **Curated publication information and links:** `data/publication_overrides.json`.
- **Publications not yet in Scholar:** `data/manual_publications.json`.
- **Design:** `public/assets/style.css`.
- **Shared HTML shell/navigation:** `templates/page.html` and `scripts/build.py`.

For a CV, put the real PDF at `public/cv.pdf` and set `"cv": "/cv.pdf"` in `data/profile.json`. The navigation and profile links then appear automatically. No CV link is shown until a valid file is configured.

A photo is optional and disabled by default. To restore an existing portrait, copy it into `public/assets/portrait.jpg` and set `"portrait": "/assets/portrait.jpg"`. No photo, logo, font download, tracker, or analytics service is needed by the default design.

Override fields include `title`, `authors`, `year`, `venue`, `venue_short`, `type`, `status`, `summary`, `abstract`, `doi`, `code`, `dataset`, `slides`, `project`, `preprint`, `preprint_label`, `featured`, `hidden`, and a custom `bibtex` string. Set `year`/`venue` manually when Scholar lists an early-access date instead of the final journal volume year. Stable local IDs determine individual publication URLs; retain them when editing titles.

## 7. Tests and scope

```sh
python -m unittest discover -s tests -v
python scripts/build.py
```

The package includes 25 offline unit tests for matching, pagination, escaping, safe links, cache preservation, local file validation, and generated page links. Desktop/mobile layouts and basic interactive behavior were also checked in Chromium; see `QA.md` for exact scope.

No live SerpApi call or authenticated GitHub deployment has been tested in this environment. Read `DATA_SOURCES.md` before publishing the seeded content. The initial four-paper bibliography is not asserted to be the complete Scholar profile. Your CV, local preprint PDFs, and any additional publications remain for you to supply or import.

## Architecture

```text
Google Scholar profile
    ↓ third-party SerpApi (scheduled GitHub Actions only)
data/scholar_cache.json
    + data/manual_publications.json
    + data/publication_overrides.json
    + data/profile.json and public/ assets
    ↓ python scripts/build.py
_site/  →  GitHub Pages
```

All publication content is built into static HTML. Search and copying are progressive enhancements; disabling JavaScript does not hide the bibliography. One stable page per paper provides scholarly metadata and a BibTeX download. Local PDFs are linked, not embedded in a heavyweight viewer. The site requires no runtime backend.

The Python/CSS/JavaScript/HTML in this package are newly written for this redesign. Existing linked projects and publication files remain subject to their own licenses; this package does not change your repository's existing license or grant redistribution rights over third-party papers.

## Official technical references

- GitHub Pages custom workflows: https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages
- GitHub scheduled workflow behavior: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule
- SerpApi author API: https://serpapi.com/google-scholar-author-api
- SerpApi citation detail API: https://serpapi.com/google-scholar-author-citation
- Google Scholar export/automated-access help: https://scholar.google.com/intl/en/scholar/help.html
- Google Scholar inclusion/metadata guidelines: https://scholar.google.com/intl/en/scholar/inclusion.html

Scholar indexing is controlled by Google. Providing metadata and crawlable pages supports discovery but does not guarantee inclusion or a particular update time.
