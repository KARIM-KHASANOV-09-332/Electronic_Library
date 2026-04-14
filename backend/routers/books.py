from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from core.database_handler import db_handler
from schemas.book import BookDirectCreate, BookModerationDecision, AuthorBookUpdate
import logging
import os
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/books", tags=["Книги"])

UPLOAD_DIR = Path("uploads/books")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/moderator/direct")
async def create_book_direct(payload: BookDirectCreate):
    try:
        query = """
            INSERT INTO books (
                title,
                description,
                genre,
                author_user_id,
                uploaded_by_user_id,
                access_level,
                copyright_holder,
                license_name,
                status,
                source_type,
                published_at
            )
            VALUES (
                $1, $2, $3,
                $4::uuid, $5::uuid,
                $6, $7, $8,
                'published',
                'moderator_direct',
                CURRENT_TIMESTAMP
            )
            RETURNING id, title, genre, status, source_type, created_at, published_at;
        """

        new_book = await db_handler.fetch_row(
            query,
            payload.title,
            payload.description or "",
            payload.genre,
            payload.author_user_id,
            payload.uploaded_by_user_id,
            payload.access_level,
            payload.copyright_holder,
            payload.license_name,
        )

        history_query = """
            INSERT INTO book_status_history (book_id, old_status, new_status, comment, changed_by_user_id)
            VALUES ($1::uuid, NULL, 'published', 'Книга добавлена модератором напрямую', $2::uuid);
        """
        await db_handler.execute(history_query, str(new_book["id"]), payload.uploaded_by_user_id)

        return {
            "status": "success",
            "book": {
                "id": str(new_book["id"]),
                "title": new_book["title"],
                "genre": new_book["genre"],
                "status": new_book["status"],
                "source_type": new_book["source_type"],
            }
        }
    except Exception as e:
        logger.error(f"Ошибка прямого добавления книги: {e}")
        raise HTTPException(status_code=500, detail="Не удалось добавить книгу")


