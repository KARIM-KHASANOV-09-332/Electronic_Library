from nicegui import app, ui
import httpx
import os
import tempfile
from urllib.parse import quote


API_BASE = os.getenv("API_BASE", "http://backend:8000")
BROWSER_API_BASE = os.getenv("BROWSER_API_BASE", "http://localhost:8000")

ROLE_LABELS = {
    "reader": "Читатель",
    "author": "Автор",
    "moderator": "Модератор",
    "admin": "Администратор",
}

ACCESS_LABELS = {
    "free": "Свободный доступ",
    "licensed": "По лицензии",
    "subscription": "По подписке",
    "restricted": "Ограничен",
}

STATUS_LABELS = {
    "published": "Опубликована",
    "pending_review": "На модерации",
    "rejected": "Отклонена",
    "hidden": "Скрыта",
    "active": "Активна",
    "returned": "Возвращена",
}


def current_user() -> dict:
    return app.storage.user.get("user", {})


def is_logged_in() -> bool:
    return bool(current_user().get("id"))


def require_login() -> dict | None:
    user = current_user()
    if not user.get("id"):
        ui.open("/")
        return None
    return user


def safe_json(response: httpx.Response):
    try:
        return response.json()
    except Exception:
        return {}


def detail_from(response: httpx.Response, fallback: str) -> str:
    detail = safe_json(response).get("detail", fallback)
    if isinstance(detail, list):
        return "; ".join(str(item.get("msg", item)) for item in detail)
    return str(detail)


async def api_get(path: str, params: dict | None = None):
    async with httpx.AsyncClient(timeout=60.0) as client:
        return await client.get(f"{API_BASE}{path}", params=params)


async def api_post(path: str, payload: dict):
    async with httpx.AsyncClient(timeout=60.0) as client:
        return await client.post(f"{API_BASE}{path}", json=payload)


async def api_put(path: str, payload: dict, params: dict | None = None):
    async with httpx.AsyncClient(timeout=60.0) as client:
        return await client.put(f"{API_BASE}{path}", json=payload, params=params)


async def api_patch(path: str, payload: dict):
    async with httpx.AsyncClient(timeout=60.0) as client:
        return await client.patch(f"{API_BASE}{path}", json=payload)


async def api_delete(path: str, params: dict | None = None):
    async with httpx.AsyncClient(timeout=60.0) as client:
        return await client.delete(f"{API_BASE}{path}", params=params)


def page_shell(title: str, active: str = "dashboard"):
    user = current_user()

    ui.colors(primary="#2563eb", secondary="#0f766e", accent="#b45309", positive="#16a34a")
    ui.query("body").classes("bg-slate-50 text-slate-900")

    with ui.header().classes("bg-white text-slate-900 border-b border-slate-200"):
        with ui.row().classes("w-full max-w-7xl mx-auto items-center justify-between px-4 py-2"):
            with ui.row().classes("items-center gap-3"):
                ui.icon("local_library").classes("text-3xl text-blue-700")
                with ui.column().classes("gap-0"):
                    ui.label("Электронная библиотека").classes("text-lg font-bold")
                    ui.label(title).classes("text-xs text-slate-500")

            if user:
                with ui.row().classes("items-center gap-2"):
                    ui.button("Кабинет", icon="dashboard", on_click=lambda: ui.open("/dashboard")).props(
                        "flat"
                    ).classes("text-slate-700")
                    if user.get("role") == "author":
                        ui.button("Автор", icon="edit_note", on_click=lambda: ui.open("/author")).props(
                            "flat"
                        ).classes("text-slate-700")
                    if user.get("role") in ("moderator", "admin"):
                        ui.button("Модерация", icon="rule", on_click=lambda: ui.open("/moderator")).props(
                            "flat"
                        ).classes("text-slate-700")
                    if user.get("role") == "admin":
                        ui.button("Админ", icon="admin_panel_settings", on_click=lambda: ui.open("/admin")).props(
                            "flat"
                        ).classes("text-slate-700")

                    ui.separator().props("vertical").classes("h-8 mx-1")
                    ui.label(user.get("name", "Пользователь")).classes("font-medium")
                    ui.badge(ROLE_LABELS.get(user.get("role"), user.get("role", ""))).classes("bg-teal-700")

                    def logout():
                        app.storage.user.clear()
                        ui.open("/")

                    ui.button(icon="logout", on_click=logout).props("flat round").classes("text-red-600")

    return ui.column().classes("w-full max-w-7xl mx-auto p-4 gap-4")


