import logging
import os
from pathlib import Path

import pandas as pd
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================================================
# SOZLAMALAR
# =========================================================

TOKEN = os.getenv("BOT_TOKEN")
EXCEL_FILE = Path("pvz.xlsx")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# =========================================================
# NORMALIZE
# =========================================================

def normalize(text):
    text = str(text).upper().strip()

    replacements = {
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

    for old, new in replacements.items():
        text = text.replace(old, new)

    # Keraksiz belgilarni bir xil qilish
    text = text.replace(" ", "")
    text = text.replace("_", "-")

    return text


# =========================================================
# EXCELNI YUKLASH
# =========================================================

def load_excel():

    if not EXCEL_FILE.exists():
        logger.error("pvz.xlsx topilmadi!")
        return None

    try:

        df = pd.read_excel(EXCEL_FILE)

        df = df.fillna("")

        # Ustun nomlarini tozalash
        df.columns = [
            str(col).strip()
            for col in df.columns
        ]

        logger.info(
            "Excel yuklandi. Qatorlar soni: %s",
            len(df)
        )

        return df

    except Exception as e:

        logger.exception(
            "Excelni o'qishda xatolik: %s",
            e
        )

        return None


# =========================================================
# START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.message is None:
        return

    await update.message.reply_text(
        "👋 Salom!\n\n"
        "PVZ nomini yuboring.\n\n"
        "Masalan:\n"
        "АНД-11\n"
        "БХР-11\n"
        "FrАНД-21"
    )


# =========================================================
# PVZ QIDIRISH
# =========================================================

async def search(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    # MUHIM!
    # Ba'zi Telegram update'larda message bo'lmaydi.
    # Shu sababli bot xato bermasligi uchun tekshiramiz.

    if update.message is None:
        return

    if update.message.text is None:
        return

    user_text = update.message.text.strip()

    if not user_text:
        await update.message.reply_text(
            "❗ PVZ nomini yuboring."
        )
        return

    logger.info(
        "Qidiruv: %s",
        user_text
    )

    # =====================================================
    # EXCEL
    # =====================================================

    df = load_excel()

    if df is None:

        await update.message.reply_text(
            "❌ pvz.xlsx faylini o'qib bo'lmadi."
        )

        return

    if df.empty:

        await update.message.reply_text(
            "❌ Excel faylida ma'lumot yo'q."
        )

        return

    # =====================================================
    # NORMALIZE USER INPUT
    # =====================================================

    search_text = normalize(user_text)

    logger.info(
        "Normalize qilingan qidiruv: %s",
        search_text
    )

    # =====================================================
    # QIDIRISH
    # =====================================================

    results = []

    for _, row in df.iterrows():

        found = False

        for value in row.values:

            if value is None:
                continue

            value_text = str(value).strip()

            if not value_text:
                continue

            normalized_value = normalize(value_text)

            if search_text in normalized_value:

                found = True
                break

        if found:
            results.append(row)

    # =====================================================
    # TOPILMADI
    # =====================================================

    if not results:

        await update.message.reply_text(
            f"❌ «{user_text}» bo'yicha PVZ topilmadi."
        )

        return

    # =====================================================
    # NATIJANI TAYYORLASH
    # =====================================================

    messages = []

    for row in results[:10]:

        lines = []

        for column in df.columns:

            value = str(row[column]).strip()

            if not value:
                continue

            if value.lower() == "nan":
                continue

            lines.append(
                f"<b>{column}:</b> {value}"
            )

        if lines:

            messages.append(
                "\n".join(lines)
            )

    # =====================================================
    # NATIJA
    # =====================================================

    if not messages:

        await update.message.reply_text(
            "❌ PVZ topildi, lekin ma'lumotni chiqarib bo'lmadi."
        )

        return

    result_text = (
        "\n\n"
        "━━━━━━━━━━━━━━━━"
        "\n\n"
    ).join(messages)

    # Telegram maksimal xabar hajmi
    if len(result_text) > 4000:

        result_text = (
            result_text[:3900]
            + "\n\n..."
        )

    await update.message.reply_text(
        result_text,
        parse_mode="HTML"
    )


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    logger.error(
        "Telegram update'da xatolik:",
        exc_info=context.error
    )


# =========================================================
# MAIN
# =========================================================

def main():

    if not TOKEN:

        raise ValueError(
            "BOT_TOKEN topilmadi! "
            "Railway Variables bo'limiga BOT_TOKEN qo'shing."
        )

    application = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

    # /start
    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    # Faqat text xabarlarni search ga yuboramiz
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            search
        )
    )

    # Error handler
    application.add_error_handler(
        error_handler
    )

    logger.info(
        "BOT ISHGA TUSHDI"
    )

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


# =========================================================
# START BOT
# =========================================================

if __name__ == "__main__":
    main()
