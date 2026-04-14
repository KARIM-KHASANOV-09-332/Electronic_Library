from nicegui import ui
import httpx
import os
import tempfile

API_BASE = 'http://backend:8000'


def safe_json(response):
    try:
        return response.json()
    except Exception:
        return {}


async def api_get(url: str):
    async with httpx.AsyncClient(timeout=60.0) as client:
        return await client.get(url)


async def api_post_json(url: str, payload: dict):
    async with httpx.AsyncClient(timeout=60.0) as client:
        return await client.post(url, json=payload)


async def api_put_json(url: str, payload: dict):
    async with httpx.AsyncClient(timeout=60.0) as client:
        return await client.put(url, json=payload)


@ui.page('/')
def index_page():
    current_user = {
        'id': None,
        'name': None,
        'role': None,
        'library_card': None,
    }

    with ui.column().classes('w-full items-center justify-center min-h-screen bg-gray-100'):
        with ui.row().classes('items-center mt-8 mb-8'):
            ui.label('📚').classes('text-5xl')
            ui.label('Электронная библиотека').classes('text-5xl font-bold text-blue-600 ml-4')

        with ui.card().classes('w-full max-w-2xl p-6 shadow-xl rounded-2xl') as auth_card:
            with ui.tabs().classes('w-full') as tabs:
                login_tab = ui.tab('ВХОД')
                register_tab = ui.tab('РЕГИСТРАЦИЯ')

            with ui.tab_panels(tabs, value=login_tab).classes('w-full'):
                with ui.tab_panel(login_tab):
                    login_input = ui.input('Email, Телефон или Билет').classes('w-full mt-8')
                    password_input = ui.input('Пароль', password=True, password_toggle_button=True).classes(
                        'w-full mt-8')
                    login_error = ui.label('').classes('text-red-500 text-lg mt-4')

                    async def try_login():
                        login_error.text = ''
                        login_value = (login_input.value or '').strip()
                        password_value = (password_input.value or '').strip()

                        if not login_value or not password_value:
                            login_error.text = 'Заполни логин и пароль'
                            return

                        payload = {
                            'login': login_value,
                            'password': password_value,
                        }

                        try:
                            res = await api_post_json(f'{API_BASE}/api/auth/login', payload)

                            if res.status_code != 200:
                                detail = safe_json(res).get('detail', 'Неверные данные для входа')
                                login_error.text = str(detail)
                                return

                            data = safe_json(res)
                            user = data.get('user', {})

                            current_user['id'] = user.get('id')
                            current_user['name'] = user.get('name')
                            current_user['role'] = user.get('role')
                            current_user['library_card'] = user.get('library_card')

                            if user.get('role') == 'admin':
                                ui.open('/admin')
                                return

                            if user.get('role') == 'moderator':
                                ui.open('/moderator')
                                return

                            show_profile(
                                user_id=user.get('id'),
                                user_name=user.get('name'),
                                role=user.get('role'),
                                existing_card=user.get('library_card'),
                            )
                        except Exception as e:
                            login_error.text = f'Ошибка соединения: {e}'

                    ui.button('ВОЙТИ', on_click=try_login).classes('w-full mt-8 bg-blue-500 text-white text-xl')

                with ui.tab_panel(register_tab):
                    register_name = ui.input('Имя').classes('w-full mt-4')
                    register_email = ui.input('Email').classes('w-full mt-4')
                    register_phone = ui.input('Телефон').classes('w-full mt-4')
                    register_password = ui.input('Пароль', password=True, password_toggle_button=True).classes(
                        'w-full mt-4')
                    register_role = ui.select(
                        {
                            'reader': 'Читатель',
                            'author': 'Писатель',
                        },
                        value='reader',
                        label='Роль'
                    ).classes('w-full mt-4')
                    register_error = ui.label('').classes('text-red-500 text-lg mt-4')

                    async def try_register():
                        register_error.text = ''

                        payload = {
                            'name': (register_name.value or '').strip(),
                            'email': (register_email.value or '').strip(),
                            'phone_number': (register_phone.value or '').strip(),
                            'password': (register_password.value or '').strip(),
                            'role': register_role.value,
                        }

                        if not payload['name'] or not payload['email'] or not payload['password']:
                            register_error.text = 'Имя, email и пароль обязательны'
                            return

                        try:
                            res = await api_post_json(f'{API_BASE}/api/auth/register', payload)

                            if res.status_code != 200:
                                detail = safe_json(res).get('detail', 'Ошибка регистрации')
                                register_error.text = str(detail)
                                return

                            ui.notify('Регистрация успешна. Теперь войди в аккаунт.', type='positive')
                            register_name.value = ''
                            register_email.value = ''
                            register_phone.value = ''
                            register_password.value = ''
                            register_role.value = 'reader'
                        except Exception as e:
                            register_error.text = f'Ошибка соединения: {e}'

                    ui.button('ЗАРЕГИСТРИРОВАТЬСЯ', on_click=try_register).classes(
                        'w-full mt-8 bg-blue-500 text-white text-xl')

        with ui.card().classes('w-full max-w-xl p-8 shadow-xl rounded-2xl items-center') as profile_card:
            profile_card.style('display: none;')

            ui.label('👤').classes('text-6xl text-purple-700')
            name_display = ui.label('').classes('text-4xl font-bold mt-4')
            id_display = ui.label('').classes('text-gray-500 mt-2')
            ui.separator().classes('w-full my-6')
            card_title = ui.label('').classes('text-2xl text-gray-700')
            card_display = ui.label('').classes('text-2xl rounded-lg px-6 py-3 mt-4')

            def open_author_cabinet():
                if current_user['id']:
                    ui.open(f"/author/{current_user['id']}")

            author_cabinet_button = ui.button(
                'Перейти в кабинет автора',
                on_click=open_author_cabinet
            ).classes('bg-purple-600 text-white mt-4')
            author_cabinet_button.style('display: none;')

            def logout():
                current_user['id'] = None
                current_user['name'] = None
                current_user['role'] = None
                current_user['library_card'] = None
                profile_card.style('display: none;')
                auth_card.style('display: block;')
                login_input.value = ''
                password_input.value = ''
                login_error.text = ''

            ui.button('Выйти', on_click=logout).classes('bg-red-500 text-white mt-6')

        def show_profile(user_id, user_name, role, existing_card=None):
            current_user['id'] = user_id
            current_user['name'] = user_name
            current_user['role'] = role
            current_user['library_card'] = existing_card

            name_display.text = user_name or 'Пользователь'
            id_display.text = f'ID: {user_id or "—"}'
            auth_card.style('display: none;')
            profile_card.style('display: flex;')
            author_cabinet_button.style('display: none;')

            if role == 'author':
                card_title.text = 'Ваш статус:'
                card_display.text = 'Писатель 🖋️'
                card_display.classes(
                    remove='bg-blue-100 text-blue-800 bg-green-100 text-green-800 bg-gray-100 text-gray-800',
                    add='bg-purple-100 text-purple-800'
                )
                author_cabinet_button.style('display: inline-flex;')
                return

            if role == 'reader':
                card_title.text = 'Ваш читательский билет:'
                card_display.text = existing_card or 'Билет еще не сгенерирован'
                card_display.classes(
                    remove='bg-green-100 text-green-800 bg-purple-100 text-purple-800 bg-gray-100 text-gray-800',
                    add='bg-blue-100 text-blue-800'
                )
                return

            card_title.text = 'Ваш статус:'
            card_display.text = role or '—'
            card_display.classes(
                remove='bg-blue-100 text-blue-800 bg-green-100 text-green-800 bg-purple-100 text-purple-800',
                add='bg-gray-100 text-gray-800'
            )


