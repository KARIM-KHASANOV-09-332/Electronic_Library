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


class UserBookAction(BaseModel):
    user_id: str


class BookmarkCreate(BaseModel):
    user_id: str
    page_number: Optional[int] = Field(default=None, ge=1)
    position_label: Optional[str] = Field(default=None, max_length=255)
    progress_percent: Optional[float] = Field(default=None, ge=0, le=100)
    note: Optional[str] = Field(default=None)


class BookmarkUpdate(BaseModel):
    page_number: Optional[int] = Field(default=None, ge=1)
    position_label: Optional[str] = Field(default=None, max_length=255)
    progress_percent: Optional[float] = Field(default=None, ge=0, le=100)
    note: Optional[str] = Field(default=None)


class BookAccessUpdate(BaseModel):
    access_level: Optional[str] = Field(default=None, description="free / licensed / subscription / restricted")
    status: Optional[str] = Field(default=None, description="published / hidden / rejected / pending_review")
    admin_user_id: Optional[str] = None
    comment: Optional[str] = Field(default=None)
