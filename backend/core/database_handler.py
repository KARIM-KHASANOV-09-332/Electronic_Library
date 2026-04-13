import asyncpg
import os
import logging
import asyncio

# Читаем URL базы данных из переменных окружения (которые мы задали в docker-compose.yml)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:rootpassword@localhost:5432/library_db")

logger = logging.getLogger(__name__)

class DatabaseHandler:
    def __init__(self):
        self.pool = None

    async def connect(self):
        """Создает пул соединений с базой данных с механизмом повторных попыток"""
        retries = 5
        while retries > 0:
            try:
                self.pool = await asyncpg.create_pool(DATABASE_URL)
                logger.info("Успешное подключение к пулу PostgreSQL!")
                return # Выходим из цикла при успешном подключении
            except Exception as e:
                retries -= 1
                logger.warning(f"База данных пока недоступна, ждем... Осталось попыток: {retries}")
                if retries == 0:
                    logger.error(f"Критическая ошибка: не удалось подключиться к БД: {e}")
                    raise e
                await asyncio.sleep(3) # Ждем 3 секунды перед следующей попыткой

    async def disconnect(self):
        """Закрывает все соединения при выключении приложения"""
        if self.pool:
            await self.pool.close()
            logger.info("Соединения с БД закрыты.")

    async def fetch_row(self, query: str, *args):
        """Выполняет запрос и возвращает одну строку (например, при INSERT ... RETURNING)"""
        async with self.pool.acquire() as connection:
            return await connection.fetchrow(query, *args)

    async def execute(self, query: str, *args):
        """Выполняет запрос без возврата данных (например, простой UPDATE)"""
        async with self.pool.acquire() as connection:
            return await connection.execute(query, *args)

    async def fetch_all(self, query: str, *args):
        """Выполняет запрос и возвращает список строк (удобно для поиска)"""
        async with self.pool.acquire() as connection:
            return await connection.fetch(query, *args)

# Создаем глобальный экземпляр (синглтон) для использования во всем проекте
db_handler = DatabaseHandler()