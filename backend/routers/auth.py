from fastapi import APIRouter, HTTPException
from schemas.user import UserCreate
from core.database_handler import db_handler
import hashlib
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["Регистрация и Авторизация"])


def hash_password(password: str) -> str:
    """Простое хэширование пароля (для старта)"""
    return hashlib.sha256(password.encode()).hexdigest()


@router.post("/register")
async def register_user(user: UserCreate):
    hashed_pw = hash_password(user.password)

    try:
        # Шаг 1: Записываем нового пользователя
        user_query = """
            INSERT INTO users (name, email, password_hash)
            VALUES ($1, $2, $3)
            RETURNING id, name, email;
        """
        new_user = await db_handler.fetch_row(user_query, user.name, user.email, hashed_pw)

        # Шаг 2: Создаем задачу для воркера в фоновой очереди
        # База данных сама подставит статус 'pending' и тип 'generate_card'
        job_query = """
            INSERT INTO analysis_jobs (user_email)
            VALUES ($1)
            RETURNING id, status;
        """
        new_job = await db_handler.fetch_row(job_query, user.email)

        logger.info(f"Пользователь {user.email} создан. Задача #{new_job['id']} добавлена в очередь.")

        return {
            "status": "success",
            "message": "Регистрация успешна. Читательский билет генерируется.",
            "user": {
                "id": str(new_user['id']),  # Превращаем UUID-объект в обычную строку
                "name": new_user['name'],
                "email": new_user['email']
            },
            "job": {
                "id": str(new_job['id']),  # То же самое здесь
                "status": new_job['status']
            }
        }

    except Exception as e:
        # Обработка дубликатов email
        if "unique constraint" in str(e).lower():
            raise HTTPException(status_code=400, detail="Пользователь с таким email уже существует")

        logger.error(f"Ошибка при регистрации: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.get("/profile/{user_id}")
async def get_user_profile(user_id: str):
    try:
        # $1::uuid - говорим базе, что строка это UUID
        query = "SELECT library_card FROM users WHERE id = $1::uuid;"
        user = await db_handler.fetch_row(query, user_id)

        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        return {"library_card": user['library_card']}

    except Exception as e:
        logger.error(f"Ошибка при получении профиля: {e}")
        raise HTTPException(status_code=500, detail="Ошибка сервера")