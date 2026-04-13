from nicegui import ui
import httpx


@ui.page('/')
def index():
    with ui.column().classes('w-full items-center justify-center h-screen bg-gray-50'):
        ui.label('📚 Электронная библиотека').classes('text-4xl font-bold mb-8 text-blue-600')

        # --- КАРТОЧКА ПРОФИЛЯ ---
        profile_card = ui.card().classes('w-96 p-8 items-center shadow-lg').style('display: none;')
        with profile_card:
            ui.label('👤').classes('text-6xl mb-4')
            name_display = ui.label('Имя').classes('text-2xl font-bold')
            id_display = ui.label('ID').classes('text-xs text-gray-500 font-mono mb-4')
            ui.separator().classes('w-full mb-4')

            card_title = ui.label('Ваш читательский билет:').classes('text-gray-600')
            card_display = ui.label('Генерируется...').classes(
                'bg-blue-100 text-blue-800 px-4 py-2 rounded font-mono text-lg mt-2')

        # Функция показа профиля с учетом РОЛИ
        def show_profile(user_id, user_name, role, existing_card=None):
            name_display.text = user_name
            id_display.text = f"ID: {user_id}"
            auth_card.style('display: none;')
            profile_card.style('display: flex;')

            # Если это автор, билет не нужен вообще
            if role == 'author':
                card_title.text = 'Ваш статус:'
                card_display.text = 'Писатель 🖋️'
                card_display.classes(remove='bg-blue-100 text-blue-800 bg-green-100 text-green-800',
                                     add='bg-purple-100 text-purple-800')
                return  # Таймер не запускаем

            # Если это читатель и билет УЖЕ ЕСТЬ
            if existing_card:
                card_display.text = existing_card
                card_display.classes(remove='bg-blue-100 text-blue-800', add='bg-green-100 text-green-800')
                return

            # Если читатель ждет генерации
            card_display.text = 'Генерируется...'
            card_display.classes(remove='bg-green-100 text-green-800 bg-purple-100 text-purple-800',
                                 add='bg-blue-100 text-blue-800')

            async def check_card_status():
                try:
                    async with httpx.AsyncClient() as client:
                        res = await client.get(f"http://backend:8000/api/auth/profile/{user_id}")
                        if res.status_code == 200 and res.json().get("library_card"):
                            card_display.text = res.json().get("library_card")
                            card_display.classes(remove='bg-blue-100 text-blue-800', add='bg-green-100 text-green-800')
                            poll_timer.deactivate()
                except Exception:
                    pass

            poll_timer = ui.timer(2.0, check_card_status, active=True)

        # --- КАРТОЧКА АВТОРИЗАЦИИ И РЕГИСТРАЦИИ ---
        auth_card = ui.card().classes('w-96 p-2 shadow-lg')
        with auth_card:
            with ui.tabs().classes('w-full') as tabs:
                ui.tab('Вход')
                ui.tab('Регистрация')

            with ui.tab_panels(tabs, value='Вход').classes('w-full'):

                with ui.tab_panel('Вход'):
                    login_input = ui.input('Email, Телефон или Билет').classes('w-full mb-2')
                    login_pwd = ui.input('Пароль').props('type=password').classes('w-full mb-4')
                    login_err = ui.label('').classes('text-red-500 text-sm font-bold w-full text-center mb-2')

                    async def try_login():
                        login_err.text = ''
                        try:
                            async with httpx.AsyncClient() as client:
                                res = await client.post("http://backend:8000/api/auth/login", json={
                                    "login": login_input.value, "password": login_pwd.value
                                })
                                if res.status_code == 200:
                                    data = res.json().get("user", {})
                                    if data["role"] == "admin":
                                        ui.open('/admin')  # <-- ИСПРАВЛЕНО
                                    else:
                                        show_profile(data.get("id"), data.get("name"), data.get("role"), data.get("library_card"))
                                else:
                                    login_err.text = res.json().get("detail", "Ошибка входа")
                        except Exception as e:
                            # Теперь мы увидим реальную ошибку питона прямо на кнопке!
                            login_err.text = f"Системная ошибка: {repr(e)}"
                            print(f"[ОШИБКА ФРОНТЕНДА]: {repr(e)}")

                    ui.button('Войти', on_click=try_login).classes('w-full bg-blue-600')

                with ui.tab_panel('Регистрация'):
                    # НОВОЕ: Переключатель ролей
                    reg_role = ui.toggle({'reader': 'Читатель', 'author': 'Автор'}, value='reader').classes(
                        'w-full mb-4 justify-center')

                    reg_name = ui.input('Имя').classes('w-full mb-2')
                    reg_email = ui.input('Email').classes('w-full mb-2')
                    reg_phone = ui.input('Телефон').classes('w-full mb-2')

                    # Прячем поле билета, если выбран Автор
                    reg_card = ui.input('Номер билета (если есть)').classes('w-full mb-2').bind_visibility_from(
                        reg_role, 'value', value=lambda v: v == 'reader')

                    reg_pwd = ui.input('Пароль').props('type=password').classes('w-full mb-4')
                    reg_err = ui.label('').classes('text-red-500 text-sm font-bold w-full text-center mb-2')

                    async def try_register():
                        reg_err.text = ''
                        payload = {
                            "name": reg_name.value,
                            "email": reg_email.value,
                            "phone_number": reg_phone.value,
                            "password": reg_pwd.value,
                            "role": reg_role.value,  # Передаем выбранную роль
                            "library_card": reg_card.value.strip() if reg_card.value.strip() and reg_role.value == 'reader' else None
                        }
                        try:
                            async with httpx.AsyncClient() as client:
                                res = await client.post("http://backend:8000/api/auth/register", json=payload)
                                if res.status_code == 200:
                                    data = res.json()["user"]
                                    show_profile(data["id"], data["name"], data["role"], data.get("library_card"))
                                else:
                                    detail = res.json().get("detail", "Ошибка")
                                    reg_err.text = detail[0]["msg"] if isinstance(detail, list) else str(detail)
                        except Exception:
                            reg_err.text = "Сервер недоступен"

                    ui.button('Зарегистрироваться', on_click=try_register).classes('w-full bg-green-600')


