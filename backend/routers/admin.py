from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from core.database_handler import db_handler
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["Админ-панель"])
ALLOWED_ROLES = {"reader", "author", "moderator", "admin"}


class RoleUpdate(BaseModel):
    new_role: str
    target_email: str  # Передаем email пользователя, чтобы записать в логи
    admin_user_id: Optional[str] = None


@router.get("/users/search")
async def search_users(q: str = Query(default="")):
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
        if payload.new_role not in ALLOWED_ROLES:
            raise HTTPException(status_code=400, detail="Недопустимая роль")

        if payload.admin_user_id:
            admin = await db_handler.fetch_row(
                "SELECT role FROM users WHERE id = $1::uuid;",
                payload.admin_user_id,
            )
            if not admin:
                raise HTTPException(status_code=404, detail="Администратор не найден")
            if admin["role"] != "admin":
                raise HTTPException(status_code=403, detail="Только администратор может менять роли")

        # 1. Обновляем роль
        update_query = "UPDATE users SET role = $1 WHERE id = $2::uuid;"
        result = await db_handler.execute(update_query, payload.new_role, user_id)
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        # 2. Записываем действие админа в логи (analysis_jobs)
        log_query = """
            INSERT INTO analysis_jobs (user_email, task_type, status) 
            VALUES ($1, $2, 'completed');
        """
        task_desc = f"role_changed_to_{payload.new_role}"
        await db_handler.execute(log_query, payload.target_email, task_desc)

        return {"status": "success", "message": "Роль успешно обновлена"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка смены роли: {e}")
        raise HTTPException(status_code=500, detail="Ошибка сервера")
