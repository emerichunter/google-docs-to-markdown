#!/usr/bin/env python3
"""
google_docs_to_markdown.py — Convert Google Docs, .docx, and Google Keep notes
to perfectly formatted Markdown or PDF.

Supported inputs:
  1. Google Docs API (--method api)  — Native Google Docs, full structural parsing
  2. HTML export   (--method export) — Native Google Docs, Drive → HTML → Markdown
  3. .docx download (--method docx)  — Office files on Drive, via mammoth
  4. Google Keep    (--method keep)  — Keep notes via Drive export

Output formats:
  --format md   (default) — Markdown
  --format pdf            — PDF (via weasyprint)

Usage:
    # Docs API parsing (default)
    python google_docs_to_markdown.py --creds client_secret.json DOC_ID

    # Quick HTML export
    python google_docs_to_markdown.py --method export --creds service_account.json DOC_ID

    # .docx file
    python google_docs_to_markdown.py --method docx --creds service_account.json FILE_ID

    # Google Keep note
    python google_docs_to_markdown.py --method keep --creds service_account.json NOTE_ID

    # Output as PDF
    python google_docs_to_markdown.py --format pdf --creds service_account.json DOC_ID

    # Custom output directory
    python google_docs_to_markdown.py --creds client_secret.json --output ./docs DOC_ID
"""

__version__ = "1.0.0"

import argparse
import json
import logging
import os
import pickle
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
KEEP_NOTE_MIME = "application/vnd.google-apps.note"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("google_docs_to_markdown")

# ===================================================================
# MarkdownConverter
# ===================================================================


