from nicegui import ui
import httpx


@ui.page('/')
def index():
    # Настраиваем центрирование всего контента на весь экран
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
            # Даем элементу имя card_display
            card_display = ui.label('Генерируется воркером...').classes(
                'bg-blue-100 text-blue-800 px-4 py-2 rounded font-mono text-lg mt-2')

        # --- ФОРМА РЕГИСТРАЦИИ ---
        form_card = ui.card().classes('w-96 p-8 shadow-lg')
        with form_card:
            name_input = ui.input('Имя').classes('w-full mb-2')
            email_input = ui.input('Email').classes('w-full mb-2')
            password_input = ui.input('Пароль').props('type=password').classes('w-full mb-4')
            error_label = ui.label('').classes('text-red-500 text-sm font-bold w-full text-center mb-2')

            async def try_register():
                error_label.text = ''
                payload = {"name": name_input.value, "email": email_input.value, "password": password_input.value}

                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.post("http://backend:8000/api/auth/register", json=payload)
                        data = response.json()

                        if response.status_code == 200:
                            user_id = data["user"]["id"]
                            name_display.text = data["user"]["name"]
                            id_display.text = f"ID: {user_id}"

                            form_card.style('display: none;')
                            profile_card.style('display: flex;')

                            # --- НОВАЯ ЛОГИКА ОЖИДАНИЯ БИЛЕТА ---
                            async def check_card_status():
                                try:
                                    async with httpx.AsyncClient() as poll_client:
                                        res = await poll_client.get(f"http://backend:8000/api/auth/profile/{user_id}")
                                        if res.status_code == 200:
                                            card = res.json().get("library_card")
                                            if card:  # Если база вернула не null
                                                card_display.text = card
                                                # Меняем цвет плашки с синего на зеленый
                                                card_display.classes(remove='bg-blue-100 text-blue-800',
                                                                     add='bg-green-100 text-green-800')
                                                timer.deactivate()  # Выключаем таймер, задача выполнена!
                                except Exception:
                                    pass  # Игнорируем временные ошибки сети

                            # Запускаем функцию check_card_status каждые 2 секунды
                            timer = ui.timer(2.0, check_card_status, active=True)

                        else:
                            detail = data.get("detail", "Ошибка валидации")
                            if isinstance(detail, list):
                                error_label.text = detail[0].get("msg", "Проверьте данные")
                            else:
                                error_label.text = str(detail)
                except Exception as e:
                    error_label.text = f"Сервер недоступен: {e}"

            ui.button('Зарегистрироваться', on_click=try_register).classes('w-full bg-blue-600')

ui.run(host='0.0.0.0', port=8080, title='Электронная библиотека', show=False)
