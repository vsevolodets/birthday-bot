import os
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from io import StringIO

import pandas as pd
import requests


# Лучше потом заменить токен в Railway через Variables.
BOT_TOKEN = os.getenv("BOT_TOKEN", "8897637264:AAEA3WAXbOTKh3H4vd0o3FdAk1fWrL62WOo")
CHAT_IDS = os.getenv("CHAT_IDS", "8570214747,115023072")

# Публичная ссылка на таблицу. Бот сам превращает pubhtml в CSV.
SHEET_URL = os.getenv(
    "SHEET_URL",
    "https://docs.google.com/spreadsheets/d/e/2PACX-1vQpQ4OyVmG2D79k72MjzAzNedczh6Y7dEnQAnSEdLKPA8mShW-IoAIzCOAKtdrSP0PDEyJo36RJipP5/pubhtml",
)

TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")
SEND_HOUR = int(os.getenv("SEND_HOUR", "10"))
SEND_MINUTE = int(os.getenv("SEND_MINUTE", "0"))

# За сколько дней заранее напоминать о ДР.
REMIND_DAYS_BEFORE = int(os.getenv("REMIND_DAYS_BEFORE", "1"))

# 0 = понедельник, 1 = вторник, ..., 6 = воскресенье.
WEEKLY_DIGEST_WEEKDAY = int(os.getenv("WEEKLY_DIGEST_WEEKDAY", "0"))


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

    # Если дата пришла как 03.04, 3.04 или 03.04.1999
    if "." in text:
        parts = text.split(".")
        if len(parts) >= 2:
            day = parts[0].strip().zfill(2)
            month = parts[1].strip().zfill(2)
            return f"{day}.{month}"

    # Если дата пришла как полноценная дата
    parsed = pd.to_datetime(text, dayfirst=True, errors="coerce")
    if not pd.isna(parsed):
        return parsed.strftime("%d.%m")

    return text


def load_rows() -> pd.DataFrame:
    csv_url = make_csv_url(SHEET_URL)
    response = requests.get(csv_url, timeout=30)
    response.raise_for_status()
    response.encoding = "utf-8"

    df = pd.read_csv(StringIO(response.text))
    df.columns = [str(col).strip() for col in df.columns]
    return df


def get_people() -> list[dict]:
    df = load_rows()

    required_columns = {"Имя", "Подразделение", "Дата"}
    missing = required_columns - set(df.columns)

    if missing:
        raise ValueError(f"В таблице не найдены колонки: {', '.join(missing)}")

    people = []

    for _, row in df.iterrows():
        name = str(row.get("Имя", "")).strip()
        department = str(row.get("Подразделение", "")).strip()
        date = normalize_date(row.get("Дата", ""))

        if name and date:
            people.append(
                {
                    "name": name,
                    "department": department,
                    "date": date,
                }
            )

    return people


def get_people_by_date(people: list[dict], target_date: datetime) -> list[dict]:
    target = target_date.strftime("%d.%m")
    return [person for person in people if person["date"] == target]


def get_people_for_week(people: list[dict], start_date: datetime) -> list[dict]:
    week_dates = {
        (start_date + timedelta(days=i)).strftime("%d.%m")
        for i in range(7)
    }

    result = [person for person in people if person["date"] in week_dates]

    return sorted(
        result,
        key=lambda person: datetime.strptime(person["date"], "%d.%m").strftime("%m%d"),
    )


def send_message(text: str):
    for chat_id in CHAT_IDS.split(","):
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": chat_id.strip(),
                "text": text,
                "parse_mode": "HTML",
            },
            timeout=30,
        ).raise_for_status()


def build_today_message(birthdays: list[dict]) -> str | None:
    if not birthdays:
        return None

    if len(birthdays) == 1:
        person = birthdays[0]
        department = person["department"] or "без подразделения"

        return (
            "🎂 <b>Сегодня день рождения!</b>\n\n"
            f"🎉 {person['name']}\n"
            f"📁 {department}\n\n"
            "Поздравьте коллегу!"
        )

    lines = ["🎂 <b>Сегодня день рождения празднуют:</b>", ""]

    for person in birthdays:
        department = person["department"] or "без подразделения"
        lines.append(f"🎉 {person['name']} — {department}")

    lines.append("")
    lines.append("Поздравьте коллег!")

    return "\n".join(lines)


def build_reminder_message(upcoming: list[dict], target_date: datetime) -> str | None:
    if not upcoming:
        return None

    target = target_date.strftime("%d.%m")

    lines = [
        f"🎈 <b>Через {REMIND_DAYS_BEFORE} дня день рождения:</b> {target}",
        "",
    ]

    for person in upcoming:
        department = person["department"] or "без подразделения"
        lines.append(f"• {person['name']} — {department}")

    return "\n".join(lines)


def build_weekly_message(weekly_birthdays: list[dict]) -> str | None:
    if not weekly_birthdays:
        return None

    lines = ["📅 <b>Дни рождения на этой неделе:</b>", ""]

    for person in weekly_birthdays:
        department = person["department"] or "без подразделения"
        lines.append(f"• {person['date']} — {person['name']} — {department}")

    return "\n".join(lines)


def run_daily_check():
    now = datetime.now(ZoneInfo(TIMEZONE))
    people = get_people()

    messages = []

    # 1. День рождения сегодня
    today_birthdays = get_people_by_date(people, now)
    today_message = build_today_message(today_birthdays)

    if today_message:
        messages.append(today_message)

    # 2. Напоминание за 3 дня
    reminder_date = now + timedelta(days=REMIND_DAYS_BEFORE)
    upcoming_birthdays = get_people_by_date(people, reminder_date)
    reminder_message = build_reminder_message(upcoming_birthdays, reminder_date)

    if reminder_message:
        messages.append(reminder_message)

    # 3. Недельный список по понедельникам
    if now.weekday() == WEEKLY_DIGEST_WEEKDAY:
        weekly_birthdays = get_people_for_week(people, now)
        weekly_message = build_weekly_message(weekly_birthdays)

        if weekly_message:
            messages.append(weekly_message)

    for message in messages:
        send_message(message)

    if not messages:
        print("Сегодня уведомлений нет.")


def main():
    last_sent_date = None

    send_message("✅ Бот дней рождения запущен. Уведомления будут приходить в 09:00 по Москве.")

    while True:
        now = datetime.now(ZoneInfo(TIMEZONE))
        today_key = now.strftime("%Y-%m-%d")

        if (
            now.hour == SEND_HOUR
            and now.minute >= SEND_MINUTE
            and last_sent_date != today_key
        ):
            run_daily_check()
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
