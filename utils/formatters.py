from typing import Dict

def format_application(app: Dict) -> str:
    return (
        f"📩 <b>Новая заявка</b>\n"
        f"<b>ID:</b> {app.get('id', '—')}\n"
        f"<b>Дата:</b> {app['created_at']}\n"
        f"<b>Имя:</b> {app['name']}\n"
        f"<b>Язык:</b> {app['language']}\n"
        f"<b>Уровень:</b> {app['level']}\n"
        f"<b>Удобное время:</b> {app['preferred_time']}\n"
        f"<b>Контакт:</b> {app['contact']}\n"
    )