def metric(label: str, value, color: str):
    with ui.card().classes("p-4 rounded-lg border border-slate-200 shadow-sm"):
        ui.label(str(value)).classes(f"text-3xl font-bold {color}")
        ui.label(label).classes("text-sm text-slate-500")


def book_summary(book: dict):
    author = book.get("author_name") or "Автор не указан"
    genre = book.get("genre") or "Без жанра"
    access = ACCESS_LABELS.get(book.get("access_level"), book.get("access_level") or "Доступ не указан")
    ui.label(book.get("title") or "Без названия").classes("text-lg font-bold text-slate-900")
    ui.label(f"{author} · {genre} · {access}").classes("text-sm text-slate-500")
    description = book.get("description") or "Описание пока не добавлено."
    ui.label(description).classes("text-sm text-slate-700")


@ui.page("/")
def auth_page():
    ui.colors(primary="#2563eb", secondary="#0f766e", accent="#b45309", positive="#16a34a")
    ui.query("body").classes("bg-slate-50 text-slate-900")

    if is_logged_in():
        ui.timer(0.1, lambda: ui.open("/dashboard"), once=True)
        return

    with ui.column().classes("w-full min-h-screen"):
        with ui.row().classes("w-full max-w-6xl mx-auto flex-1 items-center px-4 py-8 gap-6"):
            with ui.column().classes("w-full lg:w-5/12 gap-4"):
                ui.icon("local_library").classes("text-6xl text-blue-700")
                ui.label("Электронная библиотека").classes("text-5xl font-bold leading-tight")
                ui.label("Каталог, выдача книг, авторские загрузки и модерация в одном учебном сервисе.").classes(
                    "text-lg text-slate-600"
                )
                with ui.row().classes("gap-2 mt-2"):
                    ui.badge("FastAPI").classes("bg-blue-700")
                    ui.badge("PostgreSQL").classes("bg-teal-700")
                    ui.badge("NiceGUI").classes("bg-amber-700")

            with ui.card().classes("w-full lg:w-7/12 p-6 rounded-lg shadow-lg border border-slate-200"):
                with ui.tabs().classes("w-full") as tabs:
                    login_tab = ui.tab("Вход", icon="login")
                    register_tab = ui.tab("Регистрация", icon="person_add")

                with ui.tab_panels(tabs, value=login_tab).classes("w-full"):
                    with ui.tab_panel(login_tab):
                        login_input = ui.input("Email, телефон или читательский билет").classes("w-full")
                        password_input = ui.input("Пароль", password=True, password_toggle_button=True).classes(
                            "w-full"
                        )
                        login_message = ui.label("").classes("text-red-600")

                        async def login():
                            login_message.text = ""
                            payload = {
                                "login": (login_input.value or "").strip(),
                                "password": (password_input.value or "").strip(),
                            }
                            if not payload["login"] or not payload["password"]:
                                login_message.text = "Заполни логин и пароль."
                                return

                            response = await api_post("/api/auth/login", payload)
                            if response.status_code != 200:
                                login_message.text = detail_from(response, "Не удалось войти.")
                                return

                            app.storage.user["user"] = safe_json(response).get("user", {})
                            ui.notify("Вход выполнен", type="positive")
                            ui.open("/dashboard")

                        ui.button("Войти", icon="login", on_click=login).classes("w-full bg-blue-700 text-white")

                    with ui.tab_panel(register_tab):
                        with ui.grid(columns=2).classes("w-full gap-3"):
                            reg_name = ui.input("Имя").classes("w-full")
                            reg_email = ui.input("Email").classes("w-full")
                            reg_phone = ui.input("Телефон").classes("w-full")
                            reg_password = ui.input("Пароль", password=True, password_toggle_button=True).classes(
                                "w-full"
                            )
                            reg_role = ui.select(
                                {"reader": "Читатель", "author": "Автор"},
                                value="reader",
                                label="Роль",
                            ).classes("w-full")
                            reg_card = ui.input("Читательский билет LIB-XXXXXX").classes("w-full")

                        register_message = ui.label("").classes("text-red-600")

                        async def register():
                            register_message.text = ""
                            payload = {
                                "name": (reg_name.value or "").strip(),
                                "email": (reg_email.value or "").strip(),
                                "phone_number": (reg_phone.value or "").strip(),
                                "password": (reg_password.value or "").strip(),
                                "role": reg_role.value,
                            }
                            card = (reg_card.value or "").strip()
                            if card and payload["role"] == "reader":
                                payload["library_card"] = card

                            response = await api_post("/api/auth/register", payload)
                            if response.status_code != 200:
                                register_message.text = detail_from(response, "Не удалось зарегистрироваться.")
                                return

                            ui.notify("Аккаунт создан. Теперь войди.", type="positive")
                            tabs.value = login_tab

                        ui.button("Создать аккаунт", icon="person_add", on_click=register).classes(
                            "w-full bg-teal-700 text-white"
                        )


