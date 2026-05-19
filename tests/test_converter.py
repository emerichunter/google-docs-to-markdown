#!/usr/bin/env python3
"""
Unit tests for Google Docs → Markdown converter.

Tests the MarkdownConverter with a mock document to verify structural
conversion fidelity (headings, lists, tables, inline styles, etc.)
without requiring live API access.
"""
import sys
import json
import unittest
from pathlib import Path

# Allow running from project root or tests/ directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google_docs_to_markdown import MarkdownConverter, _parse_args


class TestMarkdownConverter(unittest.TestCase):
    """Verify that MarkdownConverter produces correct Markdown output."""

    def setUp(self):
        self.converter = MarkdownConverter()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _convert(self, overrides: dict | None = None) -> str:
        """Convert a rich mock document to Markdown."""
        doc = self._mock_document()
        if overrides:
            doc.update(overrides)
        return self.converter.convert(doc)

    @staticmethod
    def _mock_document() -> dict:
        """Return a representative mock Google Doc API response."""
        return {
            "title": "Test Document",
            "revisionId": "rev001",
            "lists": {},
            "body": {
                "content": [
                    # Title
                    {
                        "paragraph": {
                            "paragraphStyle": {"namedStyleType": "TITLE"},
                            "elements": [
                                {"textRun": {"content": "Main Title", "textStyle": {}}}
                            ],
                        }
                    },
                    # Subtitle
                    {
                        "paragraph": {
                            "paragraphStyle": {"namedStyleType": "SUBTITLE"},
                            "elements": [
                                {
                                    "textRun": {
                                        "content": "A document subtitle",
                                        "textStyle": {},
                                    }
                                }
                            ],
                        }
                    },
                    # Heading 1
                    {
                        "paragraph": {
                            "paragraphStyle": {"namedStyleType": "HEADING_1"},
                            "elements": [
                                {
                                    "textRun": {
                                        "content": "Introduction",
                                        "textStyle": {},
                                    }
                                }
                            ],
                        }
                    },
                    # Paragraph with inline styles
                    {
                        "paragraph": {
                            "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                            "elements": [
                                {
                                    "textRun": {
                                        "content": "Normal text with ",
                                        "textStyle": {},
                                    }
                                },
                                {
                                    "textRun": {
                                        "content": "bold",
                                        "textStyle": {"bold": True},
                                    }
                                },
                                {
                                    "textRun": {
                                        "content": ", ",
                                        "textStyle": {},
                                    }
                                },
                                {
                                    "textRun": {
                                        "content": "italic",
                                        "textStyle": {"italic": True},
                                    }
                                },
                                {
                                    "textRun": {
                                        "content": ", ",
                                        "textStyle": {},
                                    }
                                },
                                {
                                    "textRun": {
                                        "content": "strikethrough",
                                        "textStyle": {"strikethrough": True},
                                    }
                                },
                                {
                                    "textRun": {
                                        "content": ", and a ",
                                        "textStyle": {},
                                    }
                                },
                                {
                                    "textRun": {
                                        "content": "link",
                                        "textStyle": {
                                            "link": {"url": "https://example.com"}
                                        },
                                    }
                                },
                                {
                                    "textRun": {
                                        "content": ".",
                                        "textStyle": {},
                                    }
                                },
                            ],
                        }
                    },
                    # Heading 2
                    {
                        "paragraph": {
                            "paragraphStyle": {"namedStyleType": "HEADING_2"},
                            "elements": [
                                {
                                    "textRun": {
                                        "content": "Lists & Tables",
                                        "textStyle": {},
                                    }
                                }
                            ],
                        }
                    },
                    # Bullet list items
                    {
                        "paragraph": {
                            "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                            "bullet": {"listId": "l1", "nestingLevel": 0},
                            "elements": [
                                {
                                    "textRun": {
                                        "content": "First bullet item",
                                        "textStyle": {},
                                    }
                                }
                            ],
                        }
                    },
                    {
                        "paragraph": {
                            "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                            "bullet": {"listId": "l1", "nestingLevel": 0},
                            "elements": [
                                {
                                    "textRun": {
                                        "content": "Second bullet item",
                                        "textStyle": {},
                                    }
                                }
                            ],
                        }
                    },
                    # Table
                    {
                        "table": {
                            "tableRows": [
                                {
                                    "tableCells": [
                                        {
                                            "content": [
                                                {
                                                    "paragraph": {
                                                        "elements": [
                                                            {
                                                                "textRun": {
                                                                    "content": "Name",
                                                                    "textStyle": {},
                                                                }
                                                            }
                                                        ]
                                                    }
                                                }
                                            ]
                                        },
                                        {
                                            "content": [
                                                {
                                                    "paragraph": {
                                                        "elements": [
                                                            {
                                                                "textRun": {
                                                                    "content": "Value",
                                                                    "textStyle": {},
                                                                }
                                                            }
                                                        ]
                                                    }
                                                }
                                            ]
                                        },
                                    ]
                                },
                                {
                                    "tableCells": [
                                        {
                                            "content": [
                                                {
                                                    "paragraph": {
                                                        "elements": [
                                                            {
                                                                "textRun": {
                                                                    "content": "Alpha",
                                                                    "textStyle": {},
                                                                }
                                                            }
                                                        ]
                                                    }
                                                }
                                            ]
                                        },
                                        {
                                            "content": [
                                                {
                                                    "paragraph": {
                                                        "elements": [
                                                            {
                                                                "textRun": {
                                                                    "content": "100",
                                                                    "textStyle": {},
                                                                }
                                                            }
                                                        ]
                                                    }
                                                }
                                            ]
                                        },
                                    ]
                                },
                            ]
                        }
                    },
                ]
            },
        }

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_front_matter(self):
        """Should include YAML front matter with title and revision."""
        md = self._convert()
        self.assertIn("---\n", md)
        self.assertIn('title: "Test Document"', md)
        self.assertIn("revision: rev001", md)
        self.assertIn("source: google-docs-api", md)

    def test_title_and_subtitle(self):
        """TITLE → #, SUBTITLE → ##."""
        md = self._convert()
        self.assertIn("# Main Title", md)
        self.assertIn("## A document subtitle", md)

    def test_headings(self):
        """HEADING_1 → #, HEADING_2 → ##."""
        md = self._convert()
        self.assertIn("# Introduction", md)
        self.assertIn("## Lists & Tables", md)

    def test_inline_styles(self):
        """Bold → **, Italic → *, Strikethrough → ~~, Link → []()."""
        md = self._convert()
        self.assertIn("**bold**", md)
        self.assertIn("*italic*", md)
        self.assertIn("~~strikethrough~~", md)
        self.assertIn("[link](https://example.com)", md)

    def test_bullet_list(self):
        """Bullet paragraphs → - items."""
        md = self._convert()
        self.assertIn("- First bullet item", md)
        self.assertIn("- Second bullet item", md)

    def test_table(self):
        """Tables → pipe-delimited Markdown tables."""
        md = self._convert()
        self.assertIn("|Name|Value|", md)
        self.assertIn("|---|---|", md)
        self.assertIn("|Alpha|100|", md)

    def test_cli_parser(self):
        """CLI argument parser should accept expected flags."""
        args = _parse_args(
            [
                "--creds",
                "key.json",
                "--auth",
                "oauth",
                "--method",
                "export",
                "--output",
                "./out",
                "--verbose",
                "doc123",
                "doc456",
            ]
        )
        self.assertEqual(args.creds, "key.json")
        self.assertEqual(args.auth, "oauth")
        self.assertEqual(args.method, "export")
        self.assertEqual(args.output, "./out")
        self.assertTrue(args.verbose)
        self.assertEqual(args.doc_ids, ["doc123", "doc456"])

    def test_cli_parser_defaults(self):
        """CLI parser should apply sensible defaults."""
        args = _parse_args(["--creds", "key.json", "doc1"])
        self.assertEqual(args.auth, "service_account")
        self.assertEqual(args.method, "api")
        self.assertEqual(args.output, "./output")
        self.assertFalse(args.verbose)


if __name__ == "__main__":
    unittest.main()