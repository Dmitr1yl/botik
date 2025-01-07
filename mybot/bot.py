import logging
from telegram import Update, ChatMember
from telegram.ext import (filters, ApplicationBuilder, ContextTypes, CommandHandler, ConversationHandler,
                          MessageHandler, ChatMemberHandler)
from UserStatus import UserStatus
from config import BOT_TOKEN, ADMIN_ID, PROJECT_ID, DIALOGFLOW_CREDENTIALS
import db_connection
from google.cloud import dialogflow

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.WARNING  # Установить уровень логирования: (DEBUG, INFO, WARNING, ERROR, CRITICAL)
)

"""
####### Список команд #######
---> start - 🤖 запускает бота
---> chat - 💬 начать поиск собеседника
---> exit - 🔚 выйти из чата
---> newchat - ⏭ выйти из чата и открыть новый
---> stats - 📊 показать статистику бота (только для администратора)
"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Приветствует пользователя и устанавливает его статус в "ожидании", если он/она еще не в базе данных
    :param update: обновление, полученное от пользователя
    :param context: контекст бота
    :return: статус USER_ACTION
    """
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text="Добро пожаловать в этот ChatBot! Я создан для анонимного общения или простого диалога с ИИ. 🤖\nНапишите /help, чтобы увидеть список моих возможностей.")

    # Добавить пользователя в базу данных, если его там еще нет (проверка выполняется в функции)
    user_id = update.effective_user.id
    db_connection.insert_user(user_id)

    return USER_ACTION

async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает команду /help, отправляя список доступных команд
    """
    help_text = (
        "🛠️ Доступные команды:\n\n"
        "👤 Основные команды:\n"
        "/start - Запустить бота\n"
        "/help - Показать это сообщение\n"
        "/chat - Найти собеседника\n"
        "/exit - Завершить текущий чат\n\n"
        "🤖 Команды для работы с ИИ:\n"
        "/chat_AI - Начать чат с ИИ\n"
        "/exit_AI - Завершить чат с ИИ\n\n"
        "📊 Админ-команды:\n"
        "/stats - Показать статистику бота (только для администратора)\n"
    )
    await update.message.reply_text(help_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_status = db_connection.get_user_status(user_id)
    logging.debug(f"Получено сообщение от {user_id}, статус: {user_status}")

    if user_status == UserStatus.COUPLED:
        # Найти ID партнёра
        other_user_id = db_connection.get_partner_id(user_id)
        logging.debug(f"ID партнёра для {user_id}: {other_user_id}")
        if other_user_id:
            await in_chat(update, other_user_id)
        else:
            logging.warning(f"Партнёр для пользователя {user_id} не найден!")
    else:
        await context.bot.send_message(chat_id=user_id, text="🤖 Вы не находитесь в чате.")


async def handle_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает команду /chat, начиная поиск собеседника, если пользователь еще не ищет
    :param update: обновление, полученное от пользователя
    :param context: контекст бота
    :return: None
    """
    # Обработать команду /chat в разных случаях, в зависимости от статуса пользователя
    current_user_id = update.effective_user.id
    current_user_status = db_connection.get_user_status(user_id=current_user_id)

    if current_user_status == UserStatus.PARTNER_LEFT:
        # Сначала проверить, был ли пользователь оставлен своим собеседником (он обновил бы статус этого пользователя на PARTNER_LEFT)
        db_connection.set_user_status(user_id=current_user_id, new_status=UserStatus.IDLE)

        return await start_search(update, context)
    elif current_user_status == UserStatus.IN_SEARCH:
        # Предупредить пользователя, что он уже в поиске
        return await handle_already_in_search(update, context)
    elif current_user_status == UserStatus.COUPLED:
        # Дважды проверить, находится ли пользователь в чате
        other_user = db_connection.get_partner_id(current_user_id)
        if other_user is not None:
            # Если пользователь уже в паре, предупредить его/ее
            await context.bot.send_message(chat_id=current_user_id,
                                           text="🤖 Вы уже в чате, напишите /exit, чтобы выйти из чата.")
            return None
        else:
            return await start_search(update, context)
    elif current_user_status == UserStatus.IDLE:
        # Пользователь находится в статусе "ожидание", просто начать поиск
        return await start_search(update, context)


