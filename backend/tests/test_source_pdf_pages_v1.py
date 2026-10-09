import tempfile
import unittest
from pathlib import Path

import pymupdf

from app.services.source_pdf_pages import extract_clause_pdf_pages


class ClausePDFPageExtractionTests(unittest.TestCase):
    def test_exact_pages_and_vector_text_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "original.pdf"
            with pymupdf.open() as doc:
                for number in range(1, 78):
                    page = doc.new_page()
                    page.insert_text((72, 72), f"ORIGINAL PAGE {number}")
                    if number == 75:
                        page.draw_rect(pymupdf.Rect(50, 100, 150, 150))
                doc.save(path)
            original_size = path.stat().st_size
            selected = extract_clause_pdf_pages(path, 74, 75)
            self.assertTrue(selected.startswith(b"%PDF-"))
            with pymupdf.open(stream=selected, filetype="pdf") as excerpt:
                self.assertEqual(excerpt.page_count, 2)
                self.assertIn("ORIGINAL PAGE 74", excerpt[0].get_text())
                self.assertIn("ORIGINAL PAGE 75", excerpt[1].get_text())
                self.assertNotIn("ORIGINAL PAGE 76", excerpt[1].get_text())
                self.assertTrue(excerpt[1].get_drawings())
            self.assertEqual(path.stat().st_size, original_size)

    def test_invalid_ranges_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "one.pdf"
            with pymupdf.open() as doc:
                doc.new_page()
                doc.save(path)
            for start, end in [(0, 1), (2, 1), (1, 2), (None, None)]:
                with self.subTest(start=start, end=end):
                    with self.assertRaises(ValueError):
                        extract_clause_pdf_pages(path, start, end)


if __name__ == "__main__":
    unittest.main()
