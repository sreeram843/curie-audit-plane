# Author actions before CMPB submit

Package path: `papers/cmpb/submission/`.
Portal: https://www.editorialmanager.com/cmpb/

## Already recorded in the repository

- [x] Ethics: synthetic fixtures only; no IRB; no identifiable clinical records.
- [x] AI tools: coding agents drafted software and documentation; metrics come from the versioned harness (manuscript AI declaration).
- [x] Companion manuscript disclosed: related Curie FHIR translation paper (different question and evaluation).
- [x] Publication route: subscription (no author fee).
- [x] Gate C signed by Chanukya Lakamsani on tag `jbhi-eval-20260828` (`papers/jbhi/GATE_C_ATTESTATION.md`).
- [x] ORCID and corresponding-author email in front matter and cover letter.
- [x] Highlights, graphical abstract, structured abstract, CRediT, data availability.

## Before upload

- [ ] Commit the current `papers/cmpb/` package (manuscript, figures, `submission/`).
- [ ] Re-run `./assemble_submission.sh` immediately before upload.
- [ ] Recheck the live CMPB Guide for Authors, article type, and APC.
- [ ] Optional: mint a public DOI; do not invent one in the repository. The manuscript currently cites the GitHub tag.
- [ ] Confirm this paper is not also under review at IEEE J-BHI or another journal.

## In Editorial Manager

- [ ] Article type: Original Research Manuscript. Paste title, abstract, keywords from `portal_metadata/`.
- [ ] Access: subscription unless you later choose open access (APC ~USD 3180 excluding taxes).
- [ ] Upload `02_manuscript.pdf` and `01_cover_letter.pdf`. Upload `03_latex_source.zip` if source is requested.
- [ ] Upload `highlights.txt` as the Highlights file.
- [ ] Upload `gagraphic.png` (or `gagraphic.pdf`) and paste `graphical_abstract_text.txt`.
- [ ] Suggest independent reviewers from `../suggested_reviewers.md` after verifying current emails.
- [ ] Conflict of interest: check “none,” or sign `conflict_of_interest.txt`.
- [ ] Complete Elsevier declarations (ethics, funding, data availability, generative AI).

## After acceptance (later)

- Publishing agreement
- Proofs
- Final files per production instructions
