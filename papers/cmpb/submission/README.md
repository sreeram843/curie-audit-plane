# CMPB upload package

Regenerate with:

```bash
cd papers/cmpb
./assemble_submission.sh
```

Submit via Elsevier Editorial Manager: https://www.editorialmanager.com/cmpb/

| File | Portal use |
|---|---|
| `01_cover_letter.pdf` | Cover letter (also paste `cover_letter.txt` if the form uses a text box) |
| `02_manuscript.pdf` | Main manuscript, Elsevier preprint template |
| `03_latex_source.zip` | `main.tex` + `references.bib` + `highlights.txt` + `figures/` |
| `highlights.txt` | Required Highlights (3–5 bullets, ≤85 characters each) |
| `gagraphic.pdf` or `gagraphic.png` | Graphical abstract (PNG is 1320×590) |
| `graphical_abstract_text.txt` | Graphical-abstract caption |
| `graphical_abstract_text_50w.txt` | Short caption if the portal has a 50-word limit |
| `conflict_of_interest.txt` | Check the portal “no conflict” box, or sign and upload |
| `figures/Figure2_console_overview.png` | Console figure as a separate file (figures must also be uploaded separately) |
| `portal_metadata/*.txt` | Title, abstract, keywords, article type, access, data/code availability |

Fig. 1 is drawn in TikZ inside `main.tex`. Fig. 2 is the console screenshot, captured from a fresh verified evaluation store.

The package contains no patient-level data. Remaining author actions: `AUTHOR_TODO.md`.