@ui.page('/admin')
def admin_page():
    with ui.column().classes('w-full max-w-6xl mx-auto p-8'):
        with ui.row().classes('w-full items-center justify-between mb-6'):
            ui.label('Панель Администратора').classes('text-4xl font-bold text-gray-800')
            ui.button('Выйти', on_click=lambda: ui.open('/')).classes('bg-blue-500 text-white')

        ui.label('Управление правами доступа').classes('text-2xl font-semibold mt-6 mb-6')

        users_container = ui.column().classes('w-full gap-4')
        search_input = ui.input('Начните вводить имя или email...').classes('w-full mt-6')

        async def load_users(query: str = ''):
            users_container.clear()
            try:
                res = await api_get(f'{API_BASE}/api/admin/users/search?query={query}')
                if res.status_code != 200:
                    with users_container:
                        ui.label('Не удалось загрузить пользователей').classes('text-red-500')
                    return

                users = safe_json(res)
                if not users:
                    with users_container:
                        ui.label('Пользователи не найдены').classes('text-gray-500')
                    return

                for user in users:
                    with users_container:
                        with ui.card().classes('w-full p-4 shadow'):
                            with ui.row().classes('w-full items-center justify-between'):
                                with ui.column():
                                    ui.label(user.get('name', 'Без имени')).classes('text-2xl font-bold')
                                    ui.label(user.get('email', '—')).classes('text-gray-600')

                                role_select = ui.select(
                                    {
                                        'reader': 'Читатель',
                                        'author': 'Писатель',
                                        'moderator': 'Модератор',
                                        'admin': 'Администратор',
                                    },
                                    value=user.get('role', 'reader'),
                                    label='Роль'
                                ).classes('w-56')

                                async def save_role(user_id=user.get('id'), role_select=role_select):
                                    payload = {'role': role_select.value}
                                    res_update = await api_put_json(
                                        f'{API_BASE}/api/admin/users/{user_id}/role',
                                        payload
                                    )
                                    if res_update.status_code == 200:
                                        ui.notify('Роль обновлена', type='positive')
                                    else:
                                        detail = safe_json(res_update).get('detail', 'Не удалось обновить роль')
                                        ui.notify(str(detail), type='negative')

                                ui.button('СОХРАНИТЬ', on_click=save_role).classes('bg-blue-500 text-white')

            except Exception as e:
                with users_container:
                    ui.label(f'Ошибка соединения: {e}').classes('text-red-500')

        async def on_search():
            await load_users((search_input.value or '').strip())

        search_input.on('update:model-value', lambda e: ui.timer(0.1, on_search, once=True))
        ui.timer(0.2, load_users, once=True)


