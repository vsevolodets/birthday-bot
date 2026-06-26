import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from io import StringIO

import pandas as pd
import requests


# Можно оставить как есть, но безопаснее потом заменить токен в Railway через Variables.
BOT_TOKEN = os.getenv("BOT_TOKEN", "8897637264:AAEA3WAXbOTKh3H4vd0o3FdAk1fWrL62WOo")
CHAT_ID = os.getenv("CHAT_ID", "8570214747")

# Публичная ссылка на таблицу. Бот сам превращает pubhtml в CSV.
SHEET_URL = os.getenv(
    "SHEET_URL",
    "https://docs.google.com/spreadsheets/d/e/2PACX-1vQpQ4OyVmG2D79k72MjzAzNedczh6Y7dEnQAnSEdLKPA8mShW-IoAIzCOAKtdrSP0PDEyJo36RJipP5/pubhtml",
)

TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")
SEND_HOUR = int(os.getenv("SEND_HOUR", "9"))
SEND_MINUTE = int(os.getenv("SEND_MINUTE", "0"))


def make_csv_url(url: str) -> str:
    if "output=csv" in url:
        return url

    if "pubhtml" in url:
        return url.replace("pubhtml", "pub?output=csv")

    if "pub?" in url and "output=" not in url:
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}output=csv"

    return url


def normalize_date(value) -> str:
    if pd.isna(value):
        return ""

    text = str(value).strip()

    # Если Google Sheets отдал дату как 03.04 или 3.04
    if "." in text:
        parts = text.split(".")
        if len(parts) >= 2:
            day = parts[0].strip().zfill(2)
            month = parts[1].strip().zfill(2)
            return f"{day}.{month}"

    # Если дата пришла в формате datetime/pandas
    parsed = pd.to_datetime(text, dayfirst=True, errors="coerce")
    if not pd.isna(parsed):
        return parsed.strftime("%d.%m")

    return text


def load_rows() -> pd.DataFrame:
    csv_url = make_csv_url(SHEET_URL)
    response = requests.get(csv_url, timeout=30)
    response.raise_for_status()

    # На случай русской таблицы Google обычно отдаёт UTF-8.
    response.encoding = "utf-8"

    df = pd.read_csv(StringIO(response.text))
    df.columns = [str(col).strip() for col in df.columns]
    return df


def get_birthdays_today():
    df = load_rows()

    required_columns = {"Имя", "Подразделение", "Дата"}
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"В таблице не найдены колонки: {', '.join(missing)}")

    today = datetime.now(ZoneInfo(TIMEZONE)).strftime("%d.%m")
    birthdays = []

    for _, row in df.iterrows():
        name = str(row.get("Имя", "")).strip()
        department = str(row.get("Подразделение", "")).strip()
        date = normalize_date(row.get("Дата", ""))

        if name and date == today:
            birthdays.append({
                "name": name,
                "department": department,
                "date": date,
            })

    return birthdays


def send_message(text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    response = requests.post(
        url,
        json={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=30,
    )
    response.raise_for_status()


def build_birthday_message(birthdays) -> str | None:
    if not birthdays:
        return None

    lines = ["🎉 <b>Сегодня день рождения:</b>", ""]

    for person in birthdays:
        department = person["department"] or "без подразделения"
        lines.append(f"• {person['name']} — {department}")

    return "\n".join(lines)


def main():
    last_sent_date = None

    send_message("✅ Бот дней рождения запущен и подключён к таблице.")

    while True:
        now = datetime.now(ZoneInfo(TIMEZONE))
        today_key = now.strftime("%Y-%m-%d")

        if (
            now.hour == SEND_HOUR
            and now.minute >= SEND_MINUTE
            and last_sent_date != today_key
        ):
            birthdays = get_birthdays_today()
            message = build_birthday_message(birthdays)

            if message:
                send_message(message)

            last_sent_date = today_key

        time.sleep(60)


if __name__ == "__main__":
    while True:
        try:
            main()
        except Exception as error:
            try:
                send_message(f"⚠️ Ошибка в боте дней рождения:\n<code>{error}</code>")
            except Exception:
                pass

            time.sleep(300)
