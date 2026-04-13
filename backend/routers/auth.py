from fastapi import APIRouter, HTTPException
from schemas.user import UserCreate, UserLogin
from core.database_handler import db_handler
import hashlib
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["Регистрация и Авторизация"])

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

@router.post("/register")
async def register_user(user: UserCreate):
    hashed_pw = hash_password(user.password)
    try:
        # Добавили role в INSERT
        user_query = """
                     INSERT INTO users (name, email, phone_number, password_hash, library_card, role)
                     VALUES ($1, $2, $3, $4, $5, $6) RETURNING id, name, email, library_card, role; \
                     """
        new_user = await db_handler.fetch_row(user_query, user.name, user.email, user.phone_number, hashed_pw, user.library_card, user.role)

        # МАГИЯ: Закидываем задачу воркеру ТОЛЬКО если это читатель и у него нет билета
        if user.role == 'reader' and not user.library_card:
            job_query = "INSERT INTO analysis_jobs (user_email) VALUES ($1) RETURNING id, status;"
            await db_handler.fetch_row(job_query, user.email)

        return {
            "status": "success",
            "user": {
                "id": str(new_user['id']),
                "name": new_user['name'],
                "library_card": new_user['library_card'],
                "role": new_user['role'] # Возвращаем роль
            }
        }
    except Exception as e:
        if "unique constraint" in str(e).lower():
            raise HTTPException(status_code=400, detail="Этот email, телефон или билет уже заняты")
        raise HTTPException(status_code=500, detail="Ошибка сервера")

@router.post("/login")
async def login_user(credentials: UserLogin):
    hashed_pw = hash_password(credentials.password)
    try:
        # Добавили role в SELECT
        query = """
                SELECT id, name, library_card, role \
                FROM users
                WHERE (email = $1 OR phone_number = $1 OR library_card = $1) \
                  AND password_hash = $2; \
                """
        user = await db_handler.fetch_row(query, credentials.login, hashed_pw)

        if not user:
            raise HTTPException(status_code=401, detail="Неверные данные для входа")

        return {
            "status": "success",
            "user": {
                "id": str(user['id']),
                "name": user['name'],
                "library_card": user['library_card'],
                "role": user['role'] # Возвращаем роль
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка входа: {e}")
        raise HTTPException(status_code=500, detail="Ошибка сервера")

@router.get("/profile/{user_id}")
async def get_user_profile(user_id: str):
    try:
        query = "SELECT library_card FROM users WHERE id = $1::uuid;"
        user = await db_handler.fetch_row(query, user_id)
        if not user: raise HTTPException(status_code=404, detail="Пользователь не найден")
        return {"library_card": user['library_card']}
    except Exception:
        raise HTTPException(status_code=500, detail="Ошибка сервера")