@router.post("/author/upload")
async def author_upload_book(
    title: str = Form(...),
    description: str = Form(""),
    genre: str = Form(""),
    access_level: str = Form("free"),
    copyright_holder: str = Form(""),
    license_name: str = Form(""),
    author_user_id: str = Form(...),
    uploaded_by_user_id: str = Form(...),
    book_file: UploadFile = File(...)
):
    try:
        if not author_user_id.strip():
            raise HTTPException(status_code=400, detail="author_user_id обязателен")

        if not uploaded_by_user_id.strip():
            raise HTTPException(status_code=400, detail="uploaded_by_user_id обязателен")

        original_name = book_file.filename or ""
        extension = original_name.split(".")[-1].lower() if "." in original_name else ""

        if extension not in ("pdf", "epub"):
            raise HTTPException(status_code=400, detail="Разрешены только PDF и EPUB")

        stored_filename = f"{uuid.uuid4()}.{extension}"
        stored_path = UPLOAD_DIR / stored_filename

        content = await book_file.read()
        with open(stored_path, "wb") as f:
            f.write(content)

        insert_book_query = """
            INSERT INTO books (
                title,
                description,
                genre,
                author_user_id,
                uploaded_by_user_id,
                access_level,
                copyright_holder,
                license_name,
                status,
                source_type
            )
            VALUES (
                $1, $2, $3,
                $4::uuid, $5::uuid,
                $6, $7, $8,
                'pending_review',
                'author_upload'
            )
            RETURNING id, title, status, source_type;
        """

        book_row = await db_handler.fetch_row(
            insert_book_query,
            title.strip(),
            description.strip(),
            genre.strip() if genre else None,
            author_user_id,
            uploaded_by_user_id,
            access_level,
            copyright_holder.strip() if copyright_holder else None,
            license_name.strip() if license_name else None,
        )

        insert_file_query = """
            INSERT INTO book_files (
                book_id,
                file_type,
                file_path,
                original_filename
            )
            VALUES ($1::uuid, $2, $3, $4);
        """

        await db_handler.execute(
            insert_file_query,
            str(book_row["id"]),
            extension,
            str(stored_path),
            original_name
        )

        history_query = """
            INSERT INTO book_status_history (book_id, old_status, new_status, comment, changed_by_user_id)
            VALUES ($1::uuid, NULL, 'pending_review', 'Книга загружена автором и отправлена на модерацию', $2::uuid);
        """
        await db_handler.execute(history_query, str(book_row["id"]), author_user_id)

        return {
            "status": "success",
            "book": {
                "id": str(book_row["id"]),
                "title": book_row["title"],
                "status": book_row["status"],
                "source_type": book_row["source_type"],
                "original_filename": original_name,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка загрузки книги автором: {e}")
        raise HTTPException(status_code=500, detail="Не удалось загрузить книгу")


@router.put("/author/{book_id}")
async def author_update_book(book_id: str, payload: AuthorBookUpdate):
    try:
        existing = await db_handler.fetch_row(
            "SELECT id, status FROM books WHERE id = $1::uuid;",
            book_id
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Книга не найдена")

        await db_handler.execute(
            """
            UPDATE books
            SET title = $1,
                description = $2,
                genre = $3,
                access_level = $4,
                copyright_holder = $5,
                license_name = $6,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $7::uuid;
            """,
            payload.title.strip(),
            payload.description.strip() if payload.description else "",
            payload.genre.strip() if payload.genre else None,
            payload.access_level,
            payload.copyright_holder.strip() if payload.copyright_holder else None,
            payload.license_name.strip() if payload.license_name else None,
            book_id
        )

        return {"status": "success", "message": "Описание книги обновлено"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка обновления книги автором: {e}")
        raise HTTPException(status_code=500, detail="Не удалось обновить книгу")


@router.get("/author/{author_user_id}")
async def get_author_books(author_user_id: str):
    try:
        query = """
            SELECT
                b.id,
                b.title,
                b.genre,
                b.description,
                b.access_level,
                b.license_name,
                b.copyright_holder,
                b.status,
                b.source_type,
                b.moderator_comment,
                b.created_at,
                bf.original_filename,
                bf.file_type
            FROM books b
            LEFT JOIN book_files bf ON bf.book_id = b.id
            WHERE b.author_user_id = $1::uuid
            ORDER BY b.created_at DESC;
        """
        rows = await db_handler.fetch_all(query, author_user_id)

        return [
            {
                "id": str(row["id"]),
                "title": row["title"],
                "genre": row["genre"],
                "description": row["description"],
                "access_level": row["access_level"],
                "license_name": row["license_name"],
                "copyright_holder": row["copyright_holder"],
                "status": row["status"],
                "source_type": row["source_type"],
                "moderator_comment": row["moderator_comment"],
                "original_filename": row["original_filename"],
                "file_type": row["file_type"],
            }
            for row in rows
        ]
    except Exception as e:
        logger.error(f"Ошибка получения книг автора: {e}")
        raise HTTPException(status_code=500, detail="Не удалось получить книги автора")


@router.get("/published")
async def get_published_books():
    try:
        query = """
            SELECT
                b.id,
                b.title,
                b.genre,
                b.description,
                b.access_level,
                b.license_name,
                b.copyright_holder,
                b.status,
                b.created_at,
                b.published_at,
                u.name AS author_name
            FROM books b
            LEFT JOIN users u ON u.id = b.author_user_id
            WHERE b.status = 'published'
            ORDER BY b.created_at DESC;
        """
        rows = await db_handler.fetch_all(query)

        return [
            {
                "id": str(row["id"]),
                "title": row["title"],
                "genre": row["genre"],
                "description": row["description"],
                "access_level": row["access_level"],
                "license_name": row["license_name"],
                "copyright_holder": row["copyright_holder"],
                "status": row["status"],
                "author_name": row["author_name"],
            }
            for row in rows
        ]
    except Exception as e:
        logger.error(f"Ошибка получения опубликованных книг: {e}")
        raise HTTPException(status_code=500, detail="Не удалось получить список книг")


@router.get("/moderation/queue")
async def get_moderation_queue():
    try:
        query = """
            SELECT
                b.id,
                b.title,
                b.genre,
                b.description,
                b.status,
                b.source_type,
                b.moderator_comment,
                b.created_at,
                u.name AS author_name,
                bf.original_filename,
                bf.file_type
            FROM books b
            LEFT JOIN users u ON u.id = b.author_user_id
            LEFT JOIN book_files bf ON bf.book_id = b.id
            WHERE b.status IN ('pending_review', 'rejected')
            ORDER BY b.created_at DESC;
        """
        rows = await db_handler.fetch_all(query)

        return [
            {
                "id": str(row["id"]),
                "title": row["title"],
                "genre": row["genre"],
                "description": row["description"],
                "status": row["status"],
                "source_type": row["source_type"],
                "moderator_comment": row["moderator_comment"],
                "author_name": row["author_name"],
                "original_filename": row["original_filename"],
                "file_type": row["file_type"],
            }
            for row in rows
        ]
    except Exception as e:
        logger.error(f"Ошибка получения очереди модерации: {e}")
        raise HTTPException(status_code=500, detail="Не удалось получить очередь модерации")


@router.post("/{book_id}/moderation")
async def moderate_book(book_id: str, payload: BookModerationDecision):
    if payload.status not in ("published", "rejected"):
        raise HTTPException(status_code=400, detail="Допустимые статусы: published или rejected")

    try:
        old_row = await db_handler.fetch_row(
            "SELECT status FROM books WHERE id = $1::uuid;",
            book_id
        )
        if not old_row:
            raise HTTPException(status_code=404, detail="Книга не найдена")

        update_query = """
            UPDATE books
            SET status = $1,
                moderator_comment = $2,
                updated_at = CURRENT_TIMESTAMP,
                published_at = CASE WHEN $1 = 'published' THEN CURRENT_TIMESTAMP ELSE published_at END
            WHERE id = $3::uuid;
        """
        await db_handler.execute(update_query, payload.status, payload.moderator_comment, book_id)

        history_query = """
            INSERT INTO book_status_history (book_id, old_status, new_status, comment, changed_by_user_id)
            VALUES ($1::uuid, $2, $3, $4, $5::uuid);
        """
        await db_handler.execute(
            history_query,
            book_id,
            old_row["status"],
            payload.status,
            payload.moderator_comment,
            payload.changed_by_user_id
        )

        return {"status": "success", "message": "Статус книги обновлен"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка модерации книги: {e}")
        raise HTTPException(status_code=500, detail="Не удалось обновить статус книги")