@ui.page("/dashboard")
def reader_dashboard():
    user = require_login()
    if not user:
        return

    with page_shell("Личный кабинет"):
        with ui.row().classes("w-full gap-4"):
            metric("Роль", ROLE_LABELS.get(user.get("role"), user.get("role")), "text-blue-700")
            metric("Читательский билет", user.get("library_card") or "Генерируется", "text-teal-700")
            metric("ID", user.get("id", "")[:8], "text-amber-700")

        with ui.tabs().classes("w-full") as tabs:
            catalog_tab = ui.tab("Каталог", icon="menu_book")
            current_tab = ui.tab("Мои книги", icon="bookmark_added")
            history_tab = ui.tab("История", icon="history")
            bookmarks_tab = ui.tab("Закладки", icon="bookmark")

        with ui.tab_panels(tabs, value=catalog_tab).classes("w-full"):
            with ui.tab_panel(catalog_tab):
                with ui.row().classes("w-full items-end gap-3"):
                    search_input = ui.input("Название, автор или жанр").props("clearable").classes("flex-1")
                    genre_input = ui.input("Жанр").props("clearable").classes("w-64")
                    ui.button(
                        "Найти",
                        icon="search",
                        on_click=lambda: ui.timer(0.1, load_catalog, once=True),
                    ).classes("bg-blue-700 text-white")

                catalog_container = ui.column().classes("w-full gap-3 mt-4")

                async def load_catalog():
                    catalog_container.clear()
                    params = {
                        "q": (search_input.value or "").strip() or None,
                        "genre": (genre_input.value or "").strip() or None,
                    }
                    response = await api_get("/api/books/catalog", params=params)
                    if response.status_code != 200:
                        with catalog_container:
                            ui.label(detail_from(response, "Каталог не загрузился.")).classes("text-red-600")
                        return

                    books = safe_json(response)
                    with catalog_container:
                        if not books:
                            ui.label("Книг пока нет.").classes("text-slate-500")
                            return

                        for book in books:
                            with ui.card().classes("w-full p-4 rounded-lg border border-slate-200 shadow-sm"):
                                with ui.row().classes("w-full items-start justify-between gap-3"):
                                    with ui.column().classes("gap-1 flex-1"):
                                        book_summary(book)

                                    async def borrow(book_id=book["id"]):
                                        response = await api_post(f"/api/books/{book_id}/borrow", {"user_id": user["id"]})
                                        if response.status_code == 200:
                                            ui.notify("Книга добавлена в чтение на 14 дней", type="positive")
                                            await load_current()
                                            tabs.value = current_tab
                                        else:
                                            ui.notify(detail_from(response, "Не удалось взять книгу"), type="negative")

                                    ui.button("Взять", icon="add_task", on_click=borrow).classes(
                                        "bg-teal-700 text-white"
                                    )

                async def run_search():
                    await load_catalog()

                search_input.on("keydown.enter", lambda e: ui.timer(0.1, run_search, once=True))
                genre_input.on("keydown.enter", lambda e: ui.timer(0.1, run_search, once=True))
                ui.button("Обновить каталог", icon="refresh", on_click=load_catalog).classes("mt-2")
                ui.timer(0.2, load_catalog, once=True)

            with ui.tab_panel(current_tab):
                current_container = ui.column().classes("w-full gap-3")

                async def load_current():
                    current_container.clear()
                    response = await api_get(f"/api/books/users/{user['id']}/loans/current")
                    if response.status_code != 200:
                        with current_container:
                            ui.label(detail_from(response, "Не удалось загрузить текущие книги.")).classes(
                                "text-red-600"
                            )
                        return

                    loans = safe_json(response)
                    with current_container:
                        if not loans:
                            ui.label("Сейчас нет взятых книг.").classes("text-slate-500")
                            return

                        for loan in loans:
                            with ui.card().classes("w-full p-4 rounded-lg border border-slate-200 shadow-sm"):
                                with ui.row().classes("w-full items-start justify-between gap-3"):
                                    with ui.column().classes("gap-1 flex-1"):
                                        ui.label(loan.get("title")).classes("text-lg font-bold")
                                        ui.label(f"Вернуть до: {loan.get('due_at')}").classes("text-sm text-slate-500")
                                        ui.label(loan.get("description") or "Описание пока не добавлено.").classes(
                                            "text-sm text-slate-700"
                                        )

                                    with ui.row().classes("gap-2"):
                                        read_url = (
                                            f"{BROWSER_API_BASE}/api/books/{loan['book_id']}/read"
                                            f"?user_id={quote(user['id'])}"
                                        )
                                        ui.button("Читать", icon="chrome_reader_mode", on_click=lambda url=read_url: ui.open(url)).classes(
                                            "bg-blue-700 text-white"
                                        )

                                        async def add_bookmark(book_id=loan["book_id"]):
                                            response = await api_post(
                                                f"/api/books/{book_id}/bookmarks",
                                                {
                                                    "user_id": user["id"],
                                                    "position_label": "Демо-закладка",
                                                    "progress_percent": 0,
                                                },
                                            )
                                            if response.status_code == 200:
                                                ui.notify("Закладка сохранена", type="positive")
                                                await load_bookmarks()
                                            else:
                                                ui.notify(detail_from(response, "Не удалось сохранить закладку"), type="negative")

                                        ui.button(icon="bookmark_add", on_click=add_bookmark).props("round").classes(
                                            "bg-amber-700 text-white"
                                        )

                                        async def return_book(book_id=loan["book_id"]):
                                            response = await api_post(
                                                f"/api/books/{book_id}/return",
                                                {"user_id": user["id"]},
                                            )
                                            if response.status_code == 200:
                                                ui.notify("Книга возвращена", type="positive")
                                                await load_current()
                                                await load_history()
                                            else:
                                                ui.notify(detail_from(response, "Не удалось вернуть книгу"), type="negative")

                                        ui.button("Вернуть", icon="assignment_return", on_click=return_book).classes(
                                            "bg-slate-700 text-white"
                                        )

                ui.button("Обновить", icon="refresh", on_click=load_current).classes("mb-3")
                ui.timer(0.3, load_current, once=True)

            with ui.tab_panel(history_tab):
                history_container = ui.column().classes("w-full gap-3")

                async def load_history():
                    history_container.clear()
                    response = await api_get(f"/api/books/users/{user['id']}/loans/history")
                    if response.status_code != 200:
                        with history_container:
                            ui.label(detail_from(response, "Не удалось загрузить историю.")).classes("text-red-600")
                        return

                    loans = safe_json(response)
                    with history_container:
                        if not loans:
                            ui.label("История пока пустая.").classes("text-slate-500")
                            return
                        for loan in loans:
                            with ui.card().classes("w-full p-4 rounded-lg border border-slate-200 shadow-sm"):
                                ui.label(loan.get("title")).classes("text-lg font-bold")
                                ui.label(
                                    f"Взята: {loan.get('borrowed_at')} · Возврат: {loan.get('returned_at') or loan.get('due_at')}"
                                ).classes("text-sm text-slate-500")

                ui.button("Обновить историю", icon="refresh", on_click=load_history).classes("mb-3")
                ui.timer(0.4, load_history, once=True)

            with ui.tab_panel(bookmarks_tab):
                bookmark_container = ui.column().classes("w-full gap-3")

                async def load_bookmarks():
                    bookmark_container.clear()
                    response = await api_get(f"/api/books/users/{user['id']}/bookmarks")
                    if response.status_code != 200:
                        with bookmark_container:
                            ui.label(detail_from(response, "Не удалось загрузить закладки.")).classes("text-red-600")
                        return

                    bookmarks = safe_json(response)
                    with bookmark_container:
                        if not bookmarks:
                            ui.label("Закладок пока нет.").classes("text-slate-500")
                            return
                        for bookmark in bookmarks:
                            with ui.card().classes("w-full p-4 rounded-lg border border-slate-200 shadow-sm"):
                                with ui.row().classes("w-full items-center justify-between gap-3"):
                                    with ui.column().classes("gap-1"):
                                        ui.label(bookmark.get("title")).classes("text-lg font-bold")
                                        ui.label(
                                            f"Страница: {bookmark.get('page_number') or 'не указана'} · "
                                            f"Прогресс: {bookmark.get('progress_percent') or 0}%"
                                        ).classes("text-sm text-slate-500")
                                        ui.label(bookmark.get("note") or bookmark.get("position_label") or "").classes(
                                            "text-sm text-slate-700"
                                        )

                                    async def delete(bookmark_id=bookmark["id"]):
                                        response = await api_delete(
                                            f"/api/books/bookmarks/{bookmark_id}",
                                            params={"user_id": user["id"]},
                                        )
                                        if response.status_code == 200:
                                            ui.notify("Закладка удалена", type="positive")
                                            await load_bookmarks()
                                        else:
                                            ui.notify(detail_from(response, "Не удалось удалить закладку"), type="negative")

                                    ui.button(icon="delete", on_click=delete).props("round").classes("bg-red-600 text-white")

                ui.button("Обновить закладки", icon="refresh", on_click=load_bookmarks).classes("mb-3")
                ui.timer(0.5, load_bookmarks, once=True)