@ui.page('/moderator')
def moderator_page():
    with ui.column().classes('w-full max-w-5xl mx-auto p-8'):
        with ui.row().classes('w-full items-center justify-between mb-6'):
            ui.label('Панель модератора').classes('text-3xl font-bold text-gray-800')
            ui.button('Выйти', on_click=lambda: ui.open('/')).classes('bg-red-500 text-white')

        ui.label('Добавление книги напрямую в каталог').classes('text-xl font-semibold mb-2')

        title_input = ui.input('Название книги').classes('w-full mb-2')
        genre_input = ui.input('Жанр').classes('w-full mb-2')
        access_select = ui.select(
            {
                'free': 'Свободный доступ',
                'licensed': 'По лицензии',
                'subscription': 'По подписке',
            },
            value='free',
            label='Условие доступа'
        ).classes('w-full mb-2')

        copyright_input = ui.input('Правообладатель').classes('w-full mb-2')
        license_input = ui.input('Лицензия').classes('w-full mb-2')
        description_input = ui.textarea('Описание').classes('w-full mb-4')

        books_container = ui.column().classes('w-full gap-2 mt-8')

        async def load_published_books():
            books_container.clear()
            try:
                res = await api_get(f'{API_BASE}/api/books/published')
                if res.status_code != 200:
                    with books_container:
                        ui.label('Не удалось загрузить список книг').classes('text-red-500')
                    return

                books = safe_json(res)

                with books_container:
                    ui.label('Опубликованные книги').classes('text-xl font-semibold mb-2')

                    if not books:
                        ui.label('Пока книг нет').classes('text-gray-500')
                        return

                    for book in books:
                        with ui.card().classes('w-full p-4'):
                            ui.label(book.get('title', 'Без названия')).classes('text-lg font-bold')
                            ui.label(f"Жанр: {book.get('genre') or '—'}").classes('text-sm')
                            ui.label(f"Доступ: {book.get('access_level') or '—'}").classes('text-sm')
                            ui.label(f"Лицензия: {book.get('license_name') or '—'}").classes('text-sm')
                            ui.label(f"Правообладатель: {book.get('copyright_holder') or '—'}").classes('text-sm')
                            ui.label(book.get('description') or 'Без описания').classes('text-sm text-gray-700')

            except Exception as e:
                with books_container:
                    ui.label(f'Ошибка соединения: {e}').classes('text-red-500')

        async def create_book():
            if not title_input.value or not title_input.value.strip():
                ui.notify('Введите название книги', type='negative')
                return

            payload = {
                'title': title_input.value.strip(),
                'description': description_input.value.strip() if description_input.value else '',
                'genre': genre_input.value.strip() if genre_input.value else None,
                'access_level': access_select.value,
                'copyright_holder': copyright_input.value.strip() if copyright_input.value else None,
                'license_name': license_input.value.strip() if license_input.value else None,
                'uploaded_by_user_id': None,
                'author_user_id': None,
            }

            try:
                res = await api_post_json(f'{API_BASE}/api/books/moderator/direct', payload)
                if res.status_code == 200:
                    ui.notify('Книга успешно добавлена', type='positive')
                    title_input.value = ''
                    genre_input.value = ''
                    description_input.value = ''
                    copyright_input.value = ''
                    license_input.value = ''
                    access_select.value = 'free'
                    await load_published_books()
                else:
                    detail = safe_json(res).get('detail', 'Ошибка добавления книги')
                    ui.notify(str(detail), type='negative')
            except Exception as e:
                ui.notify(f'Сервер недоступен: {e}', type='negative')

        ui.button('ДОБАВИТЬ КНИГУ', on_click=create_book).classes('w-full bg-blue-500 text-white text-xl')
        ui.separator().classes('w-full my-6')
        ui.timer(0.2, load_published_books, once=True)


