
# /utils/texts.py

# --- Start Handler ---
START_MESSAGE = (
    'Привет! Я бот И КСЮША НАПИШЕТ МНЕ СЮДА ТЕКСТ.\n\n' 
    'Выбери, что хочешь сделать ниже.'
)

# --- Application Handler ---
TO_MENU_MESSAGE = START_MESSAGE

REGLAMENT_REPLY_TEXT = """
❗️❗️каждому ученику обязательно нужно ознакомиться повторно с обновленными регламентами работы и написать мне после ознакомления🤲🏻
это сайт, для того, чтобы прочитать пункты нужно нажать на треугольник рядом с каждым из них 
в некоторых пунктах есть ещё и подпункты — обращайте внимание 
*если не открывается, попробуйте отключиться от вай фая, переключиться на LTE и либо выключить впн, либо наоборот его включить
приятного прочтения! ✨
"""

PROMPT_FOR_NAME = "Хорошо! Как к тебе обращаться? (имя)"
PROMPT_FOR_LANGUAGE = "Выбери язык занятия:"
PROMPT_FOR_LEVEL = "Какой у тебя уровень? (например: A1, A2, B1, Intermediate, Beginner и т.д.)"
PROMPT_FOR_TIME = "Удобное время для занятий (например: пн/ср 18:00-20:00 или утро/вечер):"
APPLICATION_SUBMITTED = "Спасибо! Твоя заявка принята. Мы свяжемся с тобой в ближайшее время."

# --- Funnel Handler ---
GET_PRICES_TEXT = (
    "Цена зависит от формата обучения и других факторов, " 
    "которые мы как раз подробно обсудим на диагностике ☺️\n\n" 
    "Она будет бесплатная. Готов записаться?"
)
PROMPT_FOR_DIAGNOSTIC_TIME = "Отлично! Напишите удобный день и время для созвона (например: 'завтра после 15:00' или 'сб/вс в любое время')."
DIAGNOSTIC_SUBMITTED = "Спасибо! Я передал вашу заявку, скоро с вами свяжутся для подтверждения времени ☺️"

# --- Admin Handler ---
ADMIN_PANEL = 'Панель администратора:'
ADMIN_STATS_MENU = 'Раздел статистики:'
ADMIN_CASES_MENU = 'Менеджер кейсов:'
ACCESS_DENIED = 'Доступ запрещён.'
NO_APPLICATIONS = 'Заявок пока нет.'
STATS_TOTAL_APPLICATIONS = 'Всего заявок: {count}'
NO_DATA_TO_EXPORT = 'Нет данных для экспорта.'
PROMPT_ADD_STUDENT_NAME = "Введите имя ученика (оно будет на кнопке):"
PROMPT_ADD_STUDENT_STORY = "Теперь введите историю успеха ученика (можно длинным текстом):"
STUDENT_ADDED_SUCCESS = "Ученик '{name}' успешно добавлен!"
NO_STUDENTS_IN_DB = "В базе пока нет учеников."
CHOOSE_STUDENT_TO_DELETE = "Выберите ученика, которого хотите удалить:"
CONFIRM_DELETE_STUDENT = "Вы уверены, что хотите удалить ученика '{name}'? Это действие необратимо."
STUDENT_DELETED_SUCCESS = "Ученик успешно удален."
STUDENT_NOT_FOUND = "Ученик не найден!"
PROMPT_ADD_STUDENT_PHOTO = "Теперь отправь фотографию ученика (или нажми 'Пропустить')."

LEARNERS_MENU_HEADER = "Ученики (всего: {total})"
LEARNERS_MENU_ITEM = "{index}. {name} — {username}"
LEARNERS_MENU_FOOTER = "Страница {page}/{pages}"
LEARNERS_EMPTY = "Пока нет учеников. Нажмите «Добавить ученика», чтобы создать первого."
LEARNER_PICK_USER = "Выберите пользователя (страница {page}/{pages}):"
LEARNER_NO_AVAILABLE_USERS = "Нет пользователей, которых можно добавить."
LEARNER_PROMPT_DISPLAY = "Введите отображаемое имя ученика или '-' чтобы использовать вариант по умолчанию «{default}»."
LEARNER_PROMPT_NOTES = "Добавьте заметку (или '-' чтобы оставить пустой)."
LEARNER_INTERNAL_ERROR = "Не удалось завершить операцию. Попробуйте ещё раз."
LEARNER_CREATED = "Ученик «{name}» успешно добавлен."
LEARNER_ALREADY_EXISTS = "Этот пользователь уже добавлен в список учеников."
LEARNER_USER_NOT_FOUND = "Не удалось найти выбранного пользователя."
LEARNER_NOT_FOUND = "Ученик не найден."
LEARNER_NOTES_EMPTY = "—"
LEARNER_DETAILS = (
    "👤 <b>{name}</b>\n"
    "Username: {username}\n"
    "Chat ID: <code>{chat_id}</code>\n"
    "Последний контакт: {last_seen}\n"
    "Добавлен: {created_at}\n"
    "Заметка: {notes}"
)
LEARNER_REMINDER_PREFILLED = (
    "Создаём напоминание для {name}.\n"
    "Контакт уже подставлен ({username}). Выберите тип напоминания:"
)
LEARNER_NO_REMINDERS = "Для ученика {name} пока нет напоминаний."
LEARNER_REMINDERS_HEADER = "Напоминания для {name}:"
LEARNER_REMINDER_ITEM = "#{reminder_id} — {schedule} → {next_run} ({status})"
LEARNER_REMINDER_ACTIVE = "активно"
LEARNER_REMINDER_INACTIVE = "не активно"
LEARNER_DELETE_CONFIRM = "Удалить ученика «{name}»?"
LEARNER_DELETED = "Ученик удалён."

