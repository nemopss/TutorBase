from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import config

def start_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text='📝 Оставить заявку', callback_data='start_apply')
    # builder.button(text='🔗 Заполнить форму (Google Forms)', url=config.GOOGLE_FORM_URL)
    builder.button(text='🫶🏻 Регламенты работы', callback_data='reglament_reply')
    builder.adjust(1)
    return builder.as_markup()

def admin_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text='📄 Последние заявки', callback_data='admin_list')
    builder.button(text='📊 Статистика', callback_data='admin_stats')
    builder.button(text='⬇️ Export CSV', callback_data='admin_export_csv')
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
