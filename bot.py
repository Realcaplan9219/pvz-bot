import os
import asyncio
import pandas as pd

from telegram import Update
from telegram.error import TelegramError, RetryAfter, Forbidden
from telegram.ext import (
    Application,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters,
)


# =========================================================
# BOT TOKEN
# =========================================================

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError(
        "BOT_TOKEN topilmadi! Railway Variables bo'limiga "
        "BOT_TOKEN qo'shing."
    )


# =========================================================
# ADMIN ID
# =========================================================

ADMIN_ID = 570866674


# =========================================================
# FILES
# =========================================================

USERS_FILE = "users.txt"
EXCEL_FILE = "pvz.xlsx"


# =========================================================
# USERS DATABASE
# =========================================================

def save_user(user_id: int):
    """
    Foydalanuvchi ID sini users.txt ga saqlaydi.
    """

    user_id = str(user_id)

    if not os.path.exists(USERS_FILE):
        open(USERS_FILE, "w", encoding="utf-8").close()

    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = f.read().splitlines()
    except Exception:
        users = []

    if user_id not in users:
        with open(USERS_FILE, "a", encoding="utf-8") as f:
            f.write(user_id + "\n")


# =========================================================
# CYRILLIC -> LATIN
# =========================================================

CYRILLIC_TO_LATIN = {
    "А": "A",
    "Б": "B",
    "В": "V",
    "Г": "G",
    "Д": "D",
    "Е": "E",
    "Ё": "E",
    "Ж": "J",
    "З": "Z",
    "И": "I",
    "Й": "Y",
    "К": "K",
    "Л": "L",
    "М": "M",
    "Н": "N",
    "О": "O",
    "П": "P",
    "Р": "R",
    "С": "S",
    "Т": "T",
    "У": "U",
    "Ф": "F",
    "Х": "X",
    "Ц": "C",
    "Ч": "CH",
    "Ш": "SH",
    "Щ": "SH",
    "Ъ": "",
    "Ы": "Y",
    "Ь": "",
    "Э": "E",
    "Ю": "YU",
    "Я": "YA",
}


# =========================================================
# NORMALIZE
# =========================================================

def normalize(text) -> str:
    """
    Matnni qidiruv uchun yagona ko'rinishga o'tkazadi.

    Misollar:

    ТАШ-343  -> TASH343
    таш343   -> TASH343
    TASH-343 -> TASH343
    таш 343  -> TASH343

    ЛКЧ-1    -> LKCH1
    лкч1     -> LKCH1
    LKCH-1   -> LKCH1
    """

    if text is None:
        return ""

    text = str(text).upper().strip()

    # Kirilchani lotinchaga o'tkazish
    for old, new in CYRILLIC_TO_LATIN.items():
        text = text.replace(old, new)

    # Keraksiz belgilarni olib tashlash
    text = (
        text
        .replace(" ", "")
        .replace("-", "")
        .replace("_", "")
        .replace("–", "")
        .replace("—", "")
        .replace(".", "")
        .replace("/", "")
        .replace("\\", "")
    )

    return text


# =========================================================
# NORMALIZE PVZ
# =========================================================

def normalize_pvz(text) -> str:
    """
    PVZ nomini normalize qiladi.

    FrТАШ-343 -> TASH343
    TASH-343  -> TASH343
    таш343    -> TASH343
    frtash343 -> TASH343
    """

    text = normalize(text)

    # Fr prefiksini olib tashlash
    if text.startswith("FR"):
        text = text[2:]

    return text


# =========================================================
# LOAD EXCEL
# =========================================================

if not os.path.exists(EXCEL_FILE):
    raise FileNotFoundError(
        f"{EXCEL_FILE} topilmadi! "
        f"GitHub repository ichida {EXCEL_FILE} bo'lishi kerak."
    )


try:
    df = pd.read_excel(EXCEL_FILE)
except Exception as e:
    raise RuntimeError(
        f"{EXCEL_FILE} faylini o'qishda xatolik: {e}"
    )


# =========================================================
# CHECK EXCEL COLUMNS
# =========================================================

if len(df.columns) < 4:
    raise RuntimeError(
        "pvz.xlsx faylida kamida 4 ta ustun bo'lishi kerak:\n"
        "address | pvz_name | latitude | longitude"
    )


# Birinchi 4 ta ustunni standart nomga o'tkazamiz
df = df.iloc[:, :4].copy()

df.columns = [
    "address",
    "pvz_name",
    "latitude",
    "longitude",
]


# =========================================================
# CREATE NORMALIZED PVZ COLUMN
# =========================================================

df["pvz_normalized"] = (
    df["pvz_name"]
    .astype(str)
    .apply(normalize_pvz)
)


# =========================================================
# START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.effective_user:
        return

    user_id = update.effective_user.id

    save_user(user_id)

    await update.message.reply_text(
        "Bot ishga tushdi.\n\n"
        "PVZ nomini yuboring.\n\n"
        "Masalan:\n"
        "TASH343\n"
        "таш343\n"
        "ТАШ-343\n"
        "FrТАШ-343"
    )


# =========================================================
# BROADCAST
# =========================================================

