# Telegram-бот дней рождения сотрудников

Бот каждый день проверяет опубликованную Google-таблицу и отправляет сообщение в Telegram, если у сотрудника сегодня день рождения.

## Формат таблицы

Обязательные колонки:

- №
- Имя
- Подразделение
- Дата

Дата должна быть в формате `03.04`, `17.07`, `01.10`.

## Railway

После деплоя можно ничего не настраивать: токен, chat_id и ссылка на таблицу уже прописаны в `main.py`.

Но правильнее добавить Variables в Railway:

```text
BOT_TOKEN=токен бота
CHAT_ID=8570214747
SHEET_URL=https://docs.google.com/spreadsheets/d/e/2PACX-1vQpQ4OyVmG2D79k72MjzAzNedczh6Y7dEnQAnSEdLKPA8mShW-IoAIzCOAKtdrSP0PDEyJo36RJipP5/pubhtml
TIMEZONE=Europe/Moscow
SEND_HOUR=9
SEND_MINUTE=0
```

## Как запустить локально

```bash
pip install -r requirements.txt
python main.py
```
