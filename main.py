from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
from collections import defaultdict

ASK_NICK, ASK_NAME, ASK_AGE, ASK_PHOTOS = range(4)
photo_collections = defaultdict(list)
media_group_track = {}
user_photos = {}

ADMIN_ID = 0000000 # СЮДА ВПИСАТЬ СВОЙ АЙДИ
GROUP_LINK = "https://t.me/your_group_invite" # СЮДА ВСТВИТЬ ССЫЛКУ, КОТОРАЯ ПЕРЕДАСТСЯ ПОЛЬЗОВАТЕЛЮ ПРИ ПРИНЯТИИ ЗАЯВКИ


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    keyboard = [
        [InlineKeyboardButton("📥 Подать заявку", callback_data="submit_request")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(chat_id=chat_id, text='Здравствуйте. Вы можете подать заявку в клан "Отчаянные".', reply_markup=reply_markup)

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "submit_request":
        await query.message.reply_text("Введите ваш nickname:")
        return ASK_NICK
    
async def get_nick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["nick"] = update.message.text
    await update.message.reply_text("Введите ваше имя:")
    return ASK_NAME
    
async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text("Введите ваш возраст:")
    return ASK_AGE

async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["age"] = update.message.text
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Готово", callback_data="done_photos")]]
    )
    await update.message.reply_text(
        "Отправьте фотографии, а когда закончите — нажмите кнопку «Готово»", 
        reply_markup=keyboard
    )

    user_photos[update.message.from_user.id] = []

    return ASK_PHOTOS

async def get_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    # Проверяем, что у пользователя есть список для фото
    if user_id not in user_photos:
        user_photos[user_id] = []

    # Сохраняем file_id последнего фото (наибольшего размера)
    file_id = update.message.photo[-1].file_id
    user_photos[user_id].append(file_id)

    await update.message.reply_text("✅ Фото получено. Можете отправить еще или нажать кнопку «Готово».")

    return ASK_PHOTOS

async def done_photos_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    photos = user_photos.pop(user_id, [])

    if not photos:
        await query.message.reply_text("❗Вы не отправили ни одной фотографии.")
        return ASK_PHOTOS

    # Формируем медиа-группу с подписью на первом фото
    media = []
    for i, file_id in enumerate(photos):
        if i == 0:
            caption = (
                f"📨 Новая заявка:\n"
                f"👤 Ник: {context.user_data.get('nick')}\n"
                f"🧾 Имя: {context.user_data.get('name')}\n"
                f"🎂 Возраст: {context.user_data.get('age')}"
            )
            media.append(InputMediaPhoto(media=file_id, caption=caption))
        else:
            media.append(InputMediaPhoto(media=file_id))

    # Отправляем альбом админу
    await context.bot.send_media_group(chat_id=ADMIN_ID, media=media)

    # Кнопки "Принять / Отклонить"
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Принять", callback_data=f"approve:{user_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject:{user_id}")
        ]
    ])
    await context.bot.send_message(chat_id=ADMIN_ID, text="Принять заявку?", reply_markup=keyboard)

    await query.message.reply_text("🎉 Заявка отправлена на рассмотрение!")

    return ConversationHandler.END

async def handle_admin_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, user_id = query.data.split(":")
    user_id = int(user_id)

    if action == "approve":
        await context.bot.send_message(chat_id=user_id, text=f"✅ Ваша заявка одобрена! Присоединяйтесь: {GROUP_LINK}")
        await query.edit_message_text("Заявка принята ✅")
    elif action == "reject":
        await context.bot.send_message(chat_id=user_id, text="❌ Ваша заявка была отклонена.")
        await query.edit_message_text("Заявка отклонена ❌")

# Отмена анкеты
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Заявка отменена.")
    return ConversationHandler.END

async def get_my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(f"Ваш ID: `{user_id}`", parse_mode="Markdown")

if __name__ == "__main__":
    app = ApplicationBuilder().token("").build() # ВАШ ТОКЕН ОТ БОТА TELEGRAM

    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handle_button, pattern="^submit_request$")
        ],
        states={
            ASK_NICK: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_nick)],
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            ASK_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
            ASK_PHOTOS: [
                MessageHandler(filters.PHOTO, get_photos),
                CallbackQueryHandler(done_photos_callback, pattern="^done_photos$")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", get_my_id))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(handle_admin_decision, pattern="^(approve|reject):"))

    print("Бот запущен!")
    app.run_polling()