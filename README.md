# Google Docs → Markdown

Convert Google Docs, Google Keep notes, and Office files to perfectly formatted **Markdown** or **PDF**.

---

## Features

- **Four input methods** — Docs API (structural), Drive export (simple), .docx (Office), Google Keep
- **Two output formats** — Markdown (`--format md`, default) or **PDF** (`--format pdf`)
- **Headings** h1–h6, TITLE, SUBTITLE → properly nested `# … ` / ## / ###` etc.
- **Inline styling** — bold, italic, strikethrough, underline, inline code, links
- **Lists** — bullet and numbered lists (with nesting) → indented Markdown lists
- **Tables** → Markdown pipe tables
- **Images & footnotes** → reference-style Markdown references
- **YAML front matter** — title, revision, source, generation timestamp
- **Batch conversion** — pass multiple document IDs at once
- **OAuth 2.0** and **Service Account** authentication
- **UTF-8 output** with proper emoji / special character handling

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Get credentials

**Option A — Service Account (recommended for automation)**

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project → Enable the Docs API and Drive API
3. Create a Service Account → download the JSON key
4. Share your Google Doc with the service account email

**Option B — OAuth 2.0 (interactive desktop use)**

1. In the Cloud Console, create an OAuth 2.0 Client ID (Desktop app)
2. Download the `client_secret.json`
3. First run will open a browser for authentication; token is cached locally

### 3. Convert a document

Find the document ID in the URL:  `https://docs.google.com/document/d/**DOC_ID_HERE**/edit`

```bash
# Approach 1 — Docs API (full structural parsing, native Google Docs)
python google_docs_to_markdown.py \
    --creds service-account-key.json \
    --auth service_account \
    YOUR_DOC_ID

# Approach 2 — HTML export (simpler fallback, native Google Docs)
python google_docs_to_markdown.py \
    --method export \
    --creds service-account-key.json \
    YOUR_DOC_ID

# Approach 3 — .docx download (Office files uploaded to Drive)
python google_docs_to_markdown.py \
    --method docx \
    --creds service-account-key.json \
    FILE_ID

# Approach 4 — Google Keep note (via Drive export)
python google_docs_to_markdown.py \
    --method keep \
    --creds service-account-key.json \
    NOTE_ID

# Output as PDF (any method)
python google_docs_to_markdown.py \
    --format pdf \
    --creds service-account-key.json \
    YOUR_DOC_ID

# OAuth 2.0 (interactive)
python google_docs_to_markdown.py \
    --creds client_secret.json \
    --auth oauth \
    YOUR_DOC_ID
```

## Usage Guide

### Command-line arguments

| Argument | Description | Default |
|---|---|---|
| `doc_ids` | One or more document/file IDs (positional) | **required** |
| `--creds` | Path to credentials JSON | **required** |
| `--auth` | Auth type: `oauth` or `service_account` | `service_account` |
| `--method` | Input type: `api`, `export`, `docx`, `keep` | `api` |
| `--format` | Output format: `md` or `pdf` | `md` |
| `--output`, `-o` | Output directory | `./output` |
| `--verbose`, `-v` | Enable DEBUG logging | off |

### Examples

**Convert multiple documents at once:**

```bash
python google_docs_to_markdown.py \
    --creds keys/sa-key.json \
    DOC_ID_1 DOC_ID_2 DOC_ID_3
```

**Custom output directory:**

```bash
python google_docs_to_markdown.py \
    --creds keys/sa-key.json \
    --docs/my-markdown \
    DOC_ID
```

**Verbose logging for troubleshooting:**

```bash
python google_docs_to_markdown.py \
    --creds keys/sa-key.json \
    --verbose \
    DOC_ID
```

**Converting a .docx file (Office documents on Drive):**

```bash
python google_docs_to_markdown.py \
    --method docx \
    --creds keys/sa-key.json \
    FILE_ID
```

**Converting a Google Keep note:**

```bash
python google_docs_to_markdown.py \
    --method keep \
    --creds keys/sa-key.json \
    NOTE_ID
```

**Output as PDF (any input method):**

```bash
python google_docs_to_markdown.py \
    --format pdf \
    --creds keys/sa-key.json \
    DOC_ID

python google_docs_to_markdown.py \
    --method docx --format pdf \
    --creds keys/sa-key.json \
    FILE_ID

python google_docs_to_markdown.py \
    --method keep --format pdf \
    --creds keys/sa-key.json \
    NOTE_ID
```

**Using the export method (HTML → Markdown):**

```bash
python google_docs_to_markdown.py \
    --method export \
    --creds keys/sa-key.json \
    DOC_ID
```

**Using OAuth 2.0 (opens browser for login):

```bash
python google_docs_to_markdown.py \
    --auth oauth \
    --creds client_secret.json \
    DOC_ID
```

