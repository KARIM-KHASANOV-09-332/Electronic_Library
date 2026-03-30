from pydantic import BaseModel, EmailStr, Field, field_validator
import re

class UserCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Имя читателя")
    email: EmailStr = Field(..., description="Электронная почта пользователя")
    password: str = Field(..., min_length=8, description="Пароль (минимум 8 символов)")

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError('Пароль должен содержать хотя бы одну заглавную букву')
        if not re.search(r"[a-z]", v):
            raise ValueError('Пароль должен содержать хотя бы одну строчную букву')
        if not re.search(r"\d", v):
            raise ValueError('Пароль должен содержать хотя бы одну цифру')
        return v