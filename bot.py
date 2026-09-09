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
# =========================================================

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi!")


# =========================================================
# EXCEL
# =========================================================

EXCEL_FILE = "pvz.xlsx"

df = pd.read_excel(EXCEL_FILE)

# Excel ustun nomlarini tozalash
df.columns = [
    str(col).strip()
    for col in df.columns
]


print("Excel ustunlari:")
print(list(df.columns))


# =========================================================
# USTUNNI TOPISH
# =========================================================

def find_column(keywords):

    for column in df.columns:

        column_name = str(column).strip().lower()

        for keyword in keywords:

            if keyword.lower() in column_name:
                return column

    return None


# PVZ nomi
PVZ_COLUMN = find_column([
    "pvz nomi",
    "pvz_nomi",
    "pvz name",
    "pvz_name",
    "название пвз",
    "пвз",
])


# Manzil
ADDRESS_COLUMN = find_column([
    "manzil",
    "address",
    "адрес",
])


# Telefon
PHONE_COLUMN = find_column([
    "telefon",
    "phone",
    "телефон",
    "tel",
])


# Telegram
TELEGRAM_COLUMN = find_column([
    "telegram",
    "telegram user",
    "telegram username",
    "telegram_user",
    "telegram username",
])


# Bitta ustundagi koordinata
COORDINATE_COLUMN = find_column([
    "latitude, longitude",
    "latitude longitude",
    "coordinates",
    "coordinate",
    "koordinata",
    "координаты",
    "lat long",
    "lat, long",
])


# Alohida latitude
LATITUDE_COLUMN = find_column([
    "latitude",
    "широта",
])


# Alohida longitude
LONGITUDE_COLUMN = find_column([
    "longitude",
    "долгота",
])


# =========================================================
# TEKSHIRISH
# =========================================================

if PVZ_COLUMN is None:

    # Agar PVZ ustuni topilmasa, ustunlarni ko'rsatadi
    raise RuntimeError(
        "PVZ ustuni topilmadi!\n"
        f"Excel ustunlari: {list(df.columns)}"
    )


print("PVZ_COLUMN =", PVZ_COLUMN)
print("ADDRESS_COLUMN =", ADDRESS_COLUMN)
print("PHONE_COLUMN =", PHONE_COLUMN)
print("TELEGRAM_COLUMN =", TELEGRAM_COLUMN)
print("COORDINATE_COLUMN =", COORDINATE_COLUMN)
print("LATITUDE_COLUMN =", LATITUDE_COLUMN)
print("LONGITUDE_COLUMN =", LONGITUDE_COLUMN)


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
# NORMALIZE
# =========================================================

def normalize(text):

    if text is None:
        return ""

    text = str(text).upper().strip()

    result = ""

    for char in text:

        if char in CYRILLIC_TO_LATIN:
            result += CYRILLIC_TO_LATIN[char]

        else:
            result += char

    text = result

    # FR ni olib tashlash
    if text.startswith("FR"):
        text = text[2:]

    # Faqat harf va raqamlar
    text = re.sub(
        r"[^A-Z0-9]",
        "",
        text
    )

    return text


# =========================================================
# VALUE
# =========================================================

def get_value(
    row,
    column,
    default="Ma'lumot mavjud emas"
):

    if column is None:
        return default

    try:
        value = row[column]

    except Exception:
        return default

    if pd.isna(value):
        return default

    value = str(value).strip()

    if not value or value.lower() == "nan":
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

    if not value.startswith("@"):
        value = "@" + value

    return value


# =========================================================
# KOORDINATA
# =========================================================

def get_coordinates(row):

    # -----------------------------------------------------
    # 1. Alohida Latitude / Longitude
    # -----------------------------------------------------

    if (
        LATITUDE_COLUMN is not None
        and
        LONGITUDE_COLUMN is not None
    ):

        try:

            lat_text = str(
                row[LATITUDE_COLUMN]
            ).replace(",", ".")

            lon_text = str(
                row[LONGITUDE_COLUMN]
            ).replace(",", ".")

            lat = float(lat_text)
            lon = float(lon_text)

            return lat, lon

        except Exception:
            pass


    # -----------------------------------------------------
    # 2. Bitta ustunda koordinata
    # -----------------------------------------------------

    if COORDINATE_COLUMN is not None:

        value = str(
            row[COORDINATE_COLUMN]
        ).strip()

        # Masalan:
        # 41.311081, 69.240562
        #
        # yoki:
        # 41.311081 69.240562
        #
        # yoki:
        # 41.311081;69.240562

        numbers = re.findall(
            r"-?\d+(?:[.,]\d+)?",
            value
        )

        if len(numbers) >= 2:

            try:

                latitude = float(
                    numbers[0].replace(",", ".")
                )

                longitude = float(
                    numbers[1].replace(",", ".")
                )

                return latitude, longitude

            except Exception:
                pass


    return None, None


# =========================================================
# PVZ QIDIRISH
# =========================================================

def search_pvz_rows(user_text):

    search_value = normalize(
        user_text
    )

    if not search_value:
        return pd.DataFrame()

    normalized_names = df[
        PVZ_COLUMN
    ].fillna("").apply(normalize)


    # -----------------------------------------------------
    # 1. ANIQ MATCH
    # -----------------------------------------------------

    exact = df[
        normalized_names == search_value
    ]

    if not exact.empty:
        return exact


    # -----------------------------------------------------
    # 2. QISMAN MATCH
    # -----------------------------------------------------

    partial = df[
        normalized_names.str.contains(
            search_value,
            na=False,
            regex=False
        )
    ]

    return partial


# =========================================================
# SEARCH HANDLER
# =========================================================

async def search_pvz(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if not update.message.text:
        return

    user_text = (
        update.message.text
        .strip()
    )

    if not user_text:
        return


    results = search_pvz_rows(
        user_text
    )


    # =====================================================
    # TOPILMADI
    # =====================================================

    if results.empty:

        await update.message.reply_text(
            "❌ PVZ topilmadi.\n\n"
            f"Qidiruv: {user_text}"
        )

        return


    # =====================================================
    # BIR NECHTA NATIJA
    # =====================================================

    if len(results) > 1:

        text = "🔎 Bir nechta PVZ topildi:\n\n"

        for _, row in results.head(10).iterrows():

            name = get_value(
                row,
                PVZ_COLUMN,
                "Noma'lum"
            )

            text += f"• {name}\n"

        text += (
            "\nIltimos, aniqroq PVZ nomini yozing."
        )

        await update.message.reply_text(
            text
        )

        return


    # =====================================================
    # BITTA PVZ
    # =====================================================

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
        get_value(
            row,
            TELEGRAM_COLUMN,
            ""
        )
    )


    # =====================================================
    # MA'LUMOT
    # =====================================================

    message = (
        f"📍 PVZ: {pvz_name}\n\n"
        f"🏠 Manzil:\n"
        f"{address}\n\n"
        f"📞 Telefon:\n"
        f"{phone}\n\n"
        f"💬 Telegram:\n"
        f"{telegram}"
    )


    await update.message.reply_text(
        message
    )


    # =====================================================
    # LOCATION
    # =====================================================

    latitude, longitude = get_coordinates(
        row
    )


    if (
        latitude is not None
        and
        longitude is not None
    ):

        try:

            await update.message.reply_location(
                latitude=latitude,
                longitude=longitude
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
