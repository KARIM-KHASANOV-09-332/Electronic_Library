from pydantic import BaseModel, Field
from typing import Optional


class BookDirectCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(default="")
    genre: Optional[str] = Field(default=None, max_length=100)

    access_level: str = Field(default="free", description="free / licensed / subscription")
    copyright_holder: Optional[str] = Field(default=None, max_length=255)
    license_name: Optional[str] = Field(default=None, max_length=255)

    uploaded_by_user_id: Optional[str] = None
    author_user_id: Optional[str] = None


class BookModerationDecision(BaseModel):
    status: str = Field(..., description="published или rejected")
    moderator_comment: Optional[str] = ""
    changed_by_user_id: Optional[str] = None


class AuthorBookUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(default="")
    genre: Optional[str] = Field(default=None, max_length=100)
    access_level: str = Field(default="free")
    copyright_holder: Optional[str] = Field(default=None, max_length=255)
    license_name: Optional[str] = Field(default=None, max_length=255)