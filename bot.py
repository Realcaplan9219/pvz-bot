import os
import re
import pandas as pd
from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi! Railway Variables bo'limiga BOT_TOKEN qo'shing.")

EXCEL_FILE = "pvz.xlsx"

# Excel'da header yo'q, ma'lumotlar to'g'ridan-to'g'ri 1-qatorдан boshlanadi.
df = pd.read_excel(EXCEL_FILE, header=None)

# Haqiqiy Excel ustunlari:
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

CYRILLIC_TO_LATIN = {
    "А": "A", "Б": "B", "В": "V", "Г": "G", "Д": "D",
    "Е": "E", "Ё": "YO", "Ж": "J", "З": "Z", "И": "I",
    "Й": "Y", "К": "K", "Л": "L", "М": "M", "Н": "N",
    "О": "O", "П": "P", "Р": "R", "С": "S", "Т": "T",
    "У": "U", "Ф": "F", "Х": "X", "Ц": "TS", "Ч": "CH",
    "Ш": "SH", "Щ": "SH", "Ъ": "", "Ы": "Y", "Ь": "",
    "Э": "E", "Ю": "YU", "Я": "YA",
    "Қ": "Q", "Ғ": "G", "Ў": "O", "Ҳ": "H",
    "қ": "Q", "ғ": "G", "ў": "O", "ҳ": "H"
}


def normalize(text):
    if text is None or pd.isna(text):
        return ""

    text = str(text).upper().strip()

    result = []
    for char in text:
        result.append(CYRILLIC_TO_LATIN.get(char, char))

    text = "".join(result)

    # FrТАШ-417 -> TASH417
    if text.startswith("FR"):
        text = text[2:]

    # TASH-417, tash 417, ТАШ-417 -> TASH417
    text = re.sub(r"[^A-Z0-9]", "", text)

    return text


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


def format_telegram(value):
    if value is None or pd.isna(value):
        return "Ma'lumot mavjud emas"

    value = str(value).strip()

    if not value or value.lower() == "nan":
        return "Ma'lumot mavjud emas"

    if not value.startswith("@"):
        value = "@" + value

    return value


def get_coordinates(row):
    try:
        value = row.iloc[COORDINATE_COLUMN]

        if pd.isna(value):
            return None, None

        value = str(value).strip()

        # Masalan: 41.294427, 69.212664
        numbers = re.findall(r"-?\d+(?:[.,]\d+)?", value)

        if len(numbers) < 2:
            return None, None

        latitude = float(numbers[0].replace(",", "."))
        longitude = float(numbers[1].replace(",", "."))

        # Noto'g'ri koordinatalarni yubormaslik
        if not (-90 <= latitude <= 90):
            return None, None

        if not (-180 <= longitude <= 180):
            return None, None

        return latitude, longitude

    except Exception as error:
        print("Koordinata xatosi:", error)
        return None, None


def search_pvz_rows(user_text):
    search_value = normalize(user_text)

    if not search_value:
        return pd.DataFrame()

    normalized_names = df[PVZ_COLUMN].fillna("").apply(normalize)

    # Avval aniq qidiruv
    exact = df[normalized_names == search_value]

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


async def search_pvz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_text = update.message.text.strip()

    if not user_text:
        return

    print(f"Qidiruv: {user_text}")

    results = search_pvz_rows(user_text)

    if results.empty:
        await update.message.reply_text(
            "❌ PVZ topilmadi.\n\n"
            f"Qidiruv: {user_text}"
        )
        return

    # Bir nechta natija bo'lsa
    if len(results) > 1:
        text = "🔎 Bir nechta PVZ topildi:\n\n"

        for _, row in results.head(10).iterrows():
            name = get_value(row, PVZ_COLUMN)
            text += f"• {name}\n"

        text += "\nAniqroq PVZ nomini yozing."

        await update.message.reply_text(text)
        return

    row = results.iloc[0]

    pvz_name = get_value(row, PVZ_COLUMN)
    address = get_value(row, ADDRESS_COLUMN)
    phone = get_value(row, PHONE_COLUMN)
    telegram = format_telegram(
        row.iloc[TELEGRAM_COLUMN]
        if not pd.isna(row.iloc[TELEGRAM_COLUMN])
        else None
    )

    message = (
        f"📍 PVZ: {pvz_name}\n\n"
        f"🏠 Manzil:\n{address}\n\n"
        f"📞 Telefon:\n{phone}\n\n"
        f"💬 Telegram:\n{telegram}"
    )

    await update.message.reply_text(message)

    latitude, longitude = get_coordinates(row)

    if latitude is not None and longitude is not None:
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
            print("Location yuborishda xato:", error)

    else:
        await update.message.reply_text(
            "⚠️ Ushbu PVZ uchun lokatsiya topilmadi."
        )


app = Application.builder().token(TOKEN).build()

app.add_handler(
    MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        search_pvz
    )
)

print("Bot ishga tushdi...")
app.run_polling()
