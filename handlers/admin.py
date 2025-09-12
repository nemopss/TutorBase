import logging
from filters.admin import IsAdmin
from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.types import CallbackQuery, BufferedInputFile
from keyboards.common import admin_keyboard
from database.db import fetch_last_n, fetch_count
from config import config
import csv
from io import StringIO

router = Router()

@router.message(Command("admin"), IsAdmin())
async def cmd_admin(message: types.Message):
    logging.info(f"Admin {message.from_user.id} accessed admin panel.")
    await message.answer('Панель администратора:', reply_markup=admin_keyboard())

@router.message(Command("admin"))
async def cmd_admin_denied(message: types.Message):
    logging.warning(f"Unauthorized access attempt to /admin by user {message.from_user.id}.")
    await message.answer('Доступ запрещён.')


@router.callback_query(F.data == 'admin_list')
async def cb_admin_list(query: CallbackQuery):
    if query.from_user.id not in config.ADMINS:
        await query.answer('Доступ запрещён', show_alert=True)
        return
    logging.info(f"Admin {query.from_user.id} (@{query.from_user.username}) requested application list.")
    rows = await fetch_last_n(10)
    if not rows:
        await query.message.answer('Заявок пока нет.')
        await query.answer()
        return
    texts = []
    for r in rows:
        texts.append(f"#{r['id']} — {r['created_at']} — {r['name']} ({r['language']}, {r['level']})\nКонтакт: {r['contact']}")
    await query.message.answer('\n\n'.join(texts))
    await query.answer()

@router.callback_query(F.data == 'admin_stats')
async def cb_admin_stats(query: CallbackQuery):
    if query.from_user.id not in config.ADMINS:
        await query.answer('Доступ запрещён', show_alert=True)
        return
    logging.info(f"Admin {query.from_user.id} (@{query.from_user.username}) requested stats.")
    cnt = await fetch_count()
    await query.message.answer(f'Всего заявок: {cnt}')
    await query.answer()

@router.callback_query(F.data == 'admin_export_csv')
async def cb_admin_export(query: CallbackQuery):
    if query.from_user.id not in config.ADMINS:
        await query.answer('Доступ запрещён', show_alert=True)
        return
    logging.info(f"Admin {query.from_user.id} (@{query.from_user.username}) requested CSV export.")
    rows = await fetch_last_n(10000)
    if not rows:
        await query.message.answer('Нет данных для экспорта.')
        await query.answer()
        return
    
    sio = StringIO()
    writer = csv.writer(sio)
    writer.writerow(['id', 'created_at', 'name', 'language', 'level', 'preferred_time', 'contact'])
    for r in rows:
        writer.writerow([r['id'], r['created_at'], r['name'], r['language'], r['level'], r['preferred_time'], r['contact']])
    
    csv_bytes = sio.getvalue().encode('utf-8')
    sio.close()

    document = BufferedInputFile(file=csv_bytes, filename='applications.csv')
    
    await query.message.answer_document(document)
    await query.answer()