@ui.page("/author")
def author_page():
    user = require_login()
    if not user:
        return
    if user.get("role") != "author":
        ui.open("/dashboard")
        return

    with page_shell("Кабинет автора", "author"):
        with ui.row().classes("w-full gap-4 items-start"):
            with ui.card().classes("w-full lg:w-5/12 p-4 rounded-lg border border-slate-200 shadow-sm"):
                ui.label("Новая книга").classes("text-xl font-bold")
                title_input = ui.input("Название").classes("w-full")
                genre_input = ui.input("Жанр").classes("w-full")
                access_select = ui.select(ACCESS_LABELS, value="free", label="Условия доступа").classes("w-full")
                copyright_input = ui.input("Правообладатель").classes("w-full")
                license_input = ui.input("Лицензия").classes("w-full")
                description_input = ui.textarea("Описание").classes("w-full")

                uploaded_file = {"path": None, "name": None}

                def on_upload(event):
                    temp_path = os.path.join(tempfile.gettempdir(), event.name)
                    with open(temp_path, "wb") as file:
                        file.write(event.content.read())
                    uploaded_file["path"] = temp_path
                    uploaded_file["name"] = event.name
                    ui.notify(f"Файл выбран: {event.name}", type="positive")

                ui.upload(label="PDF или EPUB", on_upload=on_upload, auto_upload=True).props("accept=.pdf,.epub").classes(
                    "w-full"
                )

                async def upload_book():
                    if not title_input.value or not uploaded_file["path"]:
                        ui.notify("Укажи название и выбери файл", type="negative")
                        return
                    async with httpx.AsyncClient(timeout=120.0) as client:
                        with open(uploaded_file["path"], "rb") as file:
                            response = await client.post(
                                f"{API_BASE}/api/books/author/upload",
                                data={
                                    "title": title_input.value.strip(),
                                    "description": description_input.value or "",
                                    "genre": genre_input.value or "",
                                    "access_level": access_select.value,
                                    "copyright_holder": copyright_input.value or "",
                                    "license_name": license_input.value or "",
                                    "author_user_id": user["id"],
                                    "uploaded_by_user_id": user["id"],
                                },
                                files={"book_file": (uploaded_file["name"], file, "application/octet-stream")},
                            )
                    if response.status_code == 200:
                        ui.notify("Книга отправлена на модерацию", type="positive")
                        title_input.value = ""
                        genre_input.value = ""
                        description_input.value = ""
                        uploaded_file["path"] = None
                        uploaded_file["name"] = None
                        await load_author_books()
                    else:
                        ui.notify(detail_from(response, "Не удалось загрузить книгу"), type="negative")

                ui.button("Отправить", icon="upload_file", on_click=upload_book).classes("w-full bg-teal-700 text-white")

            author_books = ui.column().classes("w-full lg:w-7/12 gap-3")

        async def load_author_books():
            author_books.clear()
            response = await api_get(f"/api/books/author/{user['id']}")
            books = safe_json(response) if response.status_code == 200 else []
            with author_books:
                ui.label("Мои публикации").classes("text-xl font-bold")
                if not books:
                    ui.label("Загруженных книг пока нет.").classes("text-slate-500")
                    return
                for book in books:
                    with ui.card().classes("w-full p-4 rounded-lg border border-slate-200 shadow-sm"):
                        ui.label(book.get("title")).classes("text-lg font-bold")
                        ui.badge(STATUS_LABELS.get(book.get("status"), book.get("status"))).classes("bg-blue-700")
                        ui.label(f"Файл: {book.get('original_filename') or 'не прикреплен'}").classes("text-sm text-slate-500")
                        ui.label(book.get("moderator_comment") or "").classes("text-sm text-red-700")

        ui.timer(0.2, load_author_books, once=True)