async def send_all(
    context: ContextTypes.DEFAULT_TYPE,
    text: str
):

    if not os.path.exists(USERS_FILE):
        return 0

    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = f.read().splitlines()
    except Exception:
        return 0

    count = 0

    for user_id in users:

        if not user_id.strip():
            continue

        try:

            await context.bot.send_message(
                chat_id=int(user_id),
                text=text
            )

            count += 1

            # Telegram limitlariga tushmaslik uchun
            await asyncio.sleep(0.05)

        except RetryAfter as e:

            print(
                f"Telegram flood limit. "
                f"{e.retry_after} sekund kutamiz."
            )

            await asyncio.sleep(e.retry_after)

            try:
                await context.bot.send_message(
                    chat_id=int(user_id),
                    text=text
                )

                count += 1

            except TelegramError as retry_error:
                print(
                    f"{user_id} ga qayta yuborishda xato: "
                    f"{retry_error}"
                )

        except Forbidden:

            print(
                f"{user_id}: bot bloklangan yoki "
                f"foydalanuvchi mavjud emas."
            )

        except TelegramError as e:

            print(
                f"{user_id} ga yuborishda Telegram xatosi: {e}"
            )

        except Exception as e:

            print(
                f"{user_id} ga yuborishda noma'lum xato: {e}"
            )

    return count


# =========================================================
# /SEND
# =========================================================

async def broadcast(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.effective_user:
        return

    # Faqat admin ishlata oladi
    if update.effective_user.id != ADMIN_ID:
        return

    message = " ".join(context.args).strip()

    if not message:

        await update.message.reply_text(
            "Xabar matnini yozing.\n\n"
            "Misol:\n"
            "/send Bugun texnik ishlar bo'ladi."
        )

        return

    await update.message.reply_text(
        "Xabar yuborilmoqda..."
    )

    count = await send_all(
        context,
        message
    )

    await update.message.reply_text(
        f"Xabar {count} ta foydalanuvchiga yuborildi."
    )


# =========================================================
# QR SEARCH
# =========================================================

async def search_qr(
    update: Update,
    search_text: str
) -> bool:

    qr_folders = [
        "qr1",
        "qr2",
        "qr3",
    ]

    for qr_folder in qr_folders:

        if not os.path.isdir(qr_folder):
            continue

        try:
            files = os.listdir(qr_folder)
        except Exception as e:
            print(
                f"{qr_folder} o'qilmadi: {e}"
            )
            continue

        for file in files:

            if not file.lower().endswith(".png"):
                continue

            file_name = os.path.splitext(file)[0]

            normalized_file_name = normalize(
                file_name
            )

            if normalized_file_name == search_text:

                file_path = os.path.join(
                    qr_folder,
                    file
                )

                try:

                    with open(
                        file_path,
                        "rb"
                    ) as photo:

                        await update.message.reply_photo(
                            photo=photo,
                            caption=f"Mashina: {file_name}"
                        )

                    return True

                except Exception as e:

                    print(
                        f"QR yuborishda xato: {e}"
                    )

                    return False

    return False


# =========================================================
# PVZ SEARCH
# =========================================================

async def search_pvz(
    update: Update,
    user_text: str
) -> bool:

    search_text = normalize_pvz(
        user_text
    )

    if not search_text:
        return False

    # Exact matching
    result = df[
        df["pvz_normalized"] == search_text
    ]

    if result.empty:
        return False

    row = result.iloc[0]

    pvz_name = str(
        row["pvz_name"]
    )

    address = str(
        row["address"]
    )

    try:
        latitude = float(
            row["latitude"]
        )

        longitude = float(
            row["longitude"]
        )

    except (ValueError, TypeError):

        await update.message.reply_text(
            f"PVZ: {pvz_name}\n\n"
            f"Manzil:\n{address}\n\n"
            "Koordinatalar noto'g'ri."
        )

        return True

    await update.message.reply_text(
        f"PVZ: {pvz_name}\n\n"
        f"Manzil:\n{address}"
    )

    await update.message.reply_location(
        latitude=latitude,
        longitude=longitude
    )

    return True


# =========================================================
# SEARCH
# =========================================================

async def search(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.effective_user:
        return

    if not update.message:
        return

    if not update.message.text:
        return

    user_id = update.effective_user.id

    save_user(user_id)

    user_text = update.message.text.strip()

    if not user_text:
        return

    # -----------------------------------------------------
    # 1. QR SEARCH
    # -----------------------------------------------------

    normalized_qr = normalize(
        user_text
    )

    qr_found = await search_qr(
        update,
        normalized_qr
    )

    if qr_found:
        return

    # -----------------------------------------------------
    # 2. PVZ SEARCH
    # -----------------------------------------------------

    pvz_found = await search_pvz(
        update,
        user_text
    )

    if pvz_found:
        return

    # -----------------------------------------------------
    # 3. NOT FOUND
    # -----------------------------------------------------

    await update.message.reply_text(
        "Ma'lumot topilmadi."
    )


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    print(
        "BOT XATOSI:",
        context.error
    )


# =========================================================
# MAIN
# =========================================================

def main():

    print("================================")
    print("PVZ BOT ISHGA TUSHMOQDA")
    print("================================")

    print(
        f"Excel fayl: {EXCEL_FILE}"
    )

    print(
        f"PVZ soni: {len(df)}"
    )

    print(
        "BOT_TOKEN: OK"
    )

    print(
        "================================"
    )

    app = (
        Application
        .builder()
        .token(TOKEN)
        .build()
    )

    # /start
    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    # /send
    app.add_handler(
        CommandHandler(
            "send",
            broadcast
        )
    )

    # Oddiy matn
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            search
        )
    )

    # Error handler
    app.add_error_handler(
        error_handler
    )

    print(
        "Bot polling boshladi..."
    )

    app.run_polling(
        drop_pending_updates=True
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    main()
