from fastapi import FastAPI
from contextlib import asynccontextmanager
from core.database_handler import db_handler
from routers import auth
from routers import admin
from routers import books


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db_handler.connect()
    yield
    await db_handler.disconnect()


app = FastAPI(title="Electronic Library API", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(books.router)