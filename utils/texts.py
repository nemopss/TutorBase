
# /utils/texts.py

# --- Start Handler ---
START_MESSAGE = 'Привет! Выбери, что хочешь сделать ниже.'

STARTUP_DEPLOY_NOTIFICATION = "🚀 Бот обновлён и запущен.\n⏱ {time}"

STATUS_REPORT = (
    "<b>Статус бота</b>\n"
    "Запуск: {started_at}\n"
    "Активные напоминания: {active_reminders}\n"
    "Всего напоминаний: {total_reminders}\n"
    "Заявок за неделю: {recent_applications}\n"
    "Всего пользователей: {total_users}"
)

# --- Application Handler ---
TO_MENU_MESSAGE = START_MESSAGE

REGLAMENT_REPLY_TEXT = """каждому ученику обязательно нужно ознакомиться с моими регламентами работы и написать мне, что он ознакомлен🤲🏻
это сайт, для того, чтобы прочитать пункты нужно нажать на треугольник рядом с каждым из них 
в некоторых пунктах есть ещё и подпункты — обращайте внимание! 
*если не открывается, попробуйте отключиться от вай фая, переключиться на LTE и либо выключить впн, либо наоборот его включить
приятного прочтения! ✨"""

PROMPT_FOR_NAME = "Хорошо! Как к тебе обращаться? (имя)"
PROMPT_FOR_LANGUAGE = "Выбери язык занятия:"
PROMPT_FOR_LEVEL = "Какой у тебя уровень? (например: A1, A2, B1, Intermediate, Beginner, Новичок, Продолжающий и т.д.)"
PROMPT_FOR_TIME = "Удобное время для занятий (например: пн/ср 18:00-20:00 или утро/вечер):"
APPLICATION_SUBMITTED = "Спасибо! Твоя заявка принята. Мы свяжемся с тобой в ближайшее время."

# --- Funnel Handler ---
GET_PRICES_TEXT = (
    "Цена на индивидуальные занятия зависит от языка, актуальной ставки за час, "
    "формата обучения, длительности урока, их количества, цели изучения языка. "
    "Всё это необходимо обсудить лично, для этого я провожу диагностику. \n\n"
    "<b>Что такое диагностика?</b>\n"
    "— это созвон в зум на русском языке минут на 30-40, где мы можем познакомиться, "
    "ты можешь задать все вопросы и получить на них ответы, рассказать о своей нынешней "
    "ситуации и описать желаемую, а также получить индивидуальный план достижения своей цели. "
    "Поэтому чтобы узнать цену именно за твои индивидуальные занятия, приходи на диагностику. "
    "Она будет бесплатная. Готов на нее записаться? \n\n"
)
PROMPT_FOR_DIAGNOSTIC_TIME = "Отлично! Напишите удобный день и время для созвона (например: 'завтра после 15:00' или 'сб/вс в любое время')."
DIAGNOSTIC_SUBMITTED = "Спасибо! Ваша заявка принята! Скоро с вами свяжутся для подтверждения времени ☺️"