async def handle_not_in_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает случай, когда пользователь не находится в чате
    :param update: обновление, полученное от пользователя
    :param context: контекст бота
    :return: None
    """
    current_user_id = update.effective_user.id
    current_user_status = db_connection.get_user_status(user_id=current_user_id)

    if current_user_status in [UserStatus.IDLE, UserStatus.PARTNER_LEFT]:
        await context.bot.send_message(chat_id=current_user_id,
                                       text="🤖 Вы не в чате, напишите /chat, чтобы начать поиск собеседника.")
        return
    elif current_user_status == UserStatus.IN_SEARCH:
        await context.bot.send_message(chat_id=current_user_id,
                                       text="🤖 Сообщение не доставлено, вы все еще в поиске!")
        return


async def handle_already_in_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает случай, когда пользователь уже в поиске
    :param update: обновление, полученное от пользователя
    :param context: контекст бота
    :return: None
    """
    await context.bot.send_message(chat_id=update.effective_chat.id, text="🤖 Вы уже в поиске!")
    return


async def start_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Начинает поиск собеседника, устанавливает статус пользователя в "поиск" и добавляет его/ее в список пользователей
    :param update: обновление, полученное от пользователя
    :param context: контекст бота
    :return: None
    """
    current_user_id = update.effective_chat.id

    # Установить статус пользователя в "поиск"
    db_connection.set_user_status(user_id=current_user_id, new_status=UserStatus.IN_SEARCH)
    await context.bot.send_message(chat_id=current_user_id, text="🤖 Поиск собеседника...")

    # Поиск собеседника
    other_user_id = db_connection.couple(current_user_id=current_user_id)
    # Если собеседник найден, уведомить обоих пользователей
    if other_user_id is not None:
        await context.bot.send_message(chat_id=current_user_id, text="🤖 Вы были соединены с пользователем")
        await context.bot.send_message(chat_id=other_user_id, text="🤖 Вы были соединены с пользователем")

    return


async def handle_exit_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает команду /exit, выходя из чата, если пользователь находится в чате
    :param update: обновление, полученное от пользователя
    :param context: контекст бота
    :return: None
    """
    await exit_chat(update, context)
    return


async def handle_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.effective_user.id)
    if user_id == ADMIN_ID:
        # Получение статистики
        total_users_number, paired_users_number = db_connection.retrieve_users_number()
        total_messages, active_users, idle_users, most_active_user = db_connection.retrieve_detailed_statistics()

        # Формирование ответа
        response = (
            "📊 Статистика бота:\n"
            f"👤 Всего пользователей: {total_users_number}\n"
            f"🤝 Соединённых пар: {paired_users_number}\n"
            f"📨 Всего сообщений: {total_messages}\n"
            f"🔎 Пользователей в поиске: {active_users}\n"
            f"💤 Пользователей без активности: {idle_users}\n"
        )
        if most_active_user:
            response += (
                f"🏆 Самый активный пользователь: {most_active_user[0]} "
                f"(сообщений: {most_active_user[1]})\n"
            )

        # Отправка сообщений администратору
        await context.bot.send_message(chat_id=user_id, text="Добро пожаловать в админ-панель")
        await context.bot.send_message(chat_id=user_id, text=response)
    else:
        logging.warning(f"Пользователь {user_id} попытался получить доступ к админ-панели.")
        await context.bot.send_message(chat_id=user_id, text="⛔️ У вас нет доступа к админ-панели.")

async def exit_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Выходит из чата, отправляя сообщение другому пользователю и обновляя статус обоих пользователей
    :param update: обновление, полученное от пользователя
    :param context: контекст бота
    :return: булево значение: True, если пользователь был в чате (и вышел), False в противном случае
    """
    current_user = update.effective_user.id
    if db_connection.get_user_status(user_id=current_user) != UserStatus.COUPLED:
        await context.bot.send_message(chat_id=current_user, text="🤖 Вы не в чате!")
        return

    other_user = db_connection.get_partner_id(current_user)
    if other_user is None:
        return

    # Выполнить разъединение
    db_connection.uncouple(user_id=current_user)

    await context.bot.send_message(chat_id=current_user, text="🤖 Завершаем чат...")
    await context.bot.send_message(chat_id=other_user,
                                   text="🤖 Ваш собеседник покинул чат, напишите /chat, чтобы начать поиск нового собеседника.")
    await update.message.reply_text("🤖 Вы покинули чат.")

    return


async def exit_then_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает команду /newchat, выходя из чата и начиная новый поиск, если пользователь находится в чате
    :param update: обновление, полученное от пользователя
    :param context: контекст бота
    :return: None
    """
    current_user = update.effective_user.id
    if db_connection.get_user_status(user_id=current_user) == UserStatus.IN_SEARCH:
        return await handle_already_in_search(update, context)
    # Если exit_chat возвращает True, то пользователь был в чате и успешно вышел
    await exit_chat(update, context)
    # Независимо от того, был ли пользователь в чате, начать поиск
    return await start_search(update, context)