@ui.page("/moderator")
def moderator_page():
    user = require_login()
    if not user:
        return
    if user.get("role") not in ("moderator", "admin"):
        ui.open("/dashboard")
        return

    with page_shell("Модерация книг", "moderator"):
        with ui.tabs().classes("w-full") as tabs:
            queue_tab = ui.tab("Очередь", icon="rule")
            upload_tab = ui.tab("Добавить книгу", icon="upload_file")

        with ui.tab_panels(tabs, value=queue_tab).classes("w-full"):
            with ui.tab_panel(queue_tab):
                queue_container = ui.column().classes("w-full gap-3")

                async def load_queue():
                    queue_container.clear()
                    response = await api_get("/api/books/moderation/queue")
                    rows = safe_json(response) if response.status_code == 200 else []
                    with queue_container:
                        if not rows:
                            ui.label("Очередь модерации пустая.").classes("text-slate-500")
                            return
                        for book in rows:
                            with ui.card().classes("w-full p-4 rounded-lg border border-slate-200 shadow-sm"):
                                ui.label(book.get("title")).classes("text-lg font-bold")
                                ui.label(f"Автор: {book.get('author_name') or 'не указан'} · Файл: {book.get('original_filename') or 'нет'}").classes(
                                    "text-sm text-slate-500"
                                )
                                ui.label(book.get("description") or "").classes("text-sm text-slate-700")
                                comment_input = ui.input("Комментарий").classes("w-full")

                                with ui.row().classes("gap-2"):
                                    async def decide(status: str, book_id=book["id"], comment_input=comment_input):
                                        response = await api_post(
                                            f"/api/books/{book_id}/moderation",
                                            {
                                                "status": status,
                                                "moderator_comment": comment_input.value or "",
                                                "changed_by_user_id": user["id"],
                                            },
                                        )
                                        if response.status_code == 200:
                                            ui.notify("Решение сохранено", type="positive")
                                            await load_queue()
                                        else:
                                            ui.notify(detail_from(response, "Не удалось сохранить решение"), type="negative")

                                    async def approve():
                                        await decide("published")

                                    async def reject():
                                        await decide("rejected")

                                    ui.button("Одобрить", icon="check", on_click=approve).classes(
                                        "bg-green-700 text-white"
                                    )
                                    ui.button("Отклонить", icon="close", on_click=reject).classes(
                                        "bg-red-700 text-white"
                                    )

                ui.button("Обновить очередь", icon="refresh", on_click=load_queue).classes("mb-3")
                ui.timer(0.2, load_queue, once=True)

            with ui.tab_panel(upload_tab):
                with ui.card().classes("w-full max-w-3xl p-4 rounded-lg border border-slate-200 shadow-sm"):
                    title_input = ui.input("Название").classes("w-full")
                    genre_input = ui.input("Жанр").classes("w-full")
                    access_select = ui.select(ACCESS_LABELS, value="free", label="Условия доступа").classes("w-full")
                    copyright_input = ui.input("Правообладатель").classes("w-full")
                    license_input = ui.input("Лицензия").classes("w-full")
                    description_input = ui.textarea("Описание").classes("w-full")
                    uploaded_file = {"path": None, "name": None}

                    def on_upload(event):
                        temp_path = os.path.join(tempfile.gettempdir(), event.name)
                        with open(temp_path, "wb") as file:
                            file.write(event.content.read())
                        uploaded_file["path"] = temp_path
                        uploaded_file["name"] = event.name
                        ui.notify(f"Файл выбран: {event.name}", type="positive")

                    ui.upload(label="PDF или EPUB", on_upload=on_upload, auto_upload=True).props("accept=.pdf,.epub").classes(
                        "w-full"
                    )

                    async def upload_direct():
                        if not title_input.value or not uploaded_file["path"]:
                            ui.notify("Укажи название и выбери файл", type="negative")
                            return
                        async with httpx.AsyncClient(timeout=120.0) as client:
                            with open(uploaded_file["path"], "rb") as file:
                                response = await client.post(
                                    f"{API_BASE}/api/books/moderator/upload",
                                    data={
                                        "title": title_input.value.strip(),
                                        "description": description_input.value or "",
                                        "genre": genre_input.value or "",
                                        "access_level": access_select.value,
                                        "copyright_holder": copyright_input.value or "",
                                        "license_name": license_input.value or "",
                                        "uploaded_by_user_id": user["id"],
                                    },
                                    files={"book_file": (uploaded_file["name"], file, "application/octet-stream")},
                                )
                        if response.status_code == 200:
                            ui.notify("Книга опубликована", type="positive")
                        else:
                            ui.notify(detail_from(response, "Не удалось опубликовать книгу"), type="negative")

                    ui.button("Опубликовать", icon="publish", on_click=upload_direct).classes(
                        "w-full bg-blue-700 text-white"
                    )