@ui.page('/admin')
def admin_page():
    with ui.column().classes('w-full max-w-3xl mx-auto p-8'):
        with ui.row().classes('w-full items-center justify-between mb-8'):
            ui.label('Панель Администратора').classes('text-3xl font-bold text-gray-800')
            ui.button('Выйти', on_click=lambda: ui.open('/')).classes('bg-red-500 text-white')

        ui.label('Управление правами доступа').classes('text-xl font-semibold mb-2')

        # Контейнер для результатов поиска
        results_container = ui.column().classes('w-full gap-2 mt-4')

        async def perform_search(e):
            query = e.value.strip()
            results_container.clear()  # Очищаем старые результаты

            if len(query) < 2: return

            try:
                async with httpx.AsyncClient() as client:
                    res = await client.get(f"http://backend:8000/api/admin/users/search?q={query}")
                    if res.status_code == 200:
                        users = res.json()
                        if not users:
                            with results_container:
                                ui.label('Пользователи не найдены').classes('text-gray-500')
                            return

                        # Рисуем карточку для каждого найденного пользователя
                        with results_container:
                            for u in users:
                                with ui.card().classes('w-full flex-row items-center justify-between p-4'):
                                    with ui.column():
                                        ui.label(u['name']).classes('font-bold text-lg')
                                        ui.label(u['email']).classes('text-sm text-gray-500')

                                    with ui.row().classes('items-center gap-4'):
                                        # Выпадающий список ролей
                                        roles = {'reader': 'Читатель', 'author': 'Автор', 'moderator': 'Модератор',
                                                 'admin': 'Админ'}
                                        role_select = ui.select(roles, value=u['role']).classes('w-32')

                                        # Кнопка сохранения
                                        ui.button('Сохранить', on_click=lambda user_id=u['id'], email=u['email'],
                                                                               rs=role_select: update_role(user_id,
                                                                                                           email,
                                                                                                           rs.value)).classes(
                                            'bg-blue-500')

            except Exception as err:
                ui.notify(f'Ошибка соединения: {err}', type='negative')

        async def update_role(user_id, email, new_role):
            try:
                payload = {"new_role": new_role, "target_email": email}
                async with httpx.AsyncClient() as client:
                    res = await client.post(f"http://backend:8000/api/admin/users/{user_id}/role", json=payload)
                    if res.status_code == 200:
                        ui.notify(f'Права для {email} изменены на {new_role}', type='positive')
                    else:
                        ui.notify('Ошибка при обновлении', type='negative')
            except Exception:
                ui.notify('Сервер недоступен', type='negative')

        # Инпут для динамического поиска
        ui.input('Начните вводить имя или email...', on_change=perform_search).classes('w-full text-lg')

ui.run(host='0.0.0.0', port=8080, title='Электронная библиотека', show=False)