@ui.page('/author/{author_user_id}')
def author_page(author_user_id: str):
    with ui.column().classes('w-full max-w-5xl mx-auto p-8'):
        with ui.row().classes('w-full items-center justify-between mb-6'):
            ui.label('Кабинет автора').classes('text-3xl font-bold text-gray-800')
            ui.button('Выйти', on_click=lambda: ui.open('/')).classes('bg-red-500 text-white')

        ui.label('Загрузка книги в лист ожидания').classes('text-xl font-semibold mb-2')

        title_input = ui.input('Название книги').classes('w-full mb-2')
        genre_input = ui.input('Жанр').classes('w-full mb-2')

        access_select = ui.select(
            {
                'free': 'Свободный доступ',
                'licensed': 'По лицензии',
                'subscription': 'По подписке',
            },
            value='free',
            label='Условие доступа'
        ).classes('w-full mb-2')

        copyright_input = ui.input('Правообладатель').classes('w-full mb-2')
        license_input = ui.input('Лицензия').classes('w-full mb-2')
        description_input = ui.textarea('Описание').classes('w-full mb-4')

        uploaded_file_state = {'path': None, 'name': None}

        def on_upload(e):
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, e.name)

            with open(temp_path, 'wb') as f:
                f.write(e.content.read())

            uploaded_file_state['path'] = temp_path
            uploaded_file_state['name'] = e.name
            ui.notify(f'Файл выбран: {e.name}', type='positive')

        ui.upload(
            label='Загрузить PDF или EPUB',
            on_upload=on_upload,
            auto_upload=True
        ).props('accept=.pdf,.epub').classes('w-full mb-4')

        author_books_container = ui.column().classes('w-full gap-2 mt-8')

        async def load_author_books():
            author_books_container.clear()
            try:
                res = await api_get(f'{API_BASE}/api/books/author/{author_user_id}')
                if res.status_code != 200:
                    with author_books_container:
                        ui.label('Не удалось загрузить список книг автора').classes('text-red-500')
                    return

                books = safe_json(res)

                with author_books_container:
                    ui.label('Мои книги').classes('text-xl font-semibold mb-2')

                    if not books:
                        ui.label('У вас пока нет загруженных книг').classes('text-gray-500')
                        return

                    for book in books:
                        with ui.card().classes('w-full p-4'):
                            ui.label(book.get('title', 'Без названия')).classes('text-lg font-bold')
                            ui.label(f"Статус: {book.get('status') or '—'}").classes('text-sm')
                            ui.label(f"Жанр: {book.get('genre') or '—'}").classes('text-sm')
                            ui.label(f"Файл: {book.get('original_filename') or '—'}").classes('text-sm')
                            ui.label(f"Тип файла: {book.get('file_type') or '—'}").classes('text-sm')
                            ui.label(f"Доступ: {book.get('access_level') or '—'}").classes('text-sm')
                            ui.label(f"Лицензия: {book.get('license_name') or '—'}").classes('text-sm')
                            ui.label(f"Правообладатель: {book.get('copyright_holder') or '—'}").classes('text-sm')
                            ui.label(f"Комментарий модератора: {book.get('moderator_comment') or '—'}").classes('text-sm')
                            ui.label(book.get('description') or 'Без описания').classes('text-sm text-gray-700')

            except Exception as e:
                with author_books_container:
                    ui.label(f'Ошибка соединения: {e}').classes('text-red-500')

        async def upload_book():
            if not title_input.value or not title_input.value.strip():
                ui.notify('Введите название книги', type='negative')
                return

            if not uploaded_file_state['path'] or not uploaded_file_state['name']:
                ui.notify('Сначала выбери PDF или EPUB файл', type='negative')
                return

            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    with open(uploaded_file_state['path'], 'rb') as f:
                        files = {
                            'book_file': (uploaded_file_state['name'], f, 'application/octet-stream')
                        }
                        data = {
                            'title': title_input.value.strip(),
                            'description': description_input.value.strip() if description_input.value else '',
                            'genre': genre_input.value.strip() if genre_input.value else '',
                            'access_level': access_select.value,
                            'copyright_holder': copyright_input.value.strip() if copyright_input.value else '',
                            'license_name': license_input.value.strip() if license_input.value else '',
                            'author_user_id': author_user_id,
                            'uploaded_by_user_id': author_user_id,
                        }

                        res = await client.post(
                            f'{API_BASE}/api/books/author/upload',
                            data=data,
                            files=files
                        )

                if res.status_code == 200:
                    ui.notify('Книга отправлена на модерацию', type='positive')
                    title_input.value = ''
                    genre_input.value = ''
                    description_input.value = ''
                    copyright_input.value = ''
                    license_input.value = ''
                    access_select.value = 'free'
                    uploaded_file_state['path'] = None
                    uploaded_file_state['name'] = None
                    await load_author_books()
                else:
                    detail = safe_json(res).get('detail', f'Ошибка загрузки книги: {res.text}')
                    ui.notify(str(detail), type='negative')

            except Exception as e:
                ui.notify(f'Сервер недоступен: {e}', type='negative')

        ui.button('ОТПРАВИТЬ КНИГУ НА МОДЕРАЦИЮ', on_click=upload_book).classes('w-full bg-green-600 text-white text-xl')
        ui.separator().classes('w-full my-6')
        ui.button('ОБНОВИТЬ МОИ КНИГИ', on_click=load_author_books).classes('bg-blue-500 text-white')
        ui.separator().classes('w-full my-4')
        ui.timer(0.2, load_author_books, once=True)


ui.run(
    host='0.0.0.0',
    port=8080,
    title='Electronic Library',
)