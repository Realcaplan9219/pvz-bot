import os
import pandas as pd
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, ContextTypes, filters


# ==========================
# BOT TOKEN
# ==========================
TOKEN = "YANGI_TOKENINGIZNI_BU_YERGA_QOYING"


# ==========================
# ADMIN ID
# ==========================
ADMIN_ID = 123456789   # o'zingizning Telegram ID


# ==========================
# USERS DATABASE
# ==========================
USERS_FILE = "users.txt"


def save_user(user_id):

    if not os.path.exists(USERS_FILE):
        open(USERS_FILE, "w").close()

    with open(USERS_FILE, "r") as f:
        users = f.read().splitlines()

    if str(user_id) not in users:
        with open(USERS_FILE, "a") as f:
            f.write(str(user_id) + "\n")


# ==========================
# EXCEL
# ==========================
df = pd.read_excel("pvz.xlsx")
df.columns = ["address", "pvz_name", "latitude", "longitude"]


# ==========================
# TEXT TOZALASH
# ==========================
def normalize(text):
    return (
        str(text)
        .upper()
        .replace(" ", "")
        .replace("-", "")
    )


# ==========================
# START
# ==========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    save_user(user_id)

    await update.message.reply_text(
        "Bot ishga tushdi."
    )


# ==========================
# BROADCAST
# ==========================
async def send_all(context, text):

    if not os.path.exists(USERS_FILE):
        return 0

    with open(USERS_FILE, "r") as f:
        users = f.read().splitlines()

    count = 0

    for user_id in users:

        try:
            await context.bot.send_message(
                chat_id=int(user_id),
                text=text
            )

            count += 1

        except Exception as e:
            print(user_id, e)

    return count



async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        return


    message = " ".join(context.args)

    if not message:
        await update.message.reply_text(
            "Xabar matnini yozing.\nMisol:\n/send Bugun texnik ishlar bo'ladi"
        )
        return


    count = await send_all(
        context,
        message
    )


    await update.message.reply_text(
        f"Xabar {count} ta foydalanuvchiga yuborildi."
    )


# ==========================
# SEARCH
# ==========================
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id
    save_user(user_id)


    user_text = update.message.text.strip()
    search_text = normalize(user_text)


    # ==========================
    # QR SEARCH
    # ==========================

    qr_folders = ["qr1", "qr2", "qr3"]


    for qr_folder in qr_folders:

        if not os.path.isdir(qr_folder):
            continue


        for file in os.listdir(qr_folder):

            if file.lower().endswith(".png"):

                file_name = os.path.splitext(file)[0]


                if normalize(file_name) == search_text:

                    with open(os.path.join(qr_folder, file), "rb") as photo:

                        await update.message.reply_photo(
                            photo=photo,
                            caption=f"Mashina: {file_name}"
                        )

                    return



    # ==========================
    # PVZ SEARCH
    # ==========================

    result = df[
        df["pvz_name"]
        .astype(str)
        .str.upper()
        == user_text.upper()
    ]


    if not result.empty:

        row = result.iloc[0]


        await update.message.reply_text(
            f"PVZ: {row['pvz_name']}\n\n"
            f"Manzil:\n{row['address']}"
        )


        await update.message.reply_location(
            latitude=float(row["latitude"]),
            longitude=float(row["longitude"])
        )


        return



    await update.message.reply_text(
        "Ma'lumot topilmadi."
    )


# ==========================
# MAIN
# ==========================

def main():

    app = Application.builder().token(TOKEN).build()


    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )


    app.add_handler(
        CommandHandler(
            "send",
            broadcast
        )
    )


    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            search
        )
    )


    print("Bot ishga tushdi...")


    app.run_polling()



if __name__ == "__main__":
    main()