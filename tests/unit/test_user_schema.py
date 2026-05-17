import unittest

from pydantic import ValidationError

from tests.test_support import BACKEND_DIR  # noqa: F401
from schemas.user import UserCreate, UserLogin


class UserSchemaTest(unittest.TestCase):
    def test_reader_registration_normalizes_phone_and_library_card(self):
        user = UserCreate(
            name="Иван",
            email="ivan@example.com",
            phone_number="8 (999) 123-45-67",
            password="Password1",
            library_card=" lib-123456 ",
            role="reader",
        )

        self.assertEqual(user.phone_number, "+79991234567")
        self.assertEqual(user.library_card, "LIB-123456")

    def test_password_requires_uppercase_lowercase_and_digit(self):
        with self.assertRaises(ValidationError):
            UserCreate(
                name="Иван",
                email="ivan@example.com",
                phone_number="+79991234567",
                password="password",
                role="reader",
            )

    def test_library_card_requires_expected_format(self):
        with self.assertRaises(ValidationError):
            UserCreate(
                name="Иван",
                email="ivan@example.com",
                phone_number="+79991234567",
                password="Password1",
                library_card="123456",
                role="reader",
            )

    def test_login_normalizes_phone_and_library_card(self):
        phone_login = UserLogin(login="8 (999) 123-45-67", password="Password1")
        card_login = UserLogin(login=" lib-123456 ", password="Password1")

        self.assertEqual(phone_login.login, "+79991234567")
        self.assertEqual(card_login.login, "LIB-123456")
