#!/usr/bin/env bash
# Assemble papers/cmpb/submission/ for Elsevier Editorial Manager (CMPB).
set -euo pipefail

CMPB="$(cd "$(dirname "$0")" && pwd)"
SUB="$CMPB/submission"
ROOT="$(cd "$CMPB/../.." && pwd)"

need() {
  if [[ ! -f "$1" ]]; then
    echo "missing required file: $1" >&2
    exit 1
  fi
}

cd "$CMPB"
pdflatex -interaction=nonstopmode main.tex >/dev/null
bibtex main >/dev/null
pdflatex -interaction=nonstopmode main.tex >/dev/null
pdflatex -interaction=nonstopmode main.tex >/dev/null
pdflatex -interaction=nonstopmode cover_letter.tex >/dev/null
pdflatex -interaction=nonstopmode gagraphic.tex >/dev/null

need "$CMPB/main.pdf"
need "$CMPB/main.tex"
need "$CMPB/references.bib"
need "$CMPB/cover_letter.pdf"
need "$CMPB/cover_letter.txt"
need "$CMPB/highlights.txt"
need "$CMPB/gagraphic.pdf"
need "$CMPB/figures/console-overview.png"

rm -rf "$SUB/figures" "$SUB/source" "$SUB/portal_metadata"
mkdir -p "$SUB/figures" "$SUB/source/figures" "$SUB/portal_metadata"

cp "$CMPB/cover_letter.pdf" "$SUB/01_cover_letter.pdf"
cp "$CMPB/main.pdf" "$SUB/02_manuscript.pdf"
cp "$CMPB/gagraphic.pdf" "$SUB/gagraphic.pdf"
cp "$CMPB/highlights.txt" "$SUB/highlights.txt"
if command -v sips >/dev/null 2>&1; then
  sips -s format png "$CMPB/gagraphic.pdf" --out "$SUB/gagraphic.png" >/dev/null
  sips --resampleHeightWidth 590 1320 "$SUB/gagraphic.png" >/dev/null
else
  echo "sips not found; leaving gagraphic.pdf only" >&2
fi
cp "$CMPB/figures/console-overview.png" "$SUB/figures/Figure2_console_overview.png"

cp "$CMPB/main.tex" "$SUB/source/main.tex"
cp "$CMPB/references.bib" "$SUB/source/references.bib"
cp "$CMPB/main.bbl" "$SUB/source/main.bbl"
cp "$CMPB/highlights.txt" "$SUB/source/highlights.txt"
cp "$CMPB/figures/console-overview.png" "$SUB/source/figures/"
(
  cd "$SUB/source"
  zip -qr ../03_latex_source.zip main.tex main.bbl references.bib highlights.txt figures
)
rm -rf "$SUB/source"

cp "$CMPB/cover_letter.txt" "$SUB/cover_letter.txt"
need "$SUB/conflict_of_interest.txt"
need "$SUB/graphical_abstract_text.txt"
need "$SUB/graphical_abstract_text_50w.txt"

python3 - "$CMPB/main.tex" "$CMPB/highlights.txt" "$SUB/portal_metadata" <<'PY'
import re
import sys
from pathlib import Path

tex = Path(sys.argv[1]).read_text()
highlights = Path(sys.argv[2]).read_text()
out = Path(sys.argv[3])


def plain(s: str) -> str:
    s = s.replace("\\\\", " ").replace("~", " ").replace("--", "–")
    s = s.replace("\\%", "%").replace("\\,", " ")
    s = re.sub(r"\\url\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\texttt\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\cite\{[^}]*\}", "", s)
    s = re.sub(r"\\noindent", "", s)
    s = re.sub(r"\\[A-Za-z]+\*?(?:\[[^]]*\])?\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\[A-Za-z]+", "", s)
    s = s.replace("{", "").replace("}", "").replace("$", "")
    return re.sub(r"\s+", " ", s).strip()


title = re.search(r"\\title\{(.*?)\}", tex, re.DOTALL).group(1)
abstract = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", tex, re.DOTALL).group(1)
keywords = re.search(r"\\begin\{keyword\}(.*?)\\end\{keyword\}", tex, re.DOTALL).group(1)
abstract_text = plain(abstract)
body = re.search(
    r"\\end\{frontmatter\}(.*?)\\bibliographystyle", tex, re.DOTALL
).group(1)
body_text = plain(re.sub(r"\\begin\{(?:figure|table|align)\*?\}.*?\\end\{(?:figure|table|align)\*?\}", " ", body, flags=re.DOTALL))
(out / "title.txt").write_text(plain(title) + "\n")
(out / "abstract.txt").write_text(abstract_text + "\n")
(out / "keywords.txt").write_text(
    "\n".join(
        k for k in (plain(part) for part in re.split(r"\\sep", keywords)) if k
    )
    + "\n"
)
(out / "article_type.txt").write_text("Original Research Manuscript\n")
(out / "access_type.txt").write_text(
    "Subscription (no author publication fee). Open access APC is approximately USD 3180 excluding taxes if selected later.\n"
)
(out / "word_count.txt").write_text(
    f"Abstract: {len(abstract_text.split())} words\n"
    f"Main text excluding abstract (approx., captions/equations stripped): {len(body_text.split())} words\n"
    "CMPB original research: structured abstract ≤350 words; main text normally ≤3500 excluding abstract.\n"
)
(out / "data_code_availability.txt").write_text(
    "Source, synthetic fixtures, and versioned evaluation artifacts are available at "
    "https://github.com/sreeram843/curie-audit-plane under tag jbhi-eval-20260828. "
    "No DOI has been assigned.\n"
)
(out / "highlights.txt").write_text(highlights)
PY

echo "Assembled $SUB"
find "$SUB" -type f | sort