@ui.page("/admin")
def admin_page():
    user = require_login()
    if not user:
        return
    if user.get("role") != "admin":
        ui.open("/dashboard")
        return

    with page_shell("Администрирование", "admin"):
        stats_row = ui.row().classes("w-full gap-4")
        users_container = ui.column().classes("w-full gap-3")

        async def load_stats():
            stats_row.clear()
            response = await api_get("/api/books/admin/statistics", params={"admin_user_id": user["id"]})
            data = safe_json(response) if response.status_code == 200 else {}
            with stats_row:
                metric("Книг всего", data.get("books", {}).get("total", 0), "text-blue-700")
                metric("Опубликовано", data.get("books", {}).get("published", 0), "text-teal-700")
                metric("Активных выдач", data.get("loans", {}).get("active", 0), "text-amber-700")
                metric("Просрочено", data.get("loans", {}).get("overdue", 0), "text-red-700")

        search_input = ui.input("Поиск пользователя").props("clearable").classes("w-full max-w-xl")

        async def load_users():
            users_container.clear()
            response = await api_get("/api/admin/users/search", params={"q": search_input.value or ""})
            rows = safe_json(response) if response.status_code == 200 else []
            with users_container:
                if not rows:
                    ui.label("Пользователи не найдены.").classes("text-slate-500")
                    return
                for row in rows:
                    with ui.card().classes("w-full p-4 rounded-lg border border-slate-200 shadow-sm"):
                        with ui.row().classes("w-full items-center justify-between gap-3"):
                            with ui.column().classes("gap-0"):
                                ui.label(row.get("name")).classes("text-lg font-bold")
                                ui.label(row.get("email")).classes("text-sm text-slate-500")
                            role_select = ui.select(ROLE_LABELS, value=row.get("role"), label="Роль").classes("w-56")

                            async def save_role(target=row, role_select=role_select):
                                response = await api_post(
                                    f"/api/admin/users/{target['id']}/role",
                                    {
                                        "new_role": role_select.value,
                                        "target_email": target.get("email"),
                                        "admin_user_id": user["id"],
                                    },
                                )
                                if response.status_code == 200:
                                    ui.notify("Роль обновлена", type="positive")
                                else:
                                    ui.notify(detail_from(response, "Не удалось обновить роль"), type="negative")

                            ui.button("Сохранить", icon="save", on_click=save_role).classes("bg-blue-700 text-white")

        search_input.on("keydown.enter", lambda e: ui.timer(0.1, load_users, once=True))
        ui.button("Найти", icon="search", on_click=load_users).classes("bg-blue-700 text-white")
        ui.timer(0.2, load_stats, once=True)
        ui.timer(0.3, load_users, once=True)


ui.run(
    host="0.0.0.0",
    port=8080,
    title="Electronic Library",
    storage_secret="electronic-library-demo-secret",
)
