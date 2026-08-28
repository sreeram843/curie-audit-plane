# IEEE J-BHI submission checklist

Packaging follows the companion Curie FHIR J-BHI folder in
`../curie-fhir/paper/jbhi/`. Source:
https://www.embs.org/jbhi/prepare-and-submit-your-manuscript/

## Package in this folder

| File | Purpose |
|------|---------|
| `main.tex` | IEEE double-column journal manuscript |
| `main.pdf` | Upload candidate (after compile) |
| `cover_letter.txt` | Paste into Author Portal cover-letter box |
| `SUBMISSION_CHECKLIST.md` | This file |

Compile from `papers/jbhi/`:

```bash
cd papers/jbhi
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

## Portal

Submit via **IEEE Author Portal** (linked from the J-BHI prepare page).
ScholarOne URL referenced by J-BHI: https://mc.manuscriptcentral.com/jbhi-embs

## Before you click Submit

### You must provide (human / account)

- [x] **ORCID** for every author: 0009-0007-2681-006X
- [x] **IEEE e-mail**: srirammentey@ieee.org
- [x] Full **mailing address** in `\thanks` and cover letter
- [ ] **Gate C:** a second person who did not implement the verifier runs
      `docs/evaluation/independent-exercise.md` and signs
      `papers/jbhi/GATE_C_ATTESTATION.md`
- [ ] Choose **Regular Paper**
- [ ] Choose **Traditional** vs **Open Access**
- [ ] Suggest **4 independent reviewers** in the portal (`suggested_reviewers.md` is a draft; verify emails)
- [ ] Run **IEEE PDF Checker**
- [ ] Assign a public **DOI** (not invented in this repository)
- [x] Clean-clone release proof: annotated tag `jbhi-eval-20260828`
      (commit `27d8b6a`) regenerates headline ARC 20/20, tamper 19/19,
      allocated 81885/11373 bytes, and logical 39454/11373 bytes from a
      clean clone. Regenerated experiment metadata records the tag commit
      (`27d8b6a`, `git_dirty: false`); frozen campaign files record source
      `0dcf801`.
- [ ] Author Consent Form: **not required** for single-author papers unless the portal marks it required

### Manuscript rules addressed in `main.tex`

- [x] IEEE single-spaced **double-column** format
- [x] Abstract in J-BHI style (objective/methods/results/significance; no citations)
- [x] IEEE numeric bibliography (`IEEEtran`)
- [x] Synthetic-data ethics note (no IRB)
- [x] Cover letter draft and conflict-of-interest statement

### Still tighten if needed after compile

- [x] **Page count ≤ 14** (hard limit including supplementary) — current `main.pdf` is **4 pages**
- [x] Prefer **≤ 8 pages** to avoid mandatory overlength charges — current `main.pdf` is **4 pages**
- [x] Confirm abstract word count ≤ 250 in the portal field — IEEE abstract in `main.tex` is **about 221 words**

## Honest scope note

This manuscript is a **protocol and system demonstration on synthetic data**.
In-repo work cannot close IEEE PDF Checker, DOI minting, portal article/access
selection, reviewer invitation, or Gate C (a second human must exercise the
verifier). Those remain open on this checklist.
