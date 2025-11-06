from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import config

def start_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text='🫶🏻 Регламенты работы', callback_data='reglament_reply')
    # builder.button(text='🔗 Заполнить форму (Google Forms)', url=config.GOOGLE_FORM_URL)
    builder.button(text='💰 Узнать цены', callback_data='get_prices')
    # builder.button(text='💬 Результаты учеников', callback_data='show_cases')
    builder.button(text='📝 Оставить заявку', callback_data='start_apply')
    builder.adjust(1)
    return builder.as_markup()

def admin_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text='🌐 Open Web App', web_app={'url': config.MINI_APP_URL})
    builder.button(text='👩‍🎓 Ученики', callback_data='manage_students')
    builder.button(text='📦 Пакеты', callback_data='packages_manager')
    builder.button(text='📊 Статистика', callback_data='admin_stats_menu')
    builder.button(text='📚 Менеджер кейсов', callback_data='cases_manager')
    builder.adjust(1)
    return builder.as_markup()

def reglament_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text='Прочитать регламенты', url=config.REGULATIONS_URL)
    builder.button(text='📝 Оставить заявку', callback_data='start_apply')
    builder.adjust(1)
    return builder.as_markup()

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
