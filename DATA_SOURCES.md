# Initial content and verification

Prepared on September 11, 2026.

This package starts with **four curated publications**, not a scraped or complete Google Scholar bibliography. The request to the linked Google Scholar profile was blocked with HTTP 429. Consequently, `last_successful_sync` is null, and the seed cache is explicitly labeled `curated_seed_not_a_scholar_sync`.

## Profile

The name, McGill affiliation, department, email, degrees, research areas, and Google Scholar identifier were taken from the existing public website and the user's prior context:

- Existing website: https://mhamouei.github.io/
- Repository: https://github.com/mhamouei/mhamouei.github.io
- Linked Scholar profile: https://scholar.google.com/citations?hl=en&user=1GTi1MMAAAAJ

The biography and research-theme descriptions are newly drafted text. The teaching entries reflect the user's reported McGill teaching; review their wording before publishing. The profile does not include a residential address, a relocation claim, or an unverified faculty/job-market status. No CV, current portrait, or official university logo has been added.

## Publication records

**LENA (2026).** Title, author order, venue, pages, and DOI were verified against the official project repository:

https://github.com/McGill-DMaS/LENA

DOI: `10.1109/TSE.2026.3705321`.

The old personal homepage described LENA as under review. The official repository now cites it in *IEEE Transactions on Software Engineering*, 2026, pp. 1–24. The seed reflects that record. Volume/issue details were not guessed. No local LENA PDF is included.

**FIN (2026).** Title, authors, journal, volume 231, article 112603, and DOI were verified against the official project repository:

https://github.com/McGill-DMaS/FIN

DOI: `10.1016/j.jss.2025.112603`.

The publication year is 2026 despite the 2025 component in the DOI. This follows the project's journal citation. No local FIN PDF is included.

**AsmDocGen (2024).** Title, author order, venue, pages, and DOI were verified against the publisher's record:

https://www.scitepress.org/PublishedPapers/2024/127614/

DOI: `10.5220/0012761400003753`.

The seed uses the publisher's displayed author name “Jesia Yuki”; some bibliographic records expand it to “Jesia Quader Yuki.” The full publisher title is retained, rather than the shortened title on the old personal homepage. No local paper PDF is included.

**RAT (2022).** Title, authors, journal volume/issue, journal year, DOI, and the author-posted PDF link were verified against the author's arXiv record:

https://arxiv.org/abs/2312.07885

Journal DOI: `10.1109/TDSC.2021.3095417`.

The journal reference is 2022, the DOI includes 2021, and the arXiv upload is 2023. These are different dates; the seed uses the journal reference year and does not create a second duplicate entry for the arXiv upload. Pages were not guessed. The PDF link goes to arXiv and is labeled “Author version PDF”; no PDF bytes are bundled.

## Deliberate omissions

Additional Scholar items, patents, service roles, news, the 2026 workshop paper, and any unpublished/ongoing work were not promoted into the initial bibliography without a complete publication record in this implementation. They can be added through the first successful Scholar import or `data/manual_publications.json`. The old website's patent and blog pages are not silently converted into journal publications.

The short descriptions on the publication cards are newly written summaries, not quoted abstracts. Citation counts are unset in the seed. Buttons appear only for configured resources; absent PDFs and a missing CV do not produce dummy links.