class MarkdownConverter:
    """Convert Google Docs structural elements into Markdown-formatted strings.

    Handles paragraphs, headings, inline styling (bold, italic, underline,
    strikethrough, links, inline code), bullet/numbered lists, tables,
    images, horizontal rules, and section breaks.
    """

    # Glyph-type constants from the Google Docs API.
    _ORDERED_GLYPHS = frozenset({
        "DECIMAL",
        "ALPHA",
        "ALPHA_UPPER",
        "ROMAN",
        "ROMAN_UPPER",
    })

    def __init__(self, doc_title: str = "Untitled") -> None:
        """Initialise the converter.

        Args:
            doc_title: The document title for front-matter metadata.
        """
        self.doc_title: str = doc_title
        self._lines: List[str] = []
        self._list_stack: List[Tuple[str, int]] = []
        self._lists_map: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def convert(self, doc: Dict[str, Any]) -> str:
        """Convert a full Google Docs API document to a Markdown string.

        Args:
            doc: The document resource returned by documents.get().

        Returns:
            A Markdown-formatted string with YAML front matter.
        """
        self.doc_title = doc.get("title", "Untitled")
        self._lists_map = doc.get("lists", {})
        self._lines = []
        self._list_stack = []

        body = doc.get("body", {})
        content = body.get("content", [])

        for element in content:
            self._convert_element(element)

        front_matter = self._build_front_matter(doc)
        return front_matter + "\n".join(self._lines)

    def _build_front_matter(self, doc: Dict[str, Any]) -> str:
        """Build a YAML front matter block from document metadata."""
        title = doc.get("title", "Untitled")
        revision = doc.get("revisionId", "")
        lines = ["---"]
        lines.append(f'title: "{title}"')
        if revision:
            lines.append(f"revision: {revision}")
        lines.append("source: google-docs-api")
        lines.append(
            f"generated: {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}"
        )
        lines.append("---\n")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Element dispatch
    # ------------------------------------------------------------------

    def _convert_element(self, element: Dict[str, Any]) -> None:
        """Dispatch a single structural element to its converter."""
        if "paragraph" in element:
            self.convert_paragraph(element["paragraph"])
        elif "table" in element:
            self.convert_table(element["table"])
        elif "sectionBreak" in element:
            self._handle_section_break()

    # ------------------------------------------------------------------
    # Paragraphs (including headings, lists)
    # ------------------------------------------------------------------

    def convert_paragraph(self, para: Dict[str, Any]) -> None:
        """Convert a paragraph element to Markdown.

        Args:
            para: The paragraph resource from the Docs API.
        """
        styled_name = para.get("paragraphStyle", {}).get(
            "namedStyleType", "NORMAL_TEXT"
        )
        elements = para.get("elements", [])
        bullet = para.get("bullet")

        # Check for horizontal rule or page break.
        if self._is_horizontal_rule(para):
            self._flush_list()
            self._lines.append("---")
            return

        text = self._convert_paragraph_elements(elements)

        if not text and not bullet:
            if not self._list_stack:
                self._lines.append("")
            return

        # --- List handling ---
        if bullet:
            self._handle_list_item(bullet, text)
            return

        # --- Non-list paragraph ---
        self._flush_list()

        if re.search("HEADING_", styled_name):
            level_str = styled_name.replace("HEADING_", "")
            if level_str.isdigit():
                level_num = min(int(level_str), 6)
                prefix = "#" * level_num
                self._lines.append(f"{prefix} {text}")
            else:
                self._lines.append(text)
        elif "SUBTITLE" in styled_name:
            self._lines.append(f"## {text}")
        elif "TITLE" in styled_name:
            self._lines.append(f"# {text}")
        else:
            self._lines.append(text)

    @staticmethod
    def _is_horizontal_rule(para: Dict[str, Any]) -> bool:
        """Check if a paragraph is purely a page break / horizontal rule."""
        elements = para.get("elements", [])
        if not elements:
            return False
        for el in elements:
            if "pageBreak" in el:
                return True
        return False

    # ------------------------------------------------------------------
    # Inline text conversion
    # ------------------------------------------------------------------

    def _convert_paragraph_elements(
        self, elements: List[Dict[str, Any]]
    ) -> str:
        """Convert a list of paragraph elements to a single Markdown string.

        Args:
            elements: List of ParagraphElement resources.

        Returns:
            A Markdown-formatted inline string.
        """
        parts: List[str] = []
        for el in elements:
            if "textRun" in el:
                parts.append(self._convert_text_run(el["textRun"]))
            elif "inlineObjectElement" in el:
                obj = el["inlineObjectElement"]
                obj_id = obj.get("objectId", "unknown")
                parts.append(f"![inline-image]({obj_id})")
            elif "footnoteReference" in el:
                fn = el["footnoteReference"]
                parts.append(f"[^{fn.get('footnoteNumber', 'note')}]")
        return "".join(parts).strip()

    def _convert_text_run(self, text_run: Dict[str, Any]) -> str:
        """Convert a single TextRun to a Markdown-formatted string part.

        Args:
            text_run: A TextRun resource.

        Returns:
            A Markdown string segment.
        """
        content = text_run.get("content", "")
        if not content:
            return ""

        style = text_run.get("textStyle", {})
        return self._apply_inline_style(content, style)

    def _apply_inline_style(self, text: str, style: Dict[str, Any]) -> str:
        """Apply text style markers around text for various inline styles.

        Order of wrapping:
          1. Inline code (monospace font heuristic)
          2. Strikethrough -> ~~text~~
          3. Bold -> **text**
          4. Italic -> *text*
          5. Underline -> <u>text</u> (no native Markdown)
          6. Link -> [text](url)

        Args:
            text: The plain text content.
            style: The textStyle dictionary.

        Returns:
            Markdown-formatted inline string.
        """
        if not text:
            return ""

        is_bold = style.get("bold", False)
        is_italic = style.get("italic", False)
        is_strikethrough = style.get("strikethrough", False)
        is_code = self._is_inline_code(style)
        link = style.get("link")
        link_url = link.get("url") if link else None
        is_underline = style.get("underline", False)

        result = text

        # 1. Inline code (skip other styling for code spans).
        if is_code:
            escaped = self._escape_backticks(text)
            return f"`{escaped}`"

        # 2. Strikethrough.
        if is_strikethrough:
            result = f"~~{result}~~"

        # 3. Bold.
        if is_bold:
            result = f"**{result}**"

        # 4. Italic.
        if is_italic:
            result = f"*{result}*"

        # Note: bold + italic both = ***text***

        # 5. Underline.
        if is_underline:
            result = f"<u>{result}</u>"

        # 6. Link.
        if link_url:
            result = f"[{result}]({link_url})"

        return result

    @staticmethod
    def _escape_backticks(text: str) -> str:
        """Escape backticks inside inline code spans."""
        if "`" in text:
            return f"` {text} `"
        return text

    @staticmethod
    def _is_inline_code(style: Dict[str, Any]) -> bool:
        """Heuristic detection of inline code via monospace font family."""
        weighted = style.get("weightedFontFamily")
        if weighted:
            family = weighted.get("fontFamily", "")
            monospace_keywords = [
                "consolas", "courier", "monaco", "monospace", "fira code"
            ]
            if any(kw in family.lower() for kw in monospace_keywords):
                return True
        return False

    # ------------------------------------------------------------------
    # List handling
    # ------------------------------------------------------------------

    def _handle_list_item(self, bullet: Dict[str, Any], text: str) -> None:
        """Process a paragraph that is part of a list (bullet or numbered)."""
        list_id = bullet.get("listId", "")
        nesting_level = bullet.get("nestingLevel", 0)

        is_ordered = self._is_ordered_list(list_id, nesting_level)
        self._adjust_list_stack(list_id, nesting_level)

        indent = "  " * nesting_level
        if is_ordered:
            prefix = f"{indent}1. "
        else:
            prefix = f"{indent}- "

        self._lines.append(f"{prefix}{text}")

    def _is_ordered_list(self, list_id: str, nesting_level: int) -> bool:
        """Return True if the list/nesting-level uses ordered (numbered) glyphs."""
        lst = self._lists_map.get(list_id)
        if not lst:
            return False
        nesting_levels = lst.get("listProperties", {}).get("nestingLevels", [])
        if nesting_level < len(nesting_levels):
            glyph_type = nesting_levels[nesting_level].get("glyphType", "")
            return glyph_type != "BULLET"
        return False

    def _adjust_list_stack(self, list_id: str, nesting_level: int) -> None:
        """Maintain list stack so we can insert blank lines when lists end.

        Each entry is (list_id, nesting_level).  Pop entries that no longer
        match the current context, then push the current one.
        """
        while self._list_stack:
            top_id, top_level = self._list_stack[-1]
            if top_id != list_id or top_level > nesting_level:
                self._list_stack.pop()
                if top_level > nesting_level:
                    self._lines.append("")
            else:
                break

        if (
            not self._list_stack
            or self._list_stack[-1] != (list_id, nesting_level)
        ):
            self._list_stack.append((list_id, nesting_level))

    def _flush_list(self) -> None:
        """End all active lists by clearing the stack."""
        if self._list_stack:
            self._list_stack.clear()
            self._lines.append("")

    # ------------------------------------------------------------------
    # Tables
    # ------------------------------------------------------------------

    def convert_table(self, table: Dict[str, Any]) -> None:
        """Convert a Google Docs table to a Markdown table.

        Args:
            table: The table resource from the Docs API.
        """
        rows = table.get("tableRows", [])
        if not rows:
            return

        self._flush_list()

        cells: List[List[str]] = []
        for row in rows:
            row_cells: List[str] = []
            for cell in row.get("tableCells", []):
                cell_text = self._extract_cell_text(cell)
                row_cells.append(cell_text)
            cells.append(row_cells)

        if not cells:
            return

        num_cols = max(len(r) for r in cells)
        for row in cells:
            while len(row) < num_cols:
                row.append("")

        header_sep = "|" + "|".join("---" for _ in range(num_cols)) + "|"
        self._lines.append("|" + "|".join(cells[0]) + "|")
        self._lines.append(header_sep)
        for row in cells[1:]:
            self._lines.append("|" + "|".join(row) + "|")

        self._lines.append("")

    @staticmethod
    def _extract_cell_text(cell: Dict[str, Any]) -> str:
        """Extract plain-text from a table cell's content."""
        parts: List[str] = []
        for el in cell.get("content", []):
            para = el.get("paragraph")
            if para:
                for pe in para.get("elements", []):
                    tr = pe.get("textRun")
                    if tr:
                        parts.append(tr.get("content", ""))
        return "".join(parts).strip().replace("|", "\\|")

    # ------------------------------------------------------------------
    # Section breaks / page breaks
    # ------------------------------------------------------------------

    def _handle_section_break(self) -> None:
        """Handle a section break (rendered as ``)."""
        self._flush_list()
        self._lines.append("---")


