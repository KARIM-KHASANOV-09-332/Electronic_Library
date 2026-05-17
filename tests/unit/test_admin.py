import unittest
from uuid import uuid4

from fastapi import HTTPException

from tests.test_support import FakeDatabase
from routers import admin


class AdminRouterTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.original_db = admin.db_handler

    def tearDown(self):
        admin.db_handler = self.original_db

    async def test_update_user_role_rejects_unknown_role(self):
        payload = admin.RoleUpdate(
            new_role="superuser",
            target_email="user@example.com",
            admin_user_id=str(uuid4()),
        )

        with self.assertRaises(HTTPException) as error:
            await admin.update_user_role(str(uuid4()), payload)

        self.assertEqual(error.exception.status_code, 400)

    async def test_update_user_role_requires_admin_when_admin_id_is_passed(self):
        admin.db_handler = FakeDatabase(fetch_rows=[{"role": "moderator"}])
        payload = admin.RoleUpdate(
            new_role="author",
            target_email="user@example.com",
            admin_user_id=str(uuid4()),
        )

        with self.assertRaises(HTTPException) as error:
            await admin.update_user_role(str(uuid4()), payload)

        self.assertEqual(error.exception.status_code, 403)

    async def test_update_user_role_changes_role_and_logs_action(self):
        target_user_id = str(uuid4())
        admin.db_handler = FakeDatabase(
            fetch_rows=[{"role": "admin"}],
            execute_results=["UPDATE 1", "INSERT 0"],
        )
        payload = admin.RoleUpdate(
            new_role="moderator",
            target_email="user@example.com",
            admin_user_id=str(uuid4()),
        )

        result = await admin.update_user_role(target_user_id, payload)

        self.assertEqual(result["status"], "success")
        self.assertEqual(admin.db_handler.execute_calls[0][1], ("moderator", target_user_id))
        self.assertIn("analysis_jobs", admin.db_handler.execute_calls[1][0])