# --- Admin Handler ---
ADMIN_PANEL = 'Панель администратора:'
ADMIN_STATS_MENU = 'Раздел статистики:'
ADMIN_CASES_MENU = 'Менеджер кейсов:'
ADMIN_PACKAGES_MENU = 'Менеджер пакетов:'
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
REMINDER_TYPE_PAYMENT_WEEK = "оплата — за неделю"
REMINDER_TYPE_PAYMENT_DAY = "оплата — за день"
REMINDER_TYPE_PAYMENT_GENERIC = "оплата"
REMINDER_TYPE_LESSON_DAY_BEFORE = "подтверждение за день"
REMINDER_TYPE_HOMEWORK = "домашнее задание"
REMINDER_TYPE_PACKAGE_RENEWAL = "продление пакета"
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
REMINDER_DAY_BEFORE_MESSAGE = (
    "Привет, {name}! Напоминаю, у тебя завтра занятие {schedule}. Всё в силе?."
)
HOMEWORK_REMINDER_MESSAGE = (
    "Привет, {name}! Напоминаю: урок {schedule}. "
    "Не забудь выполнить и отправить домашку как минимум за час до времени твоего урока."
)
PACKAGE_RENEWAL_REMINDER_MESSAGE = (
    "Привет, {name}! Твой пакет занятий заканчивается {end_date}. "
    "Скажи, пожалуйста, ты планируешь продолжать занятия в следующем месяце?"
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
    "Тип: {kind}\n"
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
DATABASE_ERROR = "Произошла ошибка при работе с базой данных. Попробуйте ещё раз позже."


# --- Payment Reminders ---
PAYMENT_REMINDER_WEEK_BEFORE = (
    "Привет, {name}! Твой пакет занятий через неделю заканчивается. "
    "Согласно регламентам работы, оплата нового пакета занятий происходит в день "
    "последнего урока после его проведения. У нас это {last_lesson_date}. "
    "Продолжаем в том же темпе?"
)
PAYMENT_REMINDER_DAY_BEFORE = (
    "Привет, {name}! Завтра истекает срок действия твоего оплаченного пакета занятий. "
    "Согласно регламентам работы, оплата нового пакета занятий происходит в день "
    "последнего урока после его проведения."
)

# Payment reminder button texts
PAYMENT_CONFIRM_BUTTON = "✅ Всё хорошо, продолжаем"
PAYMENT_DECLINE_BUTTON = "❌ Я не смогу оплатить"

# Payment reminder response texts
PAYMENT_CONFIRM_REPLY = "Отлично! Я передам информацию преподавателю."
PAYMENT_DECLINE_REPLY = "Спасибо за информацию. Я передал её преподавателю."

# Payment reminder log texts
PAYMENT_CONFIRM_LOG = (
    "#payment_confirm\n"
    "Ученик: {name}\n"
    "Ответ: подтвердил продолжение занятий. @{mention}"
)
PAYMENT_DECLINE_LOG = (
    "#payment_decline\n"
    "Ученик: {name}\n"
    "Ответ: не сможет оплатить следующий пакет. @{mention}"
)
PAYMENT_REMINDERS_MENU_HEADER = "Напоминания об оплате для {name}:"
PAYMENT_REMINDERS_EMPTY = "Для ученика {name} напоминаний об оплате пока нет."
PAYMENT_REMINDERS_EMPTY_HINT = "Нажмите «Создать напоминание об оплате», чтобы добавить новое."
PAYMENT_REMINDER_PROMPT_LAST_LESSON = "Введите дату и время последнего занятия в формате ДД.ММ.ГГГГ ЧЧ:ММ (по Москве)."
PAYMENT_REMINDER_CREATED = (
    "Готово! Созданы напоминания об оплате:\n"
    "{week_line}\n"
    "{day_line}"
)
PAYMENT_REMINDER_STATUS_LINE = "— {label}: {status}"
PAYMENT_REMINDER_STATUS_SCHEDULE = "следующее срабатывание — {next_run}"
PAYMENT_REMINDER_STATUS_PAST = "дата в прошлом — напоминание неактивно"
PAYMENT_REMINDER_LABEL_WEEK = "За неделю"
PAYMENT_REMINDER_LABEL_DAY = "За день"
PAYMENT_REMINDER_COMMENT_WEEK = "Оплата: за неделю до последнего занятия"
PAYMENT_REMINDER_COMMENT_DAY = "Оплата: за день до последнего занятия"
PACKAGES_EMPTY = 'Пакетов пока нет. Создайте первый, чтобы начать планировать напоминания.'
PACKAGES_LIST_HEADER = 'Пакеты (всего: {total}):'
PACKAGES_LIST_ITEM = '{index}. {title} — {learner} ({status}, уроки все/проведено/отменено: {lessons})'
PACKAGE_DETAILS = (
    '<b>{title}</b>\n'
    'Ученик: {learner}\n'
    'Статус: {status}\n'
    'Уроки (все/проведено/отменено): {lessons}\n'
    'Период: {period}\n'
    'Часовой пояс: {timezone}\n'
    'Заметки: {notes}'
)
PACKAGE_PERIOD_UNKNOWN = '—'
PACKAGE_REGENERATED = 'Напоминания для пакета «{title}» обновлены.'
PACKAGE_REGENERATE_FAILED = 'Не удалось обновить напоминания: {error}'
PACKAGE_NOT_FOUND = 'Пакет не найден.'
PACKAGE_LESSONS_HEADER = 'Уроки пакета «{title}»:'
PACKAGE_LESSONS_EMPTY = 'У пакета пока нет уроков.'
PACKAGE_LESSON_ITEM = '{index}. {scheduled} — {status}'
PACKAGE_CREATE_SELECT_LEARNER = 'Выберите ученика для пакета:'
PACKAGE_CREATE_NO_LEARNERS = 'Сначала добавьте ученика, чтобы создать пакет.'
PACKAGE_PROMPT_TITLE = 'Введите название пакета:'
PACKAGE_TITLE_REQUIRED = 'Название пакета не может быть пустым.'
PACKAGE_PROMPT_NOTES = 'Добавьте заметку (или "-" чтобы пропустить).'
PACKAGE_CREATE_CANCELLED = 'Создание пакета отменено.'
PACKAGE_CREATED = 'Пакет «{title}» создан.'
PACKAGE_LESSON_PROMPT_DATETIME = 'Введите дату и время урока в формате ДД.ММ.ГГГГ ЧЧ:ММ (в часовом поясе пакета).'
PACKAGE_LESSON_INVALID_DATETIME = 'Неверный формат даты/времени. Используйте ДД.ММ.ГГГГ ЧЧ:ММ.'
PACKAGE_LESSON_PROMPT_DURATION = 'Введите длительность урока в минутах (или "-" чтобы оставить пустой):'
PACKAGE_LESSON_INVALID_DURATION = 'Длительность должна быть положительным числом.'
PACKAGE_LESSON_CREATED = 'Урок добавлен в пакет «{title}».'
PACKAGE_ADD_LESSON_CANCELLED = 'Добавление урока отменено.'
PACKAGE_LESSON_EDIT_PROMPT = 'Введите новую дату и время урока #{index} в формате ДД.ММ.ГГГГ ЧЧ:ММ (в часовом поясе пакета).'
PACKAGE_LESSON_UPDATED = 'Урок #{index} обновлён.'
PACKAGE_LESSON_DELETED = 'Урок #{index} удалён.'
PACKAGE_LESSON_EDIT_CANCELLED = 'Редактирование урока отменено.'
PACKAGE_LESSON_PROMPT_STATUS = 'Введите статус урока #{index} (например completed):'
PACKAGE_LESSON_PROMPT_STATUS_INLINE = 'Выберите статус урока #{index}:'
PACKAGE_LESSON_INVALID_STATUS = 'Недопустимый статус. Используйте scheduled/completed/cancelled.'
PACKAGE_LESSON_STATUS_UPDATED = 'Статус урока #{index} обновлён.'
PACKAGE_LESSON_PROMPT_NOTES = 'Введите заметку для урока #{index} (или "-" чтобы убрать).'
PACKAGE_LESSON_NOTES_UPDATED = 'Заметка для урока #{index} обновлена.'
PACKAGE_LESSON_PROMPT_DURATION_EDIT = 'Введите новую длительность урока #{index} в минутах (или "-" чтобы убрать):'
PACKAGE_LESSON_DURATION_UPDATED = 'Длительность урока #{index} обновлена.'
PACKAGE_CREATED_NOTICE = '✅ Пакет создан.'
PACKAGE_UPDATED_NOTICE = '✅ Пакет обновлён.'
PACKAGE_LESSON_CREATED_NOTICE = '✅ Урок добавлен.'
PACKAGE_LESSON_UPDATED_NOTICE = '✅ Урок обновлён.'
PACKAGE_EDIT_PROMPT_STATUS = 'Выберите статус пакета:'
PACKAGE_EDIT_PROMPT_START = 'Введите дату начала пакета в формате ДД.ММ.ГГГГ (или "-" чтобы пропустить):'
PACKAGE_EDIT_PROMPT_TIMEZONE = 'Введите часовой пояс пакета (например Europe/Moscow):'
PACKAGE_EDIT_PROMPT_NOTES = 'Обновите заметку (или "-" чтобы оставить пустой):'
PACKAGE_EDIT_CANCELLED = 'Редактирование пакета отменено.'
PACKAGE_UPDATED = 'Пакет «{title}» обновлён.'
PACKAGE_EDIT_INVALID_STATUS = 'Недопустимый статус. Используйте draft/active/completed/cancelled.'
PACKAGE_EDIT_INVALID_DATE = 'Неверный формат даты. Используйте ДД.ММ.ГГГГ или "-".'
PACKAGE_EDIT_INVALID_TIMEZONE = 'Не удалось распознать часовой пояс. Попробуйте снова.'
PACKAGE_EDIT_NO_CHANGES = 'Изменений не обнаружено.'
PACKAGE_DELETE_CONFIRM = 'Удалить пакет «{title}» вместе со всеми уроками и напоминаниями?'
PACKAGE_DELETED = 'Пакет удалён.'
PACKAGE_TEMPLATES_MENU = 'Пресеты пакетов:'
PACKAGE_TEMPLATES_EMPTY = 'Пресетов пока нет. Создайте первый, чтобы автоматизировать создание пакетов.'
PACKAGE_TEMPLATES_LIST_HEADER = 'Пресеты (всего: {total}):'
PACKAGE_TEMPLATE_LIST_ITEM = '{index}. {name} — {lessons} уроков, {duration} дней'
PACKAGE_TEMPLATE_DETAILS = (
    '<b>{name}</b>\n'
    'Уроков: {lesson_count}\n'
    'Длительность (дней): {duration_days}\n'
    'Часовой пояс: {timezone}\n'
    'Описание: {description}'
)
PACKAGE_TEMPLATE_SCHEDULE_LINE = '- {day} {time}'
PACKAGE_TEMPLATE_CREATED = 'Пресет «{name}» создан.'
PACKAGE_TEMPLATE_CREATED_FROM = 'Пресет «{name}» создан на основе «{source}».'
PACKAGE_TEMPLATE_DELETED = 'Пресет удалён.'
PACKAGE_TEMPLATE_DELETE_CONFIRM = 'Удалить пресет «{name}»?'
PACKAGE_TEMPLATE_PROMPT_NAME = 'Введите название пресета:'
PACKAGE_TEMPLATE_PROMPT_DESCRIPTION = 'Введите описание (или "-" чтобы пропустить):'
PACKAGE_TEMPLATE_PROMPT_SCHEDULE = 'Введите дни и время уроков (например: "Пн 19:00, Чт 19:00"):'
PACKAGE_TEMPLATE_PROMPT_LESSON_COUNT = 'Введите количество уроков (или "-" чтобы пропустить):'
PACKAGE_TEMPLATE_PROMPT_DURATION = 'Введите длительность пакета в днях (или "-" чтобы пропустить):'
PACKAGE_TEMPLATE_PROMPT_TIMEZONE = 'Введите часовой пояс (например Europe/Moscow):'
PACKAGE_TEMPLATE_INVALID_NUMBER = 'Введите положительное число или "-".'
PACKAGE_TEMPLATE_CANCELLED = 'Создание пресета отменено.'
PACKAGE_TEMPLATE_NOT_FOUND = 'Пресет не найден.'
PACKAGE_TEMPLATE_INVALID_SCHEDULE = 'Неверный формат расписания. Пример: "Пн 19:00, Чт 19:00".'
PACKAGE_TEMPLATE_PROMPT_START_DATE = 'Введите дату начала пакета для пресета в формате ДД.ММ.ГГГГ:'
PACKAGE_TEMPLATE_INVALID_DATE = 'Неверный формат даты. Используйте ДД.ММ.ГГГГ.'
PACKAGE_PROMPT_TITLE_TEMPLATE = 'Введите название пакета (или "-" чтобы использовать «{default}»):'
PACKAGE_TEMPLATE_SELECT_PROMPT = 'Выберите пресет или создайте пакет вручную:'
PACKAGE_TEMPLATE_PROMPT_NAME_EDIT = 'Введите новое название пресета (или "-" чтобы оставить «{current}»):'
PACKAGE_TEMPLATE_PROMPT_DESCRIPTION_EDIT = 'Введите новое описание (или "-" чтобы оставить текущее):'
PACKAGE_TEMPLATE_PROMPT_SCHEDULE_EDIT = 'Введите расписание (например: "Пн 19:00, Чт 19:00") или "-" чтобы оставить без изменений:'
PACKAGE_TEMPLATE_PROMPT_LESSON_COUNT_EDIT = 'Введите количество уроков (или "-" чтобы оставить {current}):'
PACKAGE_TEMPLATE_PROMPT_DURATION_EDIT = 'Введите длительность пакета в днях (или "-" чтобы оставить {current}):'
PACKAGE_TEMPLATE_PROMPT_TIMEZONE_EDIT = 'Введите часовой пояс (или "-" чтобы оставить {current}):'
