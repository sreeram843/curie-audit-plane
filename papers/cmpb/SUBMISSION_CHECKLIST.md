# CMPB submission checklist

**Current verdict:** Elsevier original-research package is assembled in
`papers/cmpb/`. Remaining work is author and Editorial Manager actions in
`submission/AUTHOR_TODO.md`. Recheck the live CMPB Guide for Authors
immediately before upload.

Portal: https://www.editorialmanager.com/cmpb/
Journal: https://www.sciencedirect.com/journal/computer-methods-and-programs-in-biomedicine

## Package

Regenerate the upload directory with `papers/cmpb/assemble_submission.sh`.

| File | Purpose |
|------|---------|
| `main.tex` | Elsevier preprint 12pt `elsarticle` manuscript |
| `main.pdf` | Compiled preview |
| `highlights.txt` | Required Highlights file |
| `cover_letter.txt` / `cover_letter.tex` | Cover letter (fit, known work, contribution, unpublished) |
| `submission/` | Numbered PDFs, LaTeX zip, graphical abstract, portal paste files |
| `SUBMISSION_CHECKLIST.md` | This file |

```bash
cd papers/cmpb
./assemble_submission.sh
```

## Recorded in the repository

- [x] Article type: Original Research Manuscript
- [x] Structured abstract headings: Background and Objectives; Methods; Results; Conclusions
- [x] Numbered sections: Introduction, Methods, Results, Discussion, Acknowledgements
- [x] Keywords: 6
- [x] Highlights: 5 bullets
- [x] Numbered Vancouver citations (`elsarticle-num`)
- [x] Generative-AI disclosure before references
- [x] CRediT, funding, competing interests, data availability, ethics
- [x] Subscription route chosen (no author fee); OA APC noted for later choice
- [x] Synthetic-data ethics note
- [x] Evaluation freeze tag `jbhi-eval-20260828`; Gate C remains in `papers/jbhi/GATE_C_ATTESTATION.md`
- [x] J-BHI IEEE package retained under `papers/jbhi/` and is not a competing submission

## Author / portal (see `submission/AUTHOR_TODO.md`)

- [ ] Commit the current `papers/cmpb/` package
- [ ] Upload files listed in `submission/README.md`
- [ ] Suggest independent reviewers after verifying emails
- [ ] Optional public DOI (do not invent one here)
- [ ] Recheck live CMPB Guide for Authors and current APC
