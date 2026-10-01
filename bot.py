import os
import re
import pandas as pd

from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters,
)

# =========================================================
# SOZLAMALAR
# =========================================================

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError(
        "BOT_TOKEN topilmadi! Railway/Render Variables bo'limiga BOT_TOKEN qo'shing."
    )

EXCEL_FILE = "pvz.xlsx"


# =========================================================
# EXCEL FAYLNI O'QISH
# =========================================================

df = pd.read_excel(EXCEL_FILE, header=None)

# Excel ustunlari:
# 0 = Manzil
# 1 = PVZ nomi
# 2 = Telefon
# 3 = Telegram
# 4 = Koordinata

ADDRESS_COLUMN = 0
PVZ_COLUMN = 1
PHONE_COLUMN = 2
TELEGRAM_COLUMN = 3
COORDINATE_COLUMN = 4


# =========================================================
# KIRILL -> LOTIN
# =========================================================

CYRILLIC_TO_LATIN = {
    "А": "A",
    "Б": "B",
    "В": "V",
    "Г": "G",
    "Д": "D",
    "Е": "E",
    "Ё": "YO",
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
    "Ц": "TS",
    "Ч": "CH",
    "Ш": "SH",
    "Щ": "SH",
    "Ъ": "",
    "Ы": "Y",
    "Ь": "",
    "Э": "E",
    "Ю": "YU",
    "Я": "YA",

    "Қ": "Q",
    "Ғ": "G",
    "Ў": "O",
    "Ҳ": "H",

    "қ": "Q",
    "ғ": "G",
    "ў": "O",
    "ҳ": "H",
}


# =========================================================
# MATNNI NORMALIZATSIYA
# =========================================================

def normalize(text):
    if text is None or pd.isna(text):
        return ""

    text = str(text).upper().strip()

    result = []

    for char in text:
        result.append(
            CYRILLIC_TO_LATIN.get(char, char)
        )

    text = "".join(result)

    # Masalan:
    # FrTASH-417 -> TASH417
    if text.startswith("FR"):
        text = text[2:]

    # TASH-417 -> TASH417
    # TASH 417 -> TASH417
    # TASH_417 -> TASH417
    text = re.sub(r"[^A-Z0-9]", "", text)

    return text


# =========================================================
# EXCELDAN QIYMAT OLISH
# =========================================================

def get_value(row, column):
    try:
        value = row.iloc[column]
    except Exception:
        return "Ma'lumot mavjud emas"

    if pd.isna(value):
        return "Ma'lumot mavjud emas"

    value = str(value).strip()

    if not value:
        return "Ma'lumot mavjud emas"

    return value


# =========================================================
# TELEGRAM USERNAME
# =========================================================

def format_telegram(value):
    if value is None or pd.isna(value):
        return "Ma'lumot mavjud emas"

    value = str(value).strip()

    if not value or value.lower() == "nan":
        return "Ma'lumot mavjud emas"

    if not value.startswith("@"):
        value = "@" + value

    return value


# =========================================================
# KOORDINATALARNI OLISH
# =========================================================

def get_coordinates(row):
    try:
        value = row.iloc[COORDINATE_COLUMN]

        if pd.isna(value):
            return None, None

        value = str(value).strip()

        # Masalan:
        # 41.294427, 69.212664
        numbers = re.findall(
            r"-?\d+(?:[.,]\d+)?",
            value
        )

        if len(numbers) < 2:
            return None, None

        latitude = float(
            numbers[0].replace(",", ".")
        )

        longitude = float(
            numbers[1].replace(",", ".")
        )

        # Noto'g'ri koordinatalarni yubormaslik
        if not (-90 <= latitude <= 90):
            return None, None

        if not (-180 <= longitude <= 180):
            return None, None

        return latitude, longitude

    except Exception as error:
        print("Koordinata xatosi:", error)

        return None, None


# =========================================================
# PVZ QIDIRISH
# =========================================================

def search_pvz_rows(user_text):
    search_value = normalize(user_text)

    if not search_value:
        return pd.DataFrame()

    normalized_names = (
        df[PVZ_COLUMN]
        .fillna("")
        .apply(normalize)
    )

    # Avval aniq qidiruv
    exact = df[
        normalized_names == search_value
    ]

    if not exact.empty:
        return exact

    # Keyin qisman qidiruv
    partial = df[
        normalized_names.str.contains(
            search_value,
            na=False,
            regex=False
        )
    ]

    return partial


# =========================================================
# /START KOMANDASI
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    await update.message.reply_text(
        "👋 Assalomu alaykum!\n\n"
        "📍 PVZ ma'lumotlarini topish uchun "
        "PVZ nomi yoki kodini yuboring.\n\n"
        "Masalan:\n"
        "TASH417"
    )


# =========================================================
# PVZ QIDIRUV FUNKSIYASI
# =========================================================

async def search_pvz(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if not update.message.text:
        return

    user_text = update.message.text.strip()

    if not user_text:
        return

    print(f"Qidiruv: {user_text}")

    # -----------------------------------------------------
    # QIDIRUV
    # -----------------------------------------------------

    results = search_pvz_rows(user_text)

    # -----------------------------------------------------
    # PVZ TOPILMADI
    # -----------------------------------------------------

    if results.empty:

        await update.message.reply_text(
            "❌ PVZ topilmadi.\n\n"
            f"Qidiruv: {user_text}"
        )

        return

    # -----------------------------------------------------
    # BIR NECHTA PVZ TOPILDI
    # -----------------------------------------------------

    if len(results) > 1:

        text = "🔎 Bir nechta PVZ topildi:\n\n"

        for _, row in results.head(10).iterrows():

            name = get_value(
                row,
                PVZ_COLUMN
            )

            text += f"• {name}\n"

        text += (
            "\nAniqroq PVZ nomi yoki kodini yozing."
        )

        await update.message.reply_text(text)

        return

    # -----------------------------------------------------
    # BITTA PVZ
    # -----------------------------------------------------

    row = results.iloc[0]

    pvz_name = get_value(
        row,
        PVZ_COLUMN
    )

    address = get_value(
        row,
        ADDRESS_COLUMN
    )

    phone = get_value(
        row,
        PHONE_COLUMN
    )

    telegram = format_telegram(
        row.iloc[TELEGRAM_COLUMN]
        if not pd.isna(
            row.iloc[TELEGRAM_COLUMN]
        )
        else None
    )

    # -----------------------------------------------------
    # JAVOB
    # -----------------------------------------------------

    message = (
        f"📍 PVZ: {pvz_name}\n\n"
        f"🏠 Manzil:\n{address}\n\n"
        f"📞 Telefon:\n{phone}\n\n"
        f"💬 Telegram:\n{telegram}"
    )

    await update.message.reply_text(
        message
    )

    # -----------------------------------------------------
    # LOKATSIYA
    # -----------------------------------------------------

    latitude, longitude = get_coordinates(row)

    if (
        latitude is not None
        and longitude is not None
    ):

        try:

            await update.message.reply_location(
                latitude=latitude,
                longitude=longitude
            )

            print(
                f"Location yuborildi: "
                f"{latitude}, {longitude}"
            )

        except Exception as error:

            print(
                "Location yuborishda xato:",
                error
            )

    else:

        await update.message.reply_text(
            "⚠️ Ushbu PVZ uchun "
            "lokatsiya topilmadi."
        )


# =========================================================
# XATOLARNI USHLASH
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
# BOTNI ISHGA TUSHIRISH
# =========================================================

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


# Oddiy matnlar:
# TASH417
# TASH-417
# tash 417
# va hokazo
app.add_handler(
    MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        search_pvz
    )
)


# Xatolarni ko'rsatish
app.add_error_handler(
    error_handler
)


print("Bot ishga tushdi...")

app.run_polling()