async def in_chat(update: Update, other_user_id: int) -> None:
    """
    Пересылает сообщение от одного пользователя к другому.
    """
    try:
        logging.debug(f"Пересылка сообщения от {update.effective_user.id} к {other_user_id}")
        await update.effective_chat.copy_message(
            chat_id=other_user_id,
            message_id=update.message.message_id,
            protect_content=False
        )
        logging.debug(f"Сообщение успешно переслано от {update.effective_user.id} к {other_user_id}")
    except Exception as e:
        logging.error(f"Ошибка при пересылке сообщения: {e}")
        await update.message.reply_text("🤖 Ошибка при отправке сообщения.")

def is_bot_blocked_by_user(update: Update) -> bool:
    new_member_status = update.my_chat_member.new_chat_member.status
    old_member_status = update.my_chat_member.old_chat_member.status
    if new_member_status == ChatMember.BANNED and old_member_status == ChatMember.MEMBER:
        return True
    else:
        return False


async def blocked_bot_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_bot_blocked_by_user(update):
        # Проверить, был ли пользователь в чате
        user_id = update.effective_user.id
        user_status = db_connection.get_user_status(user_id=user_id)
        if user_status == UserStatus.COUPLED:
            other_user = db_connection.get_partner_id(user_id)
            db_connection.uncouple(user_id=user_id)
            await context.bot.send_message(chat_id=other_user, text="🤖 Ваш собеседник покинул чат, напишите /chat, чтобы начать поиск нового собеседника.")
        db_connection.remove_user(user_id=user_id)
        return ConversationHandler.END
    else:
        # API Telegram не предоставляет способа проверить, разблокировал ли пользователь бота
        return USER_ACTION

async def start_chat_ai(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Начинает чат с ИИ.
    """
    user_id = update.effective_user.id
    db_connection.set_user_status(user_id, UserStatus.CHAT_WITH_AI)
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text="🤖 Вы начали чат с ИИ. Напишите что-нибудь!")
    return USER_CHAT_AI

async def handle_chat_ai(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает сообщения пользователя и отправляет их в Dialogflow.
    """
    user_message = update.message.text
    session_client = dialogflow.SessionsClient.from_service_account_json(DIALOGFLOW_CREDENTIALS)
    session = session_client.session_path(PROJECT_ID, update.effective_user.id)

    # Запрос к Dialogflow
    text_input = dialogflow.TextInput(text=user_message, language_code="ru")
    query_input = dialogflow.QueryInput(text=text_input)
    response = session_client.detect_intent(session=session, query_input=query_input)

    # Ответ Dialogflow
    ai_response = response.query_result.fulfillment_text
    await context.bot.send_message(chat_id=update.effective_chat.id, text=ai_response)

async def exit_chat_ai(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Завершает чат с ИИ.
    """
    user_id = update.effective_user.id
    db_connection.set_user_status(user_id, UserStatus.IDLE)
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text="🤖 Вы завершили чат с ИИ. Напишите /chat, чтобы начать поиск собеседника.")
    return ConversationHandler.END

# Определить статус для обработчика диалога
USER_ACTION = 0
USER_CHAT_AI = 1

if __name__ == '__main__':
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    # Создать базу данных, если она еще не создана
    db_connection.create_db()

    # Сбросить статус всех предыдущих существующих пользователей на IDLE, если бот был перезапущен
    db_connection.reset_users_status()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            USER_ACTION: [
                ChatMemberHandler(blocked_bot_handler),
                MessageHandler(
                    (filters.TEXT | filters.ATTACHMENT) & ~ filters.COMMAND & ~filters.Regex("exit") & ~filters.Regex(
                        "chat")
                    & ~filters.Regex("newchat") & ~filters.Regex("stats"),
                    handle_message),
                CommandHandler("chat_AI", start_chat_ai),
                CommandHandler("help", handle_help),
                CommandHandler("chat", handle_chat),
                CommandHandler("exit", handle_exit_chat),
                CommandHandler("newchat", exit_then_chat),
                CommandHandler("stats", handle_stats),
            ],
            USER_CHAT_AI: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_chat_ai),
                CommandHandler("exit_AI", exit_chat_ai),
            ],
        },
        fallbacks=[MessageHandler(filters.TEXT, handle_not_in_chat)],
    )
    application.add_handler(conv_handler)
    application.run_polling()
