# CV Skill Extraction App

A complete Python and Streamlit app that extracts text with **pypdf**, locates CV sections, and displays explicit skill evidence with page numbers. No external AI service, API key, Java, custom JavaScript, HTML, or CSS is used in application code. Streamlit supplies its own browser interface.

## Run

Python 3.10 or newer is required (tested on Python 3.12).

```sh
python -m venv .venv
source .venv/bin/activate
# Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
streamlit run app.py
```

Upload a PDF, optionally enter its password, then click **Analyze CV**. Review skills by category and source section; expand each skill for its original supporting text. The evidence table and CSV include every distinct supporting occurrence. The unique count deduplicates canonical names across sections and pages. Use the expandable extracted-text viewer to audit results. Clear analysis removes the current results; changing the uploaded file invalidates previous results.

## How detection works

1. pypdf extracts every page in layout mode, preserving spacing where possible.
2. Whole-label heading recognition identifies Skills, Technical Skills, Core Competencies, Technical Expertise, and other variants. Recognized subsequent headings close the section. Unrecognized short uppercase headings also close a skills block.
3. Whitespace column anchors track separate section state in common two-column layouts. Label/value skills tables inherit the Skills section across their row.
4. An auditable vocabulary matches complete aliases, normalizes names, avoids overlapping matches (Java versus JavaScript, C versus C++), and attaches evidence. Short ambiguous language names use additional context checks. Local negation and learning cues suppress unsupported capability claims.
5. In skills sections only, short structured list entries outside the vocabulary are retained as **Other listed skills — review**. Prose is not promoted to an unknown skill. These are explicit text entries, not inferred capabilities.

All results are **explicit mentions**. The app does not infer Python from pandas, claim proficiency, rank candidates, or invent missing skills. A mention under Education or Projects remains attributed to that section, rather than being presented as a listed skill.

## Limits and privacy

- Text-based PDFs only; no OCR. Blank/image-only pages produce a clear warning. Upload a searchable export for scanned CVs.
- Maximum 20 MB / 50 pages. Encrypted PDFs require the correct password; damaged PDFs produce a readable error.
- PDF reading order is inherently ambiguous. Irregular tables, merged cells, floating boxes, unusual headings, rotated text, page headers/footers, and mixed column widths can affect boundaries. Page breaks preserve section state where possible. Check the snippets and raw text. This is conservative rule-based NLP, not a guarantee of exhaustive extraction across every layout.
- The built-in vocabulary is primarily English. Unknown short list entries require human review; unknown skills in prose can be missed. Unknown uppercase list entries can look like section headings. Extend `CATALOG`, `SKILL_HEADINGS`, and `SECTION_HEADINGS` in `extractor.py` for your domain.
- Negation handling uses local textual cues and cannot fully interpret every sentence. Explicit mentions are evidence of text, not proof of skill.
- The app does not write uploaded PDFs to disk or call external analysis APIs. Uploaded bytes and results live in the Streamlit session; deploy only on infrastructure you trust. CSV fields are protected against spreadsheet formula injection.
- No actual user CV was supplied for validation. Tests use synthetic PDFs; please verify results on your CV.

## Tests and sample PDFs

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
python tests/generate_samples.py
```

Tests generate real PDFs covering bullet/list skills, separate sections, two columns, label/value tables, multiple pages, aliases, unsupported terms, negation, ambiguous words, encrypted documents, blank pages, corrupt uploads, and size/page limits. Streamlit AppTest covers initial UI, result rendering, filters, clearing, and empty results. Test dependencies are not required to run the app. Generated examples are in `samples/` and contain no personal data.

`requirements-lock.txt` records the exact working environment, including test packages; use `python -m pip install -r requirements-lock.txt` to reproduce those versions on compatible Python/platforms.

## Files

- `app.py`: native Streamlit UI and safe CSV export.
- `extractor.py`: PDF handling, section parsing, and evidence extraction.
- `tests/`: extraction and UI tests plus synthetic sample generator.
- `samples/`: generated PDFs for manual upload checks.
- `testing.ipynb`, `models_ev.docx`: original repository files, preserved unchanged.
