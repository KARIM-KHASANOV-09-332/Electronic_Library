from pathlib import Path
import unittest


ROOT_DIR = Path(__file__).resolve().parents[2]


def read_frontend() -> str:
    candidates = [
        ROOT_DIR / "frontend" / "main.py",
        Path("/app") / "frontend" / "main.py",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.read_text(encoding="utf-8")

    searched = ", ".join(str(candidate) for candidate in candidates)
    raise FileNotFoundError(f"Cannot find frontend/main.py. Searched: {searched}")


class FrontendSmokeTest(unittest.TestCase):
    def test_frontend_exposes_demo_pages_for_all_roles(self):
        frontend = read_frontend()

        self.assertIn('@ui.page("/")', frontend)
        self.assertIn('@ui.page("/dashboard")', frontend)
        self.assertIn('@ui.page("/author")', frontend)
        self.assertIn('@ui.page("/moderator")', frontend)
        self.assertIn('@ui.page("/admin")', frontend)
        self.assertIn('@ui.page("/reader/{book_id}")', frontend)

    def test_frontend_contains_reader_and_moderation_controls(self):
        frontend = read_frontend()

        self.assertIn("Сохранить закладку", frontend)
        self.assertIn("Скачать", frontend)
        self.assertIn("Открыть файл", frontend)
        self.assertIn("Описание книги", frontend)
