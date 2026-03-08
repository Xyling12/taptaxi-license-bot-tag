# TapTaxi License Bot

Telegram-бот для выдачи лицензионных кодов на патченый TapTaxi APK.

## Принцип работы

- Каждый телефон имеет уникальный `device_id`
- Водитель присылает боту свой `device_id`
- В режиме `AUTO_APPROVE=true` бот сразу высылает уникальный 16-значный код
- В режиме `AUTO_APPROVE=false` нужна ручная команда `/approve <device_id>`
- Код **детерминированный**: один телефон = всегда один код (переустановка не ломает лицензию)
- Алгоритм: `HMAC-SHA256(SECRET_KEY, device_id)[:16].upper()`

## Запуск

```bash
cp .env.example .env
# Заполни .env: BOT_TOKEN, SECRET_KEY, AUTO_APPROVE
# ADMIN_IDS нужен только если AUTO_APPROVE=false

pip install -r requirements.txt
python bot.py
```

### Docker

```bash
docker-compose up -d
```

### Dokploy (через готовый image)

После push в `main` GitHub Actions публикует образ:
`ghcr.io/xyling12/taptaxi-license-bot-tag:latest`

В Dokploy (Raw Compose) можно использовать:

```yaml
services:
  license-bot:
    image: ghcr.io/xyling12/taptaxi-license-bot-tag:latest
    restart: unless-stopped
    volumes:
      - bot_data:/app/data
    environment:
      BOT_TOKEN: ${BOT_TOKEN}
      AUTO_APPROVE: "true"
      SECRET_KEY: ${SECRET_KEY}
      DB_PATH: data/licenses.db

volumes:
  bot_data:
```

## Автотесты

```bash
python -m pytest tests/ -v
```

## Команды бота

| Команда | Кто | Описание |
|---------|-----|---------|
| (любой текст) | Водитель | Отправить device_id |
| `/approve <device_id>` | Админ | Выдать лицензию |
| `/revoke <device_id>` | Админ | Отозвать лицензию |
| `/list` | Админ | Все лицензии |
| `/gencode <device_id>` | Админ | Сгенерировать код без уведомления |

## Генерация SECRET_KEY

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

> ⚠️ **Важно:** `SECRET_KEY` должен быть одинаковым и в боте, и в APK!

## APK-сторона (следующий этап)

При запуске APK показывает поле для ввода кода.  
APK с тем же `SECRET_KEY` делает `HMAC(secret, device_id)` и сравнивает с введённым кодом.  
Реализация — через `javax.crypto.Mac` в smali.
