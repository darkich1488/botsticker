# Emoji Pack Bot (aiogram 3)

Telegram-бот для сборки emoji pack из Lottie-шаблонов.

## Локальный запуск

1. Установите зависимости:

```bash
pip install -r requirements.txt
```

2. Создайте `.env` из примера и заполните значения:

```bash
cp .env.example .env
```

3. Запустите бота:

```bash
python -m app.bot
```

## Railway деплой (секреты отдельно)

1. Создайте проект на Railway и подключите репозиторий.
2. В `Settings -> Variables` добавьте переменные из `.env.railway.example`.
3. Важно: реальные секреты (`BOT_TOKEN`) храните только в Railway Variables, не в git.
4. Railway автоматически поднимет процесс из `Procfile`:

```text
worker: python -m app.bot
```

### Обязательные переменные

- `BOT_TOKEN`
- `ADMIN_USER_IDS` (например `925896498`)
- `PRICE_PER_TEMPLATE` (сейчас `3.0`)

## Админ-функции

- Админ ID задается через `ADMIN_USER_IDS`.
- Для админа генерация бесплатная.
- Кнопка `📣 Рассылка` доступна только админу.
- Рассылка поддерживает текст и фото с подписью.
