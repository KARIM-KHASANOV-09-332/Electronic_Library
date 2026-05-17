import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException

from tests.test_support import FakeDatabase
from routers import books
from schemas.book import BookModerationDecision, BookmarkCreate, UserBookAction


class BooksWorkflowTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.original_db = books.db_handler

    def tearDown(self):
        books.db_handler = self.original_db

    async def test_reader_can_borrow_published_book(self):
        user_id = str(uuid4())
        book_id = str(uuid4())
        loan_id = uuid4()
        now = datetime(2026, 5, 17, 12, 0, 0)
        books.db_handler = FakeDatabase(
            fetch_rows=[
                {"id": uuid4(), "role": "reader"},
                {"id": uuid4(), "title": "Clean Code", "status": "published", "access_level": "free"},
                None,
                {
                    "id": loan_id,
                    "borrowed_at": now,
                    "due_at": now + timedelta(days=14),
                    "returned_at": None,
                    "status": "active",
                },
            ]
        )

        result = await books.borrow_book(book_id, UserBookAction(user_id=user_id))

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["loan"]["id"], str(loan_id))
        self.assertEqual(result["loan"]["status"], "active")

    async def test_non_reader_cannot_borrow_book(self):
        books.db_handler = FakeDatabase(fetch_rows=[{"id": uuid4(), "role": "author"}])

        with self.assertRaises(HTTPException) as error:
            await books.borrow_book(str(uuid4()), UserBookAction(user_id=str(uuid4())))

        self.assertEqual(error.exception.status_code, 403)

    async def test_file_status_explains_missing_uploaded_file(self):
        user_id = str(uuid4())
        book_id = str(uuid4())
        books.db_handler = FakeDatabase(
            fetch_rows=[
                {"id": uuid4(), "role": "reader"},
                {
                    "id": uuid4(),
                    "user_id": uuid4(),
                    "book_id": uuid4(),
                    "borrowed_at": datetime(2026, 5, 17),
                    "due_at": datetime(2026, 5, 31),
                    "returned_at": None,
                    "status": "active",
                },
                {
                    "file_type": "pdf",
                    "file_path": "uploads/books/not-existing-file.pdf",
                    "original_filename": "book.pdf",
                },
            ]
        )

        result = await books.get_reader_file_status(book_id, user_id=user_id)

        self.assertFalse(result["available"])
        self.assertIn("Файл книги отсутствует", result["reason"])
        self.assertEqual(result["original_filename"], "book.pdf")

    async def test_create_bookmark_saves_page_progress_and_note(self):
        user_id = str(uuid4())
        book_id = str(uuid4())
        bookmark_id = uuid4()
        now = datetime(2026, 5, 17, 12, 0, 0)
        books.db_handler = FakeDatabase(
            fetch_rows=[
                {"id": uuid4(), "role": "reader"},
                {"id": uuid4(), "title": "Book", "status": "published", "access_level": "free"},
                {
                    "id": uuid4(),
                    "user_id": uuid4(),
                    "book_id": uuid4(),
                    "borrowed_at": now,
                    "due_at": now + timedelta(days=14),
                    "returned_at": None,
                    "status": "active",
                },
                {
                    "id": bookmark_id,
                    "user_id": user_id,
                    "book_id": book_id,
                    "page_number": 12,
                    "position_label": "Страница 12",
                    "progress_percent": Decimal("42.50"),
                    "note": "Продолжить отсюда",
                    "created_at": now,
                    "updated_at": now,
                },
            ]
        )

        result = await books.create_bookmark(
            book_id,
            BookmarkCreate(
                user_id=user_id,
                page_number=12,
                position_label="Страница 12",
                progress_percent=42.5,
                note="Продолжить отсюда",
            ),
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["bookmark"]["page_number"], 12)
        self.assertEqual(result["bookmark"]["progress_percent"], 42.5)
        self.assertEqual(result["bookmark"]["note"], "Продолжить отсюда")

    async def test_moderation_updates_book_status_and_history(self):
        book_id = str(uuid4())
        moderator_id = str(uuid4())
        books.db_handler = FakeDatabase(
            fetch_rows=[{"status": "pending_review"}],
            execute_results=["UPDATE 1", "INSERT 0"],
        )

        result = await books.moderate_book(
            book_id,
            BookModerationDecision(
                status="published",
                moderator_comment="Книга проверена",
                changed_by_user_id=moderator_id,
            ),
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(books.db_handler.execute_calls[0][1], ("published", "Книга проверена", book_id))
        self.assertEqual(
            books.db_handler.execute_calls[1][1],
            (book_id, "pending_review", "published", "Книга проверена", moderator_id),
        )
