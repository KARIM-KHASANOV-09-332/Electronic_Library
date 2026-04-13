from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from core.database_handler import db_handler
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["Админ-панель"])


class RoleUpdate(BaseModel):
    new_role: str
    target_email: str  # Передаем email пользователя, чтобы записать в логи


@router.get("/users/search")
async def search_users(q: str = Query(..., min_length=1)):
    try:
        # Ищем по имени или email, ограничиваем до 10 результатов для скорости
        query = """
            SELECT id, name, email, role 
            FROM users 
            WHERE name ILIKE $1 OR email ILIKE $1
            LIMIT 10;
        """
        # Предполагается, что в db_handler есть метод fetch_all (или fetch) для списка строк
        users = await db_handler.fetch_all(query, f"%{q}%")

        return [{"id": str(u['id']), "name": u['name'], "email": u['email'], "role": u['role']} for u in users]
    except Exception as e:
        logger.error(f"Ошибка поиска: {e}")
        return []


@router.post("/users/{user_id}/role")
async def update_user_role(user_id: str, payload: RoleUpdate):
    try:
        # 1. Обновляем роль
        update_query = "UPDATE users SET role = $1 WHERE id = $2::uuid;"
        await db_handler.execute(update_query, payload.new_role, user_id)

        # 2. Записываем действие админа в логи (analysis_jobs)
        log_query = """
            INSERT INTO analysis_jobs (user_email, task_type, status) 
            VALUES ($1, $2, 'completed');
        """
        task_desc = f"role_changed_to_{payload.new_role}"
        await db_handler.execute(log_query, payload.target_email, task_desc)

        return {"status": "success", "message": "Роль успешно обновлена"}
    except Exception as e:
        logger.error(f"Ошибка смены роли: {e}")
        raise HTTPException(status_code=500, detail="Ошибка сервера")