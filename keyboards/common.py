from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import config

def start_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text='Открыть TutorBase', web_app={'url': config.MINI_APP_URL})
    builder.adjust(1)
    return builder.as_markup()

def admin_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text='Открыть TutorBase', web_app={'url': config.MINI_APP_URL})
    builder.adjust(1)
    return builder.as_markup()

def reglament_keyboard():
    return start_keyboard()

def programs_keyboard():
    return start_keyboard()

def back_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data="back")
    return builder.as_markup()


def back_with_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data="back")
    builder.button(text="🏠 В меню", callback_data="to_menu")
    builder.adjust(1)
    return builder.as_markup()


def admin_stats_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text='📄 Последние заявки', callback_data='admin_list')
    builder.button(text='📈 Общая статистика', callback_data='admin_stats')
    builder.button(text='⬇️ Export CSV', callback_data='admin_export_csv')
    builder.button(text='🗑️ Очистить заявки', callback_data='clear_applications')
    builder.button(text='⬅️ Назад', callback_data='back_to_admin_panel')
    builder.adjust(1)
    return builder.as_markup()


def admin_cases_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text='➕ Добавить кейс', callback_data='add_student')
    builder.button(text='➖ Удалить кейс', callback_data='delete_student')
    builder.button(text='⬅️ Назад', callback_data='back_to_admin_panel')
    builder.adjust(1)
    return builder.as_markup()
