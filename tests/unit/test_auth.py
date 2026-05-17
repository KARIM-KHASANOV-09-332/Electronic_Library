import unittest
from uuid import uuid4

from fastapi import HTTPException

from tests.test_support import FakeDatabase
from routers import auth
from schemas.user import UserCreate, UserLogin


class AuthRouterTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.original_db = auth.db_handler

    def tearDown(self):
        auth.db_handler = self.original_db

    async def test_register_reader_without_card_creates_worker_job(self):
        user_id = uuid4()
        auth.db_handler = FakeDatabase(
            fetch_rows=[
                {
                    "id": user_id,
                    "name": "Reader",
                    "email": "reader@example.com",
                    "library_card": None,
                    "role": "reader",
                },
                {"id": uuid4(), "status": "pending"},
            ]
        )

        result = await auth.register_user(
            UserCreate(
                name="Reader",
                email="reader@example.com",
                phone_number="+79991234567",
                password="Password1",
                role="reader",
            )
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["user"]["id"], str(user_id))
        self.assertEqual(result["user"]["role"], "reader")
        self.assertEqual(len(auth.db_handler.fetch_row_calls), 2)
        self.assertIn("analysis_jobs", auth.db_handler.fetch_row_calls[1][0])

    async def test_register_author_does_not_create_reader_card_job(self):
        user_id = uuid4()
        auth.db_handler = FakeDatabase(
            fetch_rows=[
                {
                    "id": user_id,
                    "name": "Author",
                    "email": "author@example.com",
                    "library_card": None,
                    "role": "author",
                }
            ]
        )

        result = await auth.register_user(
            UserCreate(
                name="Author",
                email="author@example.com",
                phone_number="+79991234568",
                password="Password1",
                role="author",
            )
        )

        self.assertEqual(result["user"]["role"], "author")
        self.assertEqual(len(auth.db_handler.fetch_row_calls), 1)

    async def test_login_invalid_credentials_returns_401(self):
        auth.db_handler = FakeDatabase(fetch_rows=[None])

        with self.assertRaises(HTTPException) as error:
            await auth.login_user(UserLogin(login="reader@example.com", password="Password1"))

        self.assertEqual(error.exception.status_code, 401)