# ===================================================================
# GoogleDocsConverter
# ===================================================================


class GoogleDocsConverter:
    """Fetch and convert Google Docs documents using the Google Docs API (Approach 1).

    Supports both OAuth 2.0 client secrets and service-account JSON key files.

    Attributes:
        auth_type: 'oauth' or 'service_account'.
        creds_path: Path to the credentials JSON file.
        service: The authenticated Google Docs API service object.
        drive_service: The authenticated Google Drive API service object.
    """

    SCOPES = [
        "https://www.googleapis.com/auth/documents.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]

    def __init__(self, auth_type: str = "service_account", creds_path: str = "") -> None:
        """Initialise the converter.

        Args:
            auth_type: Authentication type — 'oauth' or 'service_account'.
            creds_path: Path to the credentials JSON file.
        """
        self.auth_type = auth_type
        self.creds_path = Path(creds_path)
        self.service: Any = None
        self.drive_service: Any = None

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def authenticate(self) -> None:
        """Authenticate and build API service objects.

        Raises:
            FileNotFoundError: If the credentials file does not exist.
            json.JSONDecodeError: If the credentials file is not valid JSON.
            ValueError: If auth_type is unsupported.
            Exception: On other authentication failures.
        """
        if not self.creds_path.exists():
            raise FileNotFoundError(
                f"Credentials file not found: {self.creds_path}"
            )

        if self.auth_type == "service_account":
            self._authenticate_service_account()
        elif self.auth_type == "oauth":
            self._authenticate_oauth()
        else:
            raise ValueError(f"Unsupported auth_type: {self.auth_type}")

    def _authenticate_service_account(self) -> None:
        """Authenticate using a service-account JSON key file."""
        from google.oauth2 import service_account

        credentials = service_account.Credentials.from_service_account_file(
            str(self.creds_path), scopes=self.SCOPES
        )
        self._build_services(credentials)

    def _authenticate_oauth(self) -> None:
        """Authenticate using OAuth 2.0 client secrets (installed app flow)."""
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request

        token_path = self.creds_path.parent / "token.pickle"

        credentials = None
        if token_path.exists():
            with open(token_path, "rb") as f:
                credentials = pickle.load(f)

        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())

        if not credentials or not credentials.valid:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(self.creds_path), self.SCOPES
            )
            credentials = flow.run_local_server(port=0)
            with open(token_path, "wb") as f:
                pickle.dump(credentials, f)
            log.info("OAuth credentials cached to %s", token_path)

        self._build_services(credentials)

    def _build_services(self, credentials: Any) -> None:
        """Build the Docs and Drive API service objects.

        Args:
            credentials: Authenticated Google credentials.

        Raises:
            ImportError: If googleapiclient is not installed.
        """
        try:
            import googleapiclient.discovery
            import googleapiclient.errors
        except ImportError as exc:
            raise ImportError(
                "google-api-python-client is not installed. "
                "Run: pip install google-api-python-client google-auth-httplib2"
            ) from exc

        self.service = googleapiclient.discovery.build(
            "docs", "v1", credentials=credentials
        )
        self.drive_service = googleapiclient.discovery.build(
            "drive", "v3", credentials=credentials
        )
        log.info("Google API services initialised successfully.")

    # ------------------------------------------------------------------
    # Fetch document (Approach 1)
    # ------------------------------------------------------------------

    def get_document(self, doc_id: str) -> Dict[str, Any]:
        """Fetch a Google Doc's content via the Docs API.

        Args:
            doc_id: The Google Docs document ID (from the URL).

        Returns:
            The full document resource as a dictionary.

        Raises:
            RuntimeError: On API errors (invalid ID, auth failure, quota).
        """
        if not self.service:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        try:
            import googleapiclient.errors
            doc = self.service.documents().get(documentId=doc_id).execute()
            log.info(
                "Fetched document: %s (revision: %s)",
                doc.get("title"), doc.get("revisionId"),
            )
            return doc
        except googleapiclient.errors.HttpError as exc:
            status = exc.resp.status if hasattr(exc, "resp") else "unknown"
            reason = str(exc)
            if status == 404:
                raise RuntimeError(
                    f"Document not found (404): {doc_id}. "
                    "Check that the ID is correct and the document is shared with "
                    "your authenticated account."
                ) from exc
            elif status == 403:
                raise RuntimeError(
                    f"Access denied (403) for document: {doc_id}. "
                    "Ensure the document is shared with your authenticated account."
                ) from exc
            elif status == 429:
                raise RuntimeError(
                    "Quota exceeded (429). Please wait and retry."
                ) from exc
            else:
                raise RuntimeError(
                    f"Google Docs API error (HTTP {status}): {reason}"
                ) from exc
        except Exception as exc:
            raise RuntimeError(
                f"Network or unexpected error fetching document {doc_id}: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Convert document to Markdown via MarkdownConverter
    # ------------------------------------------------------------------

    def doc_to_markdown(self, doc: Dict[str, Any]) -> str:
        """Convert a fetched document into Markdown (Approach 1).

        Args:
            doc: The document resource from get_document().

        Returns:
            A Markdown string with YAML front matter.
        """
        converter = MarkdownConverter(doc_title=doc.get("title", "Untitled"))
        return converter.convert(doc)

    # ------------------------------------------------------------------
    # Export as HTML via Drive API (Approach 2)
    # ------------------------------------------------------------------

    def export_as_html(self, doc_id: str) -> str:
        """Export a Google Doc as an HTML string using the Drive API.

        Approach 2: uses files.export with mimeType 'text/html',
        then converts the HTML to Markdown with html2text.

        Args:
            doc_id: The Google Docs document ID.

        Returns:
            A Markdown string derived from the exported HTML.

        Raises:
            RuntimeError: On export failures.
        """
        if not self.drive_service:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        try:
            import googleapiclient.errors
            request = self.drive_service.files().export(
                fileId=doc_id, mimeType="text/html"
            )
            html_content = request.execute()
            if isinstance(html_content, bytes):
                html_text = html_content.decode("utf-8")
            else:
                html_text = html_content
            log.info(
                "Exported document %s as HTML (%d bytes)", doc_id, len(html_text)
            )
            return self._html_to_markdown(html_text)

        except googleapiclient.errors.HttpError as exc:
            status = exc.resp.status if hasattr(exc, "resp") else "unknown"
            if status == 404:
                raise RuntimeError(
                    f"Document not found (404): {doc_id}."
                ) from exc
            elif status == 403:
                raise RuntimeError(
                    f"Access denied (403) for document: {doc_id}."
                ) from exc
            raise RuntimeError(
                f"Drive API export error (HTTP {status}): {exc}"
            ) from exc
        except Exception as exc:
            raise RuntimeError(
                f"Unexpected error during HTML export: {exc}"
            ) from exc

    def _html_to_markdown(self, html_content: str) -> str:
        """Convert HTML content to Markdown using html2text or markdownify.

        Args:
            html_content: Raw HTML string from the Drive API export.

        Returns:
            A Markdown string.

        Raises:
            RuntimeError: If neither html2text nor markdownify is installed.
        """
        try:
            import html2text

            h = html2text.HTML2Text()
            h.body_width = 0
            h.ignore_links = False
            h.ignore_images = False
            h.protect_links = True
            h.mark_code = True
            h.unicode_snob = True
            return h.handle(html_content)

        except ImportError:
            try:
                import markdownify

                return markdownify.markdownify(
                    html_content,
                    heading_style="ATX",
                    bullets="-",
                    strip=["script", "style"],
                )
            except ImportError:
                raise RuntimeError(
                    "Neither html2text nor markdownify is installed. "
                    "Install html2text: pip install html2text"
                )

    # ------------------------------------------------------------------
    # Check file type via Drive API
    # ------------------------------------------------------------------

    def check_file_type(self, doc_id: str) -> Dict[str, Any]:
        """Get file metadata (name, mimeType, size) from Drive API.

        Args:
            doc_id: The file ID.

        Returns:
            Dictionary with id, name, mimeType, size.

        Raises:
            RuntimeError: On API errors.
        """
        if not self.drive_service:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        try:
            import googleapiclient.errors
            meta = self.drive_service.files().get(
                fileId=doc_id, fields="id,name,mimeType,size"
            ).execute()
            return meta
        except googleapiclient.errors.HttpError as exc:
            status = exc.resp.status if hasattr(exc, "resp") else "unknown"
            raise RuntimeError(
                f"Drive API error (HTTP {status}) checking file {doc_id}: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Download .docx and convert via mammoth (Approach 3)
    # ------------------------------------------------------------------

    def docx_to_markdown(self, doc_id: str) -> Tuple[str, Dict[str, Any]]:
        """Download a .docx file from Drive and convert to Markdown via mammoth.

        Approach 3: handles Office documents (.docx) that are not native
        Google Docs. Uses the Drive API to download the binary, then
        mammoth to convert it to Markdown.

        Args:
            doc_id: The file ID.

        Returns:
            Tuple of (markdown_string, doc_metadata_dict).

        Raises:
            RuntimeError: On download or conversion failures.
        """
        if not self.drive_service:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        # 1. Check file type first
        meta = self.check_file_type(doc_id)
        mime = meta.get("mimeType", "")
        file_name = meta.get("name", doc_id)

        if mime != "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            log.warning(
                "File %s has unexpected mime type: %s (expected .docx)",
                doc_id, mime,
            )

        # 2. Download the .docx binary
        try:
            import googleapiclient.errors
            request = self.drive_service.files().get_media(fileId=doc_id)
            content = request.execute()
            log.info("Downloaded %s (%s, %d bytes)", file_name, mime, len(content))
        except googleapiclient.errors.HttpError as exc:
            status = exc.resp.status if hasattr(exc, "resp") else "unknown"
            raise RuntimeError(
                f"Failed to download file (HTTP {status}): {exc}"
            ) from exc

        # 3. Convert via mammoth (needs a file-like object, not raw bytes)
        try:
            import mammoth
            import io
            result = mammoth.convert_to_markdown(io.BytesIO(content))
            md_body = result.value
            messages = result.messages
            if messages:
                for msg in messages:
                    log.warning("mammoth: %s", msg.message)
            log.info(
                "Converted .docx to Markdown (%d chars, %d warnings)",
                len(md_body), len(messages),
            )
        except ImportError as exc:
            raise RuntimeError(
                "mammoth is not installed. Install it: pip install mammoth"
            ) from exc
        except Exception as exc:
            raise RuntimeError(
                f"mammoth conversion error: {exc}"
            ) from exc

        # 4. Build front matter
        doc_meta = {"title": file_name, "mimeType": mime}
        fm = self._build_docx_front_matter(file_name)
        return fm + md_body, doc_meta

    @staticmethod
    def _build_docx_front_matter(file_name: str) -> str:
        """Build YAML front matter for .docx-derived Markdown."""
        lines = ["---"]
        lines.append(f'title: "{Path(file_name).stem}"')
        lines.append("source: docx-mammoth")
        lines.append(
            f"generated: {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}"
        )
        lines.append("---\n")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Google Keep via Drive API (Approach 4)
    # ------------------------------------------------------------------

    def keep_to_markdown(self, doc_id: str) -> Tuple[str, Dict[str, Any]]:
        """Export a Google Keep note to Markdown via the Drive API.

        Keep notes are stored in Drive with mime type
        application/vnd.google-apps.note. They are exported to HTML
        and then converted to Markdown via html2text/markdownify.

        Args:
            doc_id: The Drive file ID of the Keep note.

        Returns:
            Tuple of (markdown_string, doc_metadata_dict).

        Raises:
            RuntimeError: On export or conversion failures.
        """
        if not self.drive_service:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        # Fetch metadata to get the note title
        meta = self.check_file_type(doc_id)
        file_name = meta.get("name", doc_id)
        mime = meta.get("mimeType", "")

        if mime != KEEP_NOTE_MIME:
            log.warning(
                "File %s has mime type '%s', expected '%s'",
                doc_id, mime, KEEP_NOTE_MIME,
            )

        try:
            import googleapiclient.errors
            request = self.drive_service.files().export(
                fileId=doc_id, mimeType="text/html"
            )
            html_content = request.execute()
            if isinstance(html_content, bytes):
                html_text = html_content.decode("utf-8")
            else:
                html_text = html_content
        except googleapiclient.errors.HttpError as exc:
            status = exc.resp.status if hasattr(exc, "resp") else "unknown"
            raise RuntimeError(
                f"Keep export error (HTTP {status}) for {doc_id}: {exc}"
            ) from exc

        # Convert HTML to Markdown
        md_body = self._html_to_markdown(html_text)

        # Build front matter
        doc_meta = {"title": file_name, "mimeType": mime}
        fm = self._build_keep_front_matter(file_name)
        return fm + md_body, doc_meta

    @staticmethod
    def _build_keep_front_matter(file_name: str) -> str:
        """Build YAML front matter for Keep-note-derived Markdown."""
        lines = ["---"]
        lines.append(f'title: "{Path(file_name).stem}"')
        lines.append("source: google-keep")
        lines.append(
            f"generated: {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}"
        )
        lines.append("---\n")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Markdown → PDF conversion
    # ------------------------------------------------------------------

    @staticmethod
    def md_to_pdf(md_content: str, output_path: Path) -> Path:
        """Convert a Markdown string to a PDF file.

        Uses the 'markdown' library to convert MD → HTML, then
        weasyprint to convert HTML → PDF.

        Args:
            md_content: The Markdown content.
            output_path: Desired output path (should end in .pdf).

        Returns:
            The Path to the generated PDF file.

        Raises:
            RuntimeError: If markdown or weasyprint is not installed.
        """
        try:
            import markdown as md_lib
            html_body = md_lib.markdown(
                md_content,
                extensions=["fenced_code", "tables", "codehilite"],
            )
        except ImportError as exc:
            raise RuntimeError(
                "markdown library is not installed. Run: pip install markdown"
            ) from exc

        html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Document</title>
<style>
  body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 2cm; font-size: 11pt; line-height: 1.5; }}
  h1 {{ font-size: 20pt; margin-top: 1.5em; }}
  h2 {{ font-size: 16pt; margin-top: 1.2em; }}
  h3 {{ font-size: 13pt; margin-top: 1em; }}
  code {{ background: #f4f4f4; padding: 2px 4px; border-radius: 3px; font-size: 10pt; }}
  pre {{ background: #f4f4f4; padding: 10px; border-radius: 4px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1em 0; }}
  th, td {{ border: 1px solid #ccc; padding: 6px 10px; text-align: left; }}
  th {{ background: #eee; }}
  img {{ max-width: 100%; }}
</style></head>
<body>{html_body}</body></html>"""

        try:
            from weasyprint import HTML
            HTML(string=html_doc).write_pdf(str(output_path))
            log.info("Generated PDF: %s", output_path)
            return output_path
        except ImportError as exc:
            raise RuntimeError(
                "weasyprint is not installed. Run: pip install weasyprint"
            ) from exc
        except Exception as exc:
            raise RuntimeError(f"PDF generation failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def get_document_title(doc: Dict[str, Any]) -> str:
        """Extract and sanitise the document title for use as a filename.

        Args:
            doc: The document resource.

        Returns:
            A filesystem-safe filename stem.
        """
        title = doc.get("title", "Untitled")
        safe = re.sub(r'[<>:"/\\|?*]', "_", title)
        return safe.strip() or "Untitled"

    def save_markdown(
        self,
        doc: Dict[str, Any],
        md_content: str,
        output_dir: Path,
        output_format: str = "md",
    ) -> Path:
        """Save content to a file named after the document title.

        Args:
            doc: The document resource (used for title extraction).
            md_content: The Markdown string to write.
            output_dir: Directory where the file will be saved.
            output_format: 'md' (Markdown) or 'pdf' (PDF).

        Returns:
            The Path to the saved file.
        """
        safe_title = self.get_document_title(doc)
        ext = "pdf" if output_format == "pdf" else "md"
        filename = f"{safe_title}.{ext}"
        output_dir.mkdir(parents=True, exist_ok=True)
        filepath = output_dir / filename

        if output_format == "pdf":
            # Save the intermediate Markdown as well for reference
            md_path = output_dir / f"{safe_title}.md"
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(md_content)
            log.info("Saved intermediate Markdown to %s", md_path)
        else:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(md_content)

        log.info("Saved content to %s", filepath)
        return filepath


# ===================================================================
# CLI
# ===================================================================


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Argument list (defaults to sys.argv[1:]).

    Returns:
        Parsed namespace.
    """
    parser = argparse.ArgumentParser(
        description="Convert Google Docs documents to Markdown.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "doc_ids",
        nargs="+",
        help="One or more Google Docs document IDs to convert.",
    )
    parser.add_argument(
        "--creds",
        required=True,
        help=(
            "Path to OAuth client secrets JSON file (--auth oauth) or "
            "service-account JSON key file (--auth service_account)."
        ),
    )
    parser.add_argument(
        "--auth",
        choices=["oauth", "service_account"],
        default="service_account",
        help=(
            "Authentication type. 'oauth' uses OAuth 2.0 installed-app flow. "
            "'service_account' uses a Google Cloud service-account key. "
            "Default: %(default)s."
        ),
    )
    parser.add_argument(
        "--method",
        choices=["api", "export", "docx", "keep"],
        default="api",
        help=(
            "Conversion method. 'api' (default) — Google Docs API structural "
            "parsing (native Docs only). 'export' — Drive HTML export + converter. "
            "'docx' — download .docx + mammoth (Office files). "
            "'keep' — export Google Keep note via Drive API."
        ),
    )
    parser.add_argument(
        "--format",
        choices=["md", "pdf"],
        default="md",
        help="Output format. 'md' (default) — Markdown. 'pdf' — PDF via weasyprint.",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="./output",
        help="Output directory for converted files. Default: %(default)s.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable DEBUG-level logging.",
    )

    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point.

    Args:
        argv: Argument list (defaults to sys.argv[1:]).

    Returns:
        Exit code (0 = success, 1 = error).
    """
    args = _parse_args(argv)

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    output_dir = Path(args.output)

    # --- Initialise and authenticate converter ---
    try:
        converter = GoogleDocsConverter(
            auth_type=args.auth, creds_path=args.creds
        )
        converter.authenticate()
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        log.error("Authentication setup failed: %s", exc)
        return 1

    successes = 0
    failures = 0

    for doc_id in args.doc_ids:
        log.info("Processing document: %s", doc_id)
        try:
            if args.method == "api":
                doc = converter.get_document(doc_id)
                md = converter.doc_to_markdown(doc)
            elif args.method == "docx":
                md, doc = converter.docx_to_markdown(doc_id)
            elif args.method == "keep":
                md, doc = converter.keep_to_markdown(doc_id)
            else:
                # method == "export"
                md = converter.export_as_html(doc_id)
                try:
                    doc = converter.get_document(doc_id)
                except Exception:
                    doc = {"title": doc_id}
                md = _wrap_with_front_matter(md, doc)

            # Convert to PDF if requested
            if args.format == "pdf":
                saved = converter.save_markdown(doc, md, output_dir, "pdf")
                converter.md_to_pdf(md, saved)
            else:
                saved = converter.save_markdown(doc, md, output_dir, "md")
            log.info("Successfully converted -> %s", saved)
            successes += 1

        except RuntimeError as exc:
            log.error("Failed to process %s: %s", doc_id, exc)
            failures += 1
        except Exception as exc:
            log.error(
                "Unexpected error processing %s: %s [%s]",
                doc_id, exc, type(exc).__name__,
            )
            failures += 1

    log.info("Done. %d succeeded, %d failed.", successes, failures)
    return 0 if failures == 0 else 1


def _wrap_with_front_matter(md_body: str, doc: Dict[str, Any]) -> str:
    """Wrap existing Markdown content with YAML front matter for export method.

    Args:
        md_body: The Markdown body from HTML export conversion.
        doc: The document resource (or minimal dict with 'title').

    Returns:
        Markdown with front matter prepended.
    """
    title = doc.get("title", "Untitled")
    revision = doc.get("revisionId", "")
    lines = ["---"]
    lines.append(f'title: "{title}"')
    if revision:
        lines.append(f"revision: {revision}")
    lines.append("source: google-docs-export")
    lines.append(
        f"generated: {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}"
    )
    lines.append("---")
    lines.append("")
    return "\n".join(lines) + md_body


# ===================================================================
# Entry point
# ===================================================================

if __name__ == "__main__":
    sys.exit(main())