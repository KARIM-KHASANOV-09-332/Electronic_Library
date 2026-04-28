from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import FileResponse
from core.database_handler import db_handler
from schemas.book import (
    AuthorBookUpdate,
    BookAccessUpdate,
    BookDirectCreate,
    BookModerationDecision,
    BookmarkCreate,
    BookmarkUpdate,
    UserBookAction,
)
import logging
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/books", tags=["Книги"])

UPLOAD_DIR = Path("uploads/books")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

PUBLIC_BOOK_STATUS = "published"
ALLOWED_ACCESS_LEVELS = {"free", "licensed", "subscription", "restricted"}
ALLOWED_ADMIN_STATUSES = {"published", "hidden", "rejected", "pending_review"}


async def get_user_or_404(user_id: str):
    user = await db_handler.fetch_row(
        "SELECT id, role FROM users WHERE id = $1::uuid;",
        user_id,
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


async def get_book_or_404(book_id: str):
    book = await db_handler.fetch_row(
        """
        SELECT id, title, status, access_level
        FROM books
        WHERE id = $1::uuid;
        """,
        book_id,
    )
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


async def ensure_active_loan(user_id: str, book_id: str):
    loan = await db_handler.fetch_row(
        """
        SELECT id, user_id, book_id, borrowed_at, due_at, returned_at, status
        FROM book_loans
        WHERE user_id = $1::uuid
          AND book_id = $2::uuid
          AND status = 'active'
          AND returned_at IS NULL
          AND due_at >= CURRENT_TIMESTAMP;
        """,
        user_id,
        book_id,
    )
    if not loan:
        raise HTTPException(status_code=403, detail="Book is not currently borrowed by this user")
    return loan


def loan_to_dict(row):
    return {
        "id": str(row["loan_id"]),
        "book_id": str(row["book_id"]),
        "title": row["title"],
        "genre": row["genre"],
        "description": row["description"],
        "author_name": row["author_name"],
        "borrowed_at": row["borrowed_at"],
        "due_at": row["due_at"],
        "returned_at": row["returned_at"],
        "status": row["loan_status"],
    }


def bookmark_to_dict(row):
    progress = row["progress_percent"]
    return {
        "id": str(row["id"]),
        "user_id": str(row["user_id"]),
        "book_id": str(row["book_id"]),
        "title": row["title"],
        "page_number": row["page_number"],
        "position_label": row["position_label"],
        "progress_percent": float(progress) if progress is not None else None,
        "note": row["note"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


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


@router.post("/moderator/upload")
async def moderator_upload_book(
    title: str = Form(...),
    description: str = Form(""),
    genre: str = Form(""),
    access_level: str = Form("free"),
    copyright_holder: str = Form(""),
    license_name: str = Form(""),
    author_user_id: str | None = Form(None),
    uploaded_by_user_id: str | None = Form(None),
    book_file: UploadFile = File(...),
):
    try:
        if access_level not in ALLOWED_ACCESS_LEVELS:
            raise HTTPException(status_code=400, detail="Invalid access level")

        if uploaded_by_user_id:
            moderator = await get_user_or_404(uploaded_by_user_id)
            if moderator["role"] not in ("moderator", "admin"):
                raise HTTPException(status_code=403, detail="Only moderators can upload directly")

        original_name = book_file.filename or ""
        extension = original_name.split(".")[-1].lower() if "." in original_name else ""
        if extension not in ("pdf", "epub"):
            raise HTTPException(status_code=400, detail="Only PDF and EPUB files are allowed")

        stored_filename = f"{uuid.uuid4()}.{extension}"
        stored_path = UPLOAD_DIR / stored_filename
        content = await book_file.read()
        with open(stored_path, "wb") as f:
            f.write(content)

        book_row = await db_handler.fetch_row(
            """
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
            RETURNING id, title, status, source_type;
            """,
            title.strip(),
            description.strip(),
            genre.strip() if genre else None,
            author_user_id,
            uploaded_by_user_id,
            access_level,
            copyright_holder.strip() if copyright_holder else None,
            license_name.strip() if license_name else None,
        )

        await db_handler.execute(
            """
            INSERT INTO book_files (
                book_id,
                file_type,
                file_path,
                original_filename
            )
            VALUES ($1::uuid, $2, $3, $4);
            """,
            str(book_row["id"]),
            extension,
            str(stored_path),
            original_name,
        )

        await db_handler.execute(
            """
            INSERT INTO book_status_history (book_id, old_status, new_status, comment, changed_by_user_id)
            VALUES ($1::uuid, NULL, 'published', 'Book uploaded directly by moderator', $2::uuid);
            """,
            str(book_row["id"]),
            uploaded_by_user_id,
        )

        return {
            "status": "success",
            "book": {
                "id": str(book_row["id"]),
                "title": book_row["title"],
                "status": book_row["status"],
                "source_type": book_row["source_type"],
                "original_filename": original_name,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Moderator upload book error: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload book")


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


@router.get("/catalog")
async def search_catalog(
    q: str | None = Query(default=None, description="Search by title, author or genre"),
    genre: str | None = Query(default=None),
):
    try:
        search_value = f"%{q.strip()}%" if q and q.strip() else None
        genre_value = f"%{genre.strip()}%" if genre and genre.strip() else None

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
              AND (
                  $1::text IS NULL
                  OR b.title ILIKE $1
                  OR b.genre ILIKE $1
                  OR u.name ILIKE $1
              )
              AND ($2::text IS NULL OR b.genre ILIKE $2)
            ORDER BY b.created_at DESC;
        """
        rows = await db_handler.fetch_all(query, search_value, genre_value)

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
        logger.error(f"Catalog search error: {e}")
        raise HTTPException(status_code=500, detail="Failed to load catalog")


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


@router.post("/{book_id}/borrow")
async def borrow_book(book_id: str, payload: UserBookAction):
    try:
        user = await get_user_or_404(payload.user_id)
        if user["role"] != "reader":
            raise HTTPException(status_code=403, detail="Only readers can borrow books")

        book = await get_book_or_404(book_id)
        if book["status"] != PUBLIC_BOOK_STATUS:
            raise HTTPException(status_code=400, detail="Book is not available for borrowing")

        existing_loan = await db_handler.fetch_row(
            """
            SELECT id
            FROM book_loans
            WHERE user_id = $1::uuid
              AND book_id = $2::uuid
              AND status = 'active'
              AND returned_at IS NULL;
            """,
            payload.user_id,
            book_id,
        )
        if existing_loan:
            raise HTTPException(status_code=409, detail="Book is already borrowed by this user")

        loan = await db_handler.fetch_row(
            """
            INSERT INTO book_loans (user_id, book_id)
            VALUES ($1::uuid, $2::uuid)
            RETURNING id, borrowed_at, due_at, returned_at, status;
            """,
            payload.user_id,
            book_id,
        )

        return {
            "status": "success",
            "loan": {
                "id": str(loan["id"]),
                "book_id": book_id,
                "user_id": payload.user_id,
                "borrowed_at": loan["borrowed_at"],
                "due_at": loan["due_at"],
                "returned_at": loan["returned_at"],
                "status": loan["status"],
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        if "unique" in str(e).lower():
            raise HTTPException(status_code=409, detail="Book is already borrowed by this user")
        logger.error(f"Borrow book error: {e}")
        raise HTTPException(status_code=500, detail="Failed to borrow book")


@router.post("/{book_id}/return")
async def return_book(book_id: str, payload: UserBookAction):
    try:
        await get_user_or_404(payload.user_id)
        await get_book_or_404(book_id)

        loan = await db_handler.fetch_row(
            """
            UPDATE book_loans
            SET status = 'returned',
                returned_at = CURRENT_TIMESTAMP
            WHERE user_id = $1::uuid
              AND book_id = $2::uuid
              AND status = 'active'
              AND returned_at IS NULL
            RETURNING id, borrowed_at, due_at, returned_at, status;
            """,
            payload.user_id,
            book_id,
        )
        if not loan:
            raise HTTPException(status_code=404, detail="Active loan not found")

        return {
            "status": "success",
            "loan": {
                "id": str(loan["id"]),
                "book_id": book_id,
                "user_id": payload.user_id,
                "borrowed_at": loan["borrowed_at"],
                "due_at": loan["due_at"],
                "returned_at": loan["returned_at"],
                "status": loan["status"],
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Return book error: {e}")
        raise HTTPException(status_code=500, detail="Failed to return book")


@router.get("/users/{user_id}/loans/current")
async def get_current_loans(user_id: str):
    try:
        await get_user_or_404(user_id)
        rows = await db_handler.fetch_all(
            """
            SELECT
                l.id AS loan_id,
                l.status AS loan_status,
                l.borrowed_at,
                l.due_at,
                l.returned_at,
                b.id AS book_id,
                b.title,
                b.genre,
                b.description,
                u.name AS author_name
            FROM book_loans l
            JOIN books b ON b.id = l.book_id
            LEFT JOIN users u ON u.id = b.author_user_id
            WHERE l.user_id = $1::uuid
              AND l.status = 'active'
              AND l.returned_at IS NULL
              AND l.due_at >= CURRENT_TIMESTAMP
            ORDER BY l.due_at ASC;
            """,
            user_id,
        )
        return [loan_to_dict(row) for row in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Current loans error: {e}")
        raise HTTPException(status_code=500, detail="Failed to load current loans")


@router.get("/users/{user_id}/loans/history")
async def get_loan_history(user_id: str):
    try:
        await get_user_or_404(user_id)
        rows = await db_handler.fetch_all(
            """
            SELECT
                l.id AS loan_id,
                l.status AS loan_status,
                l.borrowed_at,
                l.due_at,
                l.returned_at,
                b.id AS book_id,
                b.title,
                b.genre,
                b.description,
                u.name AS author_name
            FROM book_loans l
            JOIN books b ON b.id = l.book_id
            LEFT JOIN users u ON u.id = b.author_user_id
            WHERE l.user_id = $1::uuid
              AND (
                  l.status = 'returned'
                  OR l.returned_at IS NOT NULL
                  OR l.due_at < CURRENT_TIMESTAMP
              )
            ORDER BY COALESCE(l.returned_at, l.due_at) DESC;
            """,
            user_id,
        )
        return [loan_to_dict(row) for row in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Loan history error: {e}")
        raise HTTPException(status_code=500, detail="Failed to load loan history")


@router.get("/{book_id}/read")
async def read_book(book_id: str, user_id: str = Query(...)):
    try:
        await get_user_or_404(user_id)
        await ensure_active_loan(user_id, book_id)

        file_row = await db_handler.fetch_row(
            """
            SELECT id, file_type, file_path, original_filename
            FROM book_files
            WHERE book_id = $1::uuid
            ORDER BY created_at ASC
            LIMIT 1;
            """,
            book_id,
        )
        if not file_row:
            raise HTTPException(status_code=404, detail="Book file not found")

        file_path = Path(file_row["file_path"])
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Stored book file is missing")

        media_type = "application/pdf"
        if file_row["file_type"] == "epub":
            media_type = "application/epub+zip"

        return FileResponse(
            path=file_path,
            media_type=media_type,
            filename=file_row["original_filename"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Read book error: {e}")
        raise HTTPException(status_code=500, detail="Failed to open book file")


@router.post("/{book_id}/bookmarks")
async def create_bookmark(book_id: str, payload: BookmarkCreate):
    try:
        await get_user_or_404(payload.user_id)
        await get_book_or_404(book_id)
        await ensure_active_loan(payload.user_id, book_id)

        row = await db_handler.fetch_row(
            """
            INSERT INTO book_bookmarks (
                user_id,
                book_id,
                page_number,
                position_label,
                progress_percent,
                note
            )
            VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6)
            RETURNING id, user_id, book_id, page_number, position_label,
                      progress_percent, note, created_at, updated_at;
            """,
            payload.user_id,
            book_id,
            payload.page_number,
            payload.position_label,
            payload.progress_percent,
            payload.note,
        )

        return {
            "status": "success",
            "bookmark": {
                "id": str(row["id"]),
                "user_id": str(row["user_id"]),
                "book_id": str(row["book_id"]),
                "page_number": row["page_number"],
                "position_label": row["position_label"],
                "progress_percent": float(row["progress_percent"]) if row["progress_percent"] is not None else None,
                "note": row["note"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create bookmark error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create bookmark")


@router.get("/users/{user_id}/bookmarks")
async def get_user_bookmarks(user_id: str, book_id: str | None = Query(default=None)):
    try:
        await get_user_or_404(user_id)

        rows = await db_handler.fetch_all(
            """
            SELECT
                bm.id,
                bm.user_id,
                bm.book_id,
                bm.page_number,
                bm.position_label,
                bm.progress_percent,
                bm.note,
                bm.created_at,
                bm.updated_at,
                b.title
            FROM book_bookmarks bm
            JOIN books b ON b.id = bm.book_id
            WHERE bm.user_id = $1::uuid
              AND ($2::uuid IS NULL OR bm.book_id = $2::uuid)
            ORDER BY bm.updated_at DESC, bm.created_at DESC;
            """,
            user_id,
            book_id,
        )
        return [bookmark_to_dict(row) for row in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Load bookmarks error: {e}")
        raise HTTPException(status_code=500, detail="Failed to load bookmarks")


@router.put("/bookmarks/{bookmark_id}")
async def update_bookmark(bookmark_id: str, payload: BookmarkUpdate, user_id: str = Query(...)):
    try:
        await get_user_or_404(user_id)
        row = await db_handler.fetch_row(
            """
            UPDATE book_bookmarks
            SET page_number = COALESCE($1, page_number),
                position_label = COALESCE($2, position_label),
                progress_percent = COALESCE($3, progress_percent),
                note = COALESCE($4, note),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $5::uuid
              AND user_id = $6::uuid
            RETURNING id, user_id, book_id, page_number, position_label,
                      progress_percent, note, created_at, updated_at;
            """,
            payload.page_number,
            payload.position_label,
            payload.progress_percent,
            payload.note,
            bookmark_id,
            user_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Bookmark not found")

        book = await get_book_or_404(str(row["book_id"]))
        return {
            "status": "success",
            "bookmark": {
                "id": str(row["id"]),
                "user_id": str(row["user_id"]),
                "book_id": str(row["book_id"]),
                "title": book["title"],
                "page_number": row["page_number"],
                "position_label": row["position_label"],
                "progress_percent": float(row["progress_percent"]) if row["progress_percent"] is not None else None,
                "note": row["note"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update bookmark error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update bookmark")


@router.delete("/bookmarks/{bookmark_id}")
async def delete_bookmark(bookmark_id: str, user_id: str = Query(...)):
    try:
        await get_user_or_404(user_id)
        result = await db_handler.execute(
            """
            DELETE FROM book_bookmarks
            WHERE id = $1::uuid
              AND user_id = $2::uuid;
            """,
            bookmark_id,
            user_id,
        )
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Bookmark not found")

        return {"status": "success", "message": "Bookmark deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete bookmark error: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete bookmark")


@router.patch("/admin/{book_id}/access")
async def update_book_access(book_id: str, payload: BookAccessUpdate):
    try:
        if payload.access_level is not None and payload.access_level not in ALLOWED_ACCESS_LEVELS:
            raise HTTPException(status_code=400, detail="Invalid access level")
        if payload.status is not None and payload.status not in ALLOWED_ADMIN_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid book status")

        if payload.admin_user_id:
            admin = await get_user_or_404(payload.admin_user_id)
            if admin["role"] != "admin":
                raise HTTPException(status_code=403, detail="Only admins can manage book access")

        old_book = await get_book_or_404(book_id)

        updated = await db_handler.fetch_row(
            """
            UPDATE books
            SET access_level = COALESCE($1, access_level),
                status = COALESCE($2, status),
                moderator_comment = COALESCE($3, moderator_comment),
                updated_at = CURRENT_TIMESTAMP,
                published_at = CASE
                    WHEN $2 = 'published' AND published_at IS NULL THEN CURRENT_TIMESTAMP
                    ELSE published_at
                END
            WHERE id = $4::uuid
            RETURNING id, title, access_level, status, moderator_comment;
            """,
            payload.access_level,
            payload.status,
            payload.comment,
            book_id,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Book not found")

        if payload.status and payload.status != old_book["status"]:
            await db_handler.execute(
                """
                INSERT INTO book_status_history (
                    book_id,
                    old_status,
                    new_status,
                    comment,
                    changed_by_user_id
                )
                VALUES ($1::uuid, $2, $3, $4, $5::uuid);
                """,
                book_id,
                old_book["status"],
                payload.status,
                payload.comment,
                payload.admin_user_id,
            )

        return {
            "status": "success",
            "book": {
                "id": str(updated["id"]),
                "title": updated["title"],
                "access_level": updated["access_level"],
                "status": updated["status"],
                "comment": updated["moderator_comment"],
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update book access error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update book access")


@router.get("/admin/statistics")
async def get_book_statistics(admin_user_id: str | None = Query(default=None)):
    try:
        if admin_user_id:
            admin = await get_user_or_404(admin_user_id)
            if admin["role"] != "admin":
                raise HTTPException(status_code=403, detail="Only admins can view statistics")

        totals = await db_handler.fetch_row(
            """
            SELECT
                COUNT(*) AS total_books,
                COUNT(*) FILTER (WHERE status = 'published') AS published_books,
                COUNT(*) FILTER (WHERE status = 'pending_review') AS pending_books,
                COUNT(*) FILTER (WHERE status = 'rejected') AS rejected_books,
                COUNT(*) FILTER (WHERE status = 'hidden') AS hidden_books
            FROM books;
            """
        )
        loans = await db_handler.fetch_row(
            """
            SELECT
                COUNT(*) AS total_loans,
                COUNT(*) FILTER (WHERE status = 'active' AND returned_at IS NULL AND due_at >= CURRENT_TIMESTAMP) AS active_loans,
                COUNT(*) FILTER (WHERE status = 'returned' OR returned_at IS NOT NULL) AS returned_loans,
                COUNT(*) FILTER (WHERE status = 'active' AND returned_at IS NULL AND due_at < CURRENT_TIMESTAMP) AS overdue_loans
            FROM book_loans;
            """
        )
        popular_books = await db_handler.fetch_all(
            """
            SELECT
                b.id,
                b.title,
                b.genre,
                COUNT(l.id) AS borrow_count
            FROM books b
            LEFT JOIN book_loans l ON l.book_id = b.id
            GROUP BY b.id, b.title, b.genre
            ORDER BY borrow_count DESC, b.title ASC
            LIMIT 10;
            """
        )
        popular_genres = await db_handler.fetch_all(
            """
            SELECT
                COALESCE(b.genre, 'unknown') AS genre,
                COUNT(l.id) AS borrow_count
            FROM books b
            LEFT JOIN book_loans l ON l.book_id = b.id
            GROUP BY COALESCE(b.genre, 'unknown')
            ORDER BY borrow_count DESC, genre ASC
            LIMIT 10;
            """
        )

        return {
            "books": {
                "total": totals["total_books"],
                "published": totals["published_books"],
                "pending_review": totals["pending_books"],
                "rejected": totals["rejected_books"],
                "hidden": totals["hidden_books"],
            },
            "loans": {
                "total": loans["total_loans"],
                "active": loans["active_loans"],
                "returned": loans["returned_loans"],
                "overdue": loans["overdue_loans"],
            },
            "popular_books": [
                {
                    "id": str(row["id"]),
                    "title": row["title"],
                    "genre": row["genre"],
                    "borrow_count": row["borrow_count"],
                }
                for row in popular_books
            ],
            "popular_genres": [
                {
                    "genre": row["genre"],
                    "borrow_count": row["borrow_count"],
                }
                for row in popular_genres
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Book statistics error: {e}")
        raise HTTPException(status_code=500, detail="Failed to load statistics")


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
            SET status = $1::varchar,
                moderator_comment = $2,
                updated_at = CURRENT_TIMESTAMP,
                published_at = CASE WHEN $1::varchar = 'published' THEN CURRENT_TIMESTAMP ELSE published_at END
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
