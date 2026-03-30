import asyncio
import random
import string
import logging
# Чтобы импорт работал корректно при запуске скрипта из корня backend/
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database_handler import db_handler

# Настраиваем логирование, чтобы видеть процесс в терминале
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("Worker")


async def generate_unique_card(email: str) -> str:
    """Генерирует уникальный номер билета, обрабатывая возможные коллизии в БД"""
    max_retries = 3

    for attempt in range(max_retries):
        random_digits = ''.join(random.choices(string.digits, k=6))
        card_number = f"LIB-{random_digits}"

        try:
            # Пытаемся присвоить номер пользователю
            query = """
                UPDATE users 
                SET library_card = $1 
                WHERE email = $2 AND library_card IS NULL
                RETURNING id;
            """
            result = await db_handler.fetch_row(query, card_number, email)

            if result:
                return card_number
            else:
                raise Exception("Пользователь не найден или билет уже был сгенерирован")

        except Exception as e:
            # Ловим ошибку нарушения уникальности, если такой билет уже случайно выпал кому-то другому
            if "unique constraint" in str(e).lower() or "UniqueViolationError" in type(e).__name__:
                logger.warning(f"Коллизия номера {card_number}. Попытка {attempt + 1} из {max_retries}...")
                continue
            raise e

    raise Exception("Не удалось сгенерировать уникальный билет после 3 попыток")


async def process_jobs():
    logger.info("Воркер успешно запущен и ожидает задачи...")
    await db_handler.connect()

    try:
        while True:
            # 1. Ищем одну задачу в статусе pending
            # FOR UPDATE SKIP LOCKED - это магия PostgreSQL. Она блокирует строку от других воркеров,
            # но не заставляет их ждать, а говорит "пропусти эту строку и бери следующую".
            find_job_query = """
                SELECT id, user_email 
                FROM analysis_jobs 
                WHERE status = 'pending' AND task_type = 'generate_card'
                LIMIT 1 
                FOR UPDATE SKIP LOCKED;
            """
            job = await db_handler.fetch_row(find_job_query)

            if not job:
                # Если задач нет, засыпаем на 2 секунды, чтобы не перегружать базу запросами
                await asyncio.sleep(2)
                continue

            job_id = job['id']
            email = job['user_email']
            logger.info(f"Взята в работу задача #{job_id} для пользователя {email}")

            # 2. Переводим статус в processing (в обработке)
            await db_handler.execute("UPDATE analysis_jobs SET status = 'processing' WHERE id = $1", job_id)

            try:
                # 3. Имитируем тяжелую задачу (если нужно) и генерируем билет
                await asyncio.sleep(1)
                card_number = await generate_unique_card(email)

                # 4. Помечаем задачу как успешно завершенную
                await db_handler.execute("UPDATE analysis_jobs SET status = 'completed' WHERE id = $1", job_id)
                logger.info(f"Задача #{job_id} завершена. Билет {card_number} закреплен за {email}")

            except Exception as e:
                logger.error(f"Ошибка при обработке задачи #{job_id}: {e}")
                # Если что-то сломалось, помечаем задачу как ошибочную, чтобы расследовать позже
                await db_handler.execute("UPDATE analysis_jobs SET status = 'failed' WHERE id = $1", job_id)

    finally:
        await db_handler.disconnect()


if __name__ == "__main__":
    # Запускаем асинхронный цикл
    asyncio.run(process_jobs())