## Approach Comparison

| Criterion | Docs API (`api`) | HTML Export (`export`) | .docx Download (`docx`) | Google Keep (`keep`) |
|---|---|---|---|---|
| **Target files** | Native Google Docs | Native Google Docs | `.docx` Office files | Google Keep notes |
| **Accuracy** | Perfect structural fidelity | Depends on HTML quality | Good text + images | Preserves note structure |
| **Speed** | Moderate | Fast | Slower | Fast |
| **Dependencies** | `google-api-python-client` | `html2text` / `markdownify` | `mammoth` | `html2text` / `markdownify` |
| **Inline styles** | Full support | Best-effort | Basic | Basic |
| **Tables** | Yes | Yes | Via mammoth | No (Keep has no tables) |
| **Lists** | Full nesting | Good flat lists | Standard Word lists | Checklists supported |
| **Output formats** | Markdown / PDF | Markdown / PDF | Markdown / PDF | Markdown / PDF |
| **Recommended for** | Production Docs | Quick drafts | Office files on Drive | Keep notes |

## Output Format

Each document produces a file named after the document title (special characters replaced by `_`).

- **Markdown** (`--format md`, default): `.md` file with YAML front matter
- **PDF** (`--format pdf`): `.pdf` file + intermediate `.md` saved alongside

### Markdown example output

```markdown
---
title: "Performance Review — Q1 2025"
revision: a1b2c3d4e5
source: google-docs-api
generated: 2025-06-18T14:30:00Z
---

# Performance Review

## Summary section with **bold** metrics and *italic* notes.

## Key Metrics

| Metric | Value | Status |
|---|---|---|
| Latency p50 | 2.3 ms | ✅ |
| Throughput | RPM | ✅ throughput

## Action Items

- Migrate remaining RDS instances
- Update monitoring dashboard
- Schedule load testing for next sprint
```

## Python API

Use the converter directly in your Python scripts:

```python
from pathlib import Path
from google_docs_to_markdown import GoogleDocsConverter

# Create converter with service account
converter = GoogleDocsConverter(
    auth_type="service_account",
    creds_path="path/to/service-account-key.json"
)
converter.authenticate()

# --- Google Docs (API method) ---
doc = converter.get_document("YOUR_DOC_ID")
md = converter.doc_to_markdown(doc)
converter.save_markdown(doc, md, Path("./output"))

# --- Google Docs (export method) ---
md = converter.export_as_html("YOUR_DOC_ID")

# --- .docx files ---
md, meta = converter.docx_to_markdown("FILE_ID")

# --- Google Keep notes ---
md, meta = converter.keep_to_markdown("NOTE_ID")

# --- PDF conversion ---
from google_docs_to_markdown import GoogleDocsConverter as GDC
GDC.md_to_pdf(md, Path("./output/my_doc.pdf"))
```

## PDF Output

PDF output uses **weasyprint** (Markdown → HTML → PDF).

| Platform | Status |
|---|---|
| **Linux / macOS** | ✅ Works out of the box |
| **Windows** | Requires [GTK3 runtime](https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases) |

If GTK is missing on Windows, the tool:
1. ✅ Saves the **Markdown** file as a fallback
2. ✅ Logs a clear warning with install instructions
3. ✅ Counts the conversion as successful (Markdown is always usable)

## Project Structure

```
google-docs-to-markdown/
├── google_docs_to_markdown.py   # Main converter (1,240+ lines)
├── requirements.txt             # Python dependencies (8 packages)
├── README.md                    # This file
├── .gitignore                   # Git ignore rules (blocks *.json, output/)
├── .github/
│   └── PULL_REQUEST_TEMPLATE/   # PR template for contributors
├── sample-credentials/          # JSON template files (dummy data)
└── tests/
    └── test_converter.py        # 15 unit tests
```

## Authentication Troubleshooting

| Issue | Likely Cause | Fix |
|---|---|---|
| `404 Document not found` | Doc ID is wrong or not shared | Verify the ID and share the doc with your account |
| `403 Access denied` | Permissions missing | Share the doc with your service account email or OAuth user |
| `429 Quota exceeded` | API rate limit hit | Wait a few minutes and retry |
| `token.pickle` errors | Stale OAuth token | Delete `token.pickle` and re-authenticate |
| `This operation is not supported` | File is an Office doc, not a native Doc | Use `--method docx` instead |
| `fileNotExportable` | File format can't be exported to HTML | Use `--method docx` for .docx files |

## Development

```bash
# Clone and setup
cd google-docs-to-markdown
git clone ...
pip install -r requirements.txt

# Run all tests (no API keys needed — uses mock data)
python -m unittest tests.test_converter -v
```

## License

MIT