# --- Reminders ---
REMINDERS_MENU = "Менеджер уроков:"
REMINDERS_EMPTY = "Напоминаний пока нет."
REMINDER_NOT_FOUND = "Напоминание не найдено."
REMINDER_PROMPT_STUDENT_NAME = "Введите имя ученика для напоминания:"
REMINDER_PROMPT_STUDENT_CONTACT = (
    "Пришлите контакт ученика. Можно указать числовой chat_id или @username."
)
REMINDER_CONTACT_RESOLVE_FAILED = (
    "Не удалось получить chat_id по этому контакту. Убедитесь, что ученик написал боту, "
    "или введите числовой chat_id вручную."
)
REMINDER_TYPE_CHOICE = "Напоминание будет регулярным или одноразовым?"
REMINDER_SELECT_DAYS = "Выберите дни проведения уроков. Нажимайте, чтобы переключать."
REMINDER_NO_DAYS_SELECTED = "Выберите хотя бы один день."
REMINDER_PROMPT_TIME = "Введите время урока в формате HH:MM (по Москве)."
REMINDER_PROMPT_DATE = (
    "Введите дату и время урока в формате ДД.ММ.ГГГГ ЧЧ:ММ (по Москве)."
)
REMINDER_PROMPT_LEAD = "За сколько минут до урока отправлять напоминание? (число, по умолчанию 60)"
REMINDER_PROMPT_COMMENT = "Добавьте комментарий (или пришлите '-')."
REMINDER_CREATED = "Напоминание создано. Следующее срабатывание: {next_run}."
REMINDER_INVALID_TIME = "Неверный формат времени. Используйте HH:MM."
REMINDER_INVALID_DATE = "Неверный формат даты. Используйте ДД.ММ.ГГГГ ЧЧ:ММ."
REMINDER_INVALID_LEAD = "Введите количество минут (целое неотрицательное число)."
REMINDER_SUMMARY = (
    "<b>{name}</b> — {schedule}\n"
    "Следующее срабатывание: {next_run}\n"
    "Тип: {reminder_type}\n"
    "Комментарий: {comment}"
)
REMINDER_TYPE_RECURRING = "еженедельное"
REMINDER_TYPE_ONE_TIME = "одноразовое"
REMINDER_DAY_PREFIX = "✅ "
REMINDER_DAY_PREFIX_OFF = "❌ "
REMINDER_ALREADY_INACTIVE = "Это напоминание уже отключено."
REMINDER_DEACTIVATED = "Напоминание отключено."
REMINDER_ACTIVATED = "Напоминание активировано. Следующее срабатывание: {next_run}."
REMINDER_DELETED = "Напоминание удалено."
REMINDER_NO_NEXT_RUN = "Нет будущих срабатываний — проверьте расписание."
REMINDER_TRIGGER_MESSAGE = (
    "Привет, {name}! Напоминаю о занятии {schedule}."
)
REMINDER_CONFIRM_BUTTON = "👍 Подтверждаю"
REMINDER_DECLINE_BUTTON = "😔 Не смогу"
REMINDER_CONFIRM_REPLY = "Отлично! Я передам информацию преподавателю."
REMINDER_DECLINE_REASON_PROMPT = "Жаль! Напишите, пожалуйста, причину отмены занятия."
REMINDER_DECLINE_REPLY = "Спасибо! Я передал информацию преподавателю."
REMINDER_CONFIRM_LOG = (
    "#reminder_confirm\n"
    "Ученик: {name}\n"
    "Ответ: подтвердил занятие. @{mention}"
)
REMINDER_DECLINE_LOG = (
    "#reminder_decline\n"
    "Ученик: {name}\n"
    "Ответ: отменил занятие. Причина: {reason}\n@{mention}"
)
REMINDER_SENT_LOG = (
    "#reminder_sent\n"
    "Ученик: {name}\n"
    "Расписание: {schedule}\n"
    "Lead: {lead} минут\n"
    "Следующее срабатывание: {next_run}\n@{mention}"
)
REMINDER_DETAILS_TITLE = "Напоминание #{id}"
REMINDER_DETAILS_BODY = (
    "Ученик: {name}\n"
    "Контакт: {contact}\n"
    "Тип: {reminder_type}\n"
    "Расписание: {schedule}\n"
    "Следующее срабатывание: {next_run}\n"
    "Активно: {active}\n"
    "Комментарий: {comment}\n"
    "Последний ответ: {last_response}"
)
REMINDER_STATUS_NONE = "—"
REMINDER_STATUS_CONFIRM = "Подтвержден"
REMINDER_STATUS_DECLINE = "Отменен"

# --- Clear Applications ---
NO_APPLICATIONS_TO_CLEAR = "Заявок для очистки нет."
CLEAR_APPLICATIONS_CONFIRMATION = "Вы уверены, что хотите очистить все заявки? Это действие необратимо. Все заявки будут выгружены в файлы и отправлены вам."
APPLICATIONS_CLEARED = "Все заявки были успешно удалены."

# --- Cute Message ---
PROMPT_FOR_CUTE_MESSAGE = "Напиши сообщение, которое хочешь отправить!"
CUTE_MESSAGE_SENT = "Сообщение успешно отправлено!"
CUTE_MESSAGE_HEADER = "Сообщение!️:"



# --- Cases Handler ---
NO_CASES_YET = "Пока здесь нет историй учеников."
CASES_LIST_HEADER = "Вот результаты некоторых моих учеников. Нажмите на имя, чтобы прочитать историю:"
CASE_STORY_HEADER = "Кейс: {name}\n\n{story}"

# --- Common Errors ---
DATABASE_ERROR = "Произошла ошибка при работе с базой данных. Попробуйте позже."
