# Google Docs → Markdown

Convert Google Docs documents and Office files to perfectly formatted Markdown with full structural fidelity.

---

## Features

- **Three conversion approaches** — Docs API (structural), Drive export (simple), .docx download (Office files)
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
| `doc_ids` | One or more Google Docs document IDs (positional) | **required** |
| `--creds` ** | Path to credentials JSON | **required** |
| `--auth` | Authentication type: `oauth` or `service_account` | `service_account` |
| `--method` | Conversion method: `api` or `export` | `api` |
| `--output`, `-o` | Output directory for `.md` files | `./output` |
| `--verbose`, `-v` | Enable DEBUG-level logging | off |

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

| Criterion | Approach 1 — Docs API (`--method api`) | Approach 2 — HTML Export (`--method export`) | Approach 3 — .docx Download (`--method docx`) |
|---|---|---|---|
| **Target files** | Native Google Docs only | Native Google Docs only | `.docx` Office files on Drive |
| **Accuracy** | Perfect structural fidelity | Depends on HTML conversion quality | Good text + images; custom Word styles → plain text |
| **Speed** | Moderate (API response) | Fast (single export) | Slower (download + convert) |
| **Dependencies** | `google-api-python-client` | `html2text` or `markdownify` | `mammoth` |
| **Inline styles** | Full support (bold, italic, code, links, underline, strikethrough) | Best-effort via HTML parser | Good for basic styles; custom styles may be stripped |
| **Tables** | Converted to Markdown pipe tables | Converted via HTML table → Markdown | Converted via mammoth |
| **Lists** | Proper nesting, mixed bullet/numbered | Good for flat lists | Good for standard Word lists |
| **Recommended for** | Native Google Docs (production) | Quick drafts, simple docs | Office `.docx` files uploaded to Drive |

## Output Format

Each document produces a `.md` file named after the document title (with special characters replaced by `_`).

### Example output

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

You can also use the converter directly in your Python scripts:

```python
from google_docs_to_markdown import GoogleDocsConverter

# Initialise
converter = GoogleDocsConverter(
    auth_type="service_account",
    creds_path="path/to/service-account-key.json"
)

# Authenticate
converter.authenticate()

# Fetch and convert
doc = converter_document("YOUR_DOC_ID")
markdown ="
md  converter.doc_to_markdown(doc)

# Save
converter.save_markdown(doc, md, Path("./output"))
```

## Project Structure

```
google-docs-to-markdown/
├── google_docs_to_markdown.py   # Main converter (930 lines)
├── requirements.txt             # Python dependencies
├── README.md                    # This file
└── .gitignore                   # Git ignore rules
```

## Authentication Troubleshooting

| Issue | Likely Cause | Fix |
|---|---|---|
| `404 Document not found` | Doc ID is wrong or not shared | Verify the ID and share the doc with your account |
| `403 Access denied` | Permissions missing | Share the doc with your service account email or OAuth user |
| `429 Quota exceeded` | API rate limit hit | Wait a few minutes and retry |
| `token.pickle` errors | Stale OAuth token | Delete `token.pickle` and re-authenticate |

## Development

```bash
# Clone and setup
cd google-docs-to-markdown
git clone ...
pip install -r requirements.txt

# Run tests
python - pytest tests/
```

## License

MIT
