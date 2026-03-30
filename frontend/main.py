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
            ui.label('Ваш читательский билет:').classes('text-gray-600')
            card_display = ui.label('Генерируется...').classes(
                'bg-blue-100 text-blue-800 px-4 py-2 rounded font-mono text-lg mt-2')

        # Функция показа профиля с проверкой наличия билета
        def show_profile(user_id, user_name, existing_card=None):
            name_display.text = user_name
            id_display.text = f"ID: {user_id}"
            auth_card.style('display: none;')
            profile_card.style('display: flex;')

            # Если билет УЖЕ ЕСТЬ (ввели при регистрации или вошли в систему), показываем сразу
            if existing_card:
                card_display.text = existing_card
                card_display.classes(remove='bg-blue-100 text-blue-800', add='bg-green-100 text-green-800')
                return  # Выходим, таймер не нужен!

            # Иначе включаем таймер ожидания воркера
            card_display.text = 'Генерируется...'
            card_display.classes(remove='bg-green-100 text-green-800', add='bg-blue-100 text-blue-800')

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

                # ВКЛАДКА ЛОГИНА
                with ui.tab_panel('Вход'):
                    # Обновили текст-подсказку
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
                                    data = res.json()["user"]
                                    # Передаем существующий билет в профиль
                                    show_profile(data["id"], data["name"], data.get("library_card"))
                                else:
                                    login_err.text = res.json().get("detail", "Ошибка входа")
                        except Exception as e:
                            login_err.text = "Сервер недоступен"

                    ui.button('Войти', on_click=try_login).classes('w-full bg-blue-600')

                # ВКЛАДКА РЕГИСТРАЦИИ
                with ui.tab_panel('Регистрация'):
                    reg_name = ui.input('Имя').classes('w-full mb-2')
                    reg_email = ui.input('Email').classes('w-full mb-2')
                    reg_phone = ui.input('Телефон').classes('w-full mb-2')
                    # НОВОЕ ПОЛЕ
                    reg_card = ui.input('Номер билета (если есть)').classes('w-full mb-2')
                    reg_pwd = ui.input('Пароль').props('type=password').classes('w-full mb-4')
                    reg_err = ui.label('').classes('text-red-500 text-sm font-bold w-full text-center mb-2')

                    async def try_register():
                        reg_err.text = ''
                        payload = {
                            "name": reg_name.value,
                            "email": reg_email.value,
                            "phone_number": reg_phone.value,
                            "password": reg_pwd.value,
                            # Передаем билет, если поле не пустое
                            "library_card": reg_card.value.strip() if reg_card.value.strip() else None
                        }
                        try:
                            async with httpx.AsyncClient() as client:
                                res = await client.post("http://backend:8000/api/auth/register", json=payload)
                                if res.status_code == 200:
                                    data = res.json()["user"]
                                    show_profile(data["id"], data["name"], data.get("library_card"))
                                else:
                                    detail = res.json().get("detail", "Ошибка")
                                    reg_err.text = detail[0]["msg"] if isinstance(detail, list) else str(detail)
                        except Exception as e:
                            reg_err.text = "Сервер недоступен"

                    ui.button('Зарегистрироваться', on_click=try_register).classes('w-full bg-green-600')


ui.run(host='0.0.0.0', port=8080, title='Электронная библиотека', show=False)