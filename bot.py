import os
import re
import pandas as pd

from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    ContextTypes,
    filters
)


# =========================================================
# TOKEN
# Railway -> Variables -> BOT_TOKEN
# =========================================================

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi!")


# =========================================================
# EXCEL
# =========================================================

EXCEL_FILE = "pvz.xlsx"

df = pd.read_excel(EXCEL_FILE)


# Excel ustunlarini avtomatik aniqlash
def find_column(possible_names):
    for col in df.columns:
        col_clean = str(col).strip().lower()

        for name in possible_names:
            if name in col_clean:
                return col

    return None


PVZ_COLUMN = find_column([
    "pvz nomi",
    "pvz_name",
    "pvz",
    "название пвз"
])

ADDRESS_COLUMN = find_column([
    "manzil",
    "address",
    "адрес"
])

COORDINATE_COLUMN = find_column([
    "latitude, longitude",
    "latitude longitude",
    "coordinates",
    "coordinate",
    "koordinata",
    "координаты",
    "lat long",
    "lat, long"
])

PHONE_COLUMN = find_column([
    "telefon",
    "phone",
    "телефон"
])

TELEGRAM_COLUMN = find_column([
    "telegram",
    "telegram user",
    "telegram username",
    "telegram_user",
    "телеграм"
])


# Agar koordinata ikkita alohida ustunda bo'lsa
LATITUDE_COLUMN = find_column([
    "latitude",
    "широта"
])

LONGITUDE_COLUMN = find_column([
    "longitude",
    "долгота"
])


if PVZ_COLUMN is None:
    raise RuntimeError(
        "Excel'da PVZ nomi ustuni topilmadi!"
    )


# =========================================================
# KIRILL -> LOTIN
# LOTIN -> KIRILL bilan bir xil qidirish uchun
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


def normalize(text):
    """
    PVZ nomini qidiruv uchun standart ko'rinishga keltiradi.

    Misollar:

    FrТАШ-417 -> TASH417
    tash417   -> TASH417
    таш417    -> TASH417
    ТАШ-417   -> TASH417
    frtash417 -> TASH417
    """

    if text is None:
        return ""

    text = str(text).upper().strip()

    # Kirill harflarini lotinga o'tkazish
    result = ""

    for char in text:
        if char in CYRILLIC_TO_LATIN:
            result += CYRILLIC_TO_LATIN[char]
        else:
            result += char

    text = result

    # FR prefiksini olib tashlash
    if text.startswith("FR"):
        text = text[2:]

    # Faqat harf va raqamlarni qoldirish
    text = re.sub(r"[^A-Z0-9]", "", text)

    return text


# =========================================================
# COORDINATE
# =========================================================

def get_coordinates(row):
    """
    Koordinatalar:

    1) Bitta ustunda:
       41.311081, 69.240562

    yoki

       41.311081 69.240562

    yoki

       41.311081;69.240562

    2) Alohida ustunlarda:
       Latitude
       Longitude
    """

    # Avval alohida Latitude / Longitude
    if LATITUDE_COLUMN and LONGITUDE_COLUMN:

        try:
            lat = float(str(row[LATITUDE_COLUMN]).replace(",", "."))
            lon = float(str(row[LONGITUDE_COLUMN]).replace(",", "."))

            return lat, lon

        except (ValueError, TypeError):
            pass

    # Bitta koordinata ustuni
    if COORDINATE_COLUMN:

        value = str(row[COORDINATE_COLUMN]).strip()

        # Vergul, nuqtali vergul yoki bo'sh joy orqali
        numbers = re.findall(
            r"-?\d+(?:[.,]\d+)?",
            value
        )

        if len(numbers) >= 2:

            try:
                lat = float(numbers[0].replace(",", "."))
                lon = float(numbers[1].replace(",", "."))

                return lat, lon

            except ValueError:
                pass

    return None, None


# =========================================================
# PVZ QIDIRISH
# =========================================================

def search_rows(user_text):

    search_value = normalize(user_text)

    if not search_value:
        return pd.DataFrame()

    normalized_names = df[PVZ_COLUMN].apply(normalize)

    # 1. Avval aniq match
    exact = df[
        normalized_names == search_value
    ]

    if not exact.empty:
        return exact

    # 2. Agar aniq topilmasa, qisman qidirish
    partial = df[
        normalized_names.str.contains(
            search_value,
            na=False
        )
    ]

    return partial


# =========================================================
# PVZ HAQIDA MA'LUMOT
# =========================================================

def get_value(row, column, default="Ma'lumot mavjud emas"):

    if column is None:
        return default

    value = row.get(column)

    if pd.isna(value):
        return default

    value = str(value).strip()

    if not value:
        return default

    return value


# =========================================================
# TELEGRAM USER
# =========================================================

def format_telegram(value):

    if value is None:
        return "Ma'lumot mavjud emas"

    value = str(value).strip()

    if not value or value.lower() == "nan":
        return "Ma'lumot mavjud emas"

    # Agar @ yozilmagan bo'lsa
    if not value.startswith("@"):
        value = "@" + value

    return value


# =========================================================
# PVZ QIDIRUV HANDLER
# =========================================================

async def search_pvz(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    user_text = update.message.text.strip()

    if not user_text:
        return

    results = search_rows(user_text)

    # -----------------------------------------------------
    # TOPILMADI
    # -----------------------------------------------------

    if results.empty:

        await update.message.reply_text(
            "❌ PVZ topilmadi.\n\n"
            f"Qidirilgan: {user_text}"
        )

        return

    # -----------------------------------------------------
    # BIR NECHTA PVZ
    # -----------------------------------------------------

    if len(results) > 1:

        names = []

        for _, row in results.head(10).iterrows():

            name = get_value(
                row,
                PVZ_COLUMN,
                "Noma'lum PVZ"
            )

            names.append(f"• {name}")

        await update.message.reply_text(
            "🔎 Bir nechta PVZ topildi:\n\n"
            + "\n".join(names)
            + "\n\nAniqroq PVZ nomini yozing."
        )

        return

    # -----------------------------------------------------
    # BIRTA PVZ
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

    telegram_user = format_telegram(
        get_value(
            row,
            TELEGRAM_COLUMN,
            ""
        )
    )

    # -----------------------------------------------------
    # MATN
    # -----------------------------------------------------

    message = (
        f"📍 PVZ: {pvz_name}\n\n"
        f"🏠 Manzil:\n{address}\n\n"
        f"📞 Telefon:\n{phone}\n\n"
        f"💬 Telegram:\n{telegram_user}"
    )

    await update.message.reply_text(message)

    # -----------------------------------------------------
    # LOCATION
    # -----------------------------------------------------

    latitude, longitude = get_coordinates(row)

    if latitude is not None and longitude is not None:

        try:

            await update.message.reply_location(
                latitude=latitude,
                longitude=longitude
            )

        except Exception as e:

            print(
                f"Lokatsiya yuborishda xato: {e}"
            )

    else:

        await update.message.reply_text(
            "⚠️ Ushbu PVZ uchun koordinata topilmadi."
        )


# =========================================================
# BOT
# =========================================================

app = (
    Application
    .builder()
    .token(TOKEN)
    .build()
)


app.add_handler(
    MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        search_pvz
    )
)


print("Bot ishga tushdi...")

app.run_polling()
