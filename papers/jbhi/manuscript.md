# J-BHI manuscript pointer

**Canonical IEEE source:** [`main.tex`](main.tex) (IEEEtran journal class). Compile to [`main.pdf`](main.pdf) before portal upload.

This Markdown file is **not** a scientific manuscript and must not be treated as a second source of claims. Prior drafts here diverged from `main.tex` (for example, RQ3 wording). All research questions, metrics, related work, and numeric results live only in `main.tex`.

**Author:** Satya Venkata Ranga Janaki Sriram Mentey (corresponding)  
Address: 8601 Anderson Mill Rd, Apt 722, Austin, TX 78729, USA  
E-mail: srirammentey@ieee.org · ORCID: [0009-0007-2681-006X](https://orcid.org/0009-0007-2681-006X)

Compile from this directory:

```bash
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```
