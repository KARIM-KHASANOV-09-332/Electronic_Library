from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
import re


class UserCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone_number: str = Field(..., description="Номер телефона")
    password: str = Field(..., min_length=8)
    # НОВОЕ: Опциональное поле для существующего билета
    library_card: Optional[str] = Field(None, description="Существующий номер билета")

    @field_validator('phone_number')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        cleaned = re.sub(r"[\s\-\(\)]", "", v)
        if not re.match(r"^(?:\+7|8)\d{10}$", cleaned):
            raise ValueError('Неверный формат телефона (пример: +79991234567)')
        if cleaned.startswith('8'):
            cleaned = '+7' + cleaned[1:]
        return cleaned

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v): raise ValueError('Нужна заглавная буква')
        if not re.search(r"[a-z]", v): raise ValueError('Нужна строчная буква')
        if not re.search(r"\d", v): raise ValueError('Нужна цифра')
        return v

    @field_validator('library_card')
    @classmethod
    def format_library_card(cls, v: Optional[str]) -> Optional[str]:
        if v:
            cleaned = v.strip().upper()  # Убираем пробелы и делаем заглавными

            # НОВОЕ: Строгая проверка формата (LIB- и 6 цифр)
            if not re.match(r"^LIB-\d{6}$", cleaned):
                raise ValueError('Билет должен быть в формате LIB-XXXXXX (где X - цифра)')

            return cleaned
        return v


class UserLogin(BaseModel):
    login: str = Field(..., description="Email, номер телефона или читательский билет")
    password: str

    @field_validator('login')
    @classmethod
    def normalize_login(cls, v: str) -> str:
        v = v.strip()
        if '@' in v:
            return v  # Это Email
        if re.search(r'[a-zA-Z]', v):
            return v.upper()  # Если есть буквы, значит это читательский билет (LIB-123)

        # Иначе это телефон, чистим его
        cleaned = re.sub(r"[\s\-\(\)]", "", v)
        if re.match(r"^(?:\+7|8)\d{10}$", cleaned):
            if cleaned.startswith('8'):
                return '+7' + cleaned[1:]
            return cleaned
        return v