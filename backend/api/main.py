from fastapi import FastAPI
from contextlib import asynccontextmanager
from core.database_handler import db_handler
from routers import auth
from routers import admin

# Эта функция управляет событиями старта и остановки
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Логика до yield выполняется при запуске сервера
    await db_handler.connect()
    yield
    # Логика после yield выполняется при выключении сервера
    await db_handler.disconnect()

# Передаем lifespan в приложение
app = FastAPI(title="Electronic Library API", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(admin.router)