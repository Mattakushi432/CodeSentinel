# CodeSentinel — Инструкция по запуску на локальном сервере

## Что представляет собой проект

**CodeSentinel** — self-hosted платформа AI-ревью pull request'ов. Состоит из:
- **FastAPI-приложение** (`app/`) — веб-интерфейс + API + фоновый воркер
- **SQLite** (`data/codesentinel.db`) — хранилище данных
- **Ollama** — локальный LLM-движок для AI-ревью
- **Caddy** — reverse proxy с автоматическим TLS (в Docker-варианте)

---

## Способ 1 — Docker Compose (рекомендуется для сервера)

### Требования

- Docker Engine 24+ и Docker Compose v2
- ~8 ГБ RAM (6 ГБ для Ollama, 2 ГБ для приложения и ОС)
- ~10 ГБ свободного места (модель LLM ~4.5 ГБ)

### Шаг 1 — Клонировать репозиторий

```bash
git clone https://github.com/Mattakushi432/CodeSentinel.git
cd CodeSentinel
```

### Шаг 2 — Создать файл `.env`

```bash
cp .env.example .env
```

Открыть `.env` и заполнить обязательные поля:

```dotenv
# База данных (SQLite, путь менять не нужно)
DATABASE_URL=sqlite:///./data/codesentinel.db

# Секретный ключ сессии — ОБЯЗАТЕЛЬНО сгенерировать свой
# Генерация: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=<сгенерированный-ключ>

# Публичный URL приложения (для webhook-ссылок в интерфейсе)
# При локальном запуске оставить http://localhost:8000
BASE_URL=http://localhost:8000

# LLM-провайдер (ollama — локальный, работает из коробки)
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=qwen2.5-coder:7b-instruct

# Email (необязательно для локального теста — можно оставить пустым)
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=noreply@localhost

# Stripe (необязательно — оставить пустым для локальной разработки)
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PRICE_PRO=
STRIPE_PRICE_TEAM=

# Caddy (домен — для локального теста оставить localhost)
CADDY_DOMAIN=localhost

# Режим разработки — включает /auth/dev-login и /api/docs
DEV_MODE=true

# Лимиты
MAX_DIFF_LINES=500
WORKER_POLL_INTERVAL=10
LLM_TIMEOUT=300
```

> **Важно:** `SECRET_KEY` не может быть пустым или равным `change-me-in-production` — приложение откажется стартовать.

Сгенерировать ключ:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Шаг 3 — Создать папку для данных

```bash
mkdir -p data
```

### Шаг 4 — Запустить контейнеры

```bash
docker compose up -d
```

Первый запуск занимает несколько минут — скачивается образ Ollama (~500 МБ).

### Шаг 5 — Загрузить LLM-модель в Ollama

После старта контейнеров нужно скачать модель (однократно, ~4.5 ГБ):

```bash
docker exec -it codesentinel_ollama ollama pull qwen2.5-coder:7b-instruct
```

Дождаться завершения загрузки. Проверить, что модель доступна:

```bash
docker exec -it codesentinel_ollama ollama list
```

### Шаг 6 — Проверить работоспособность

```bash
# Health-check
curl http://localhost:8000/health
# Ожидаемый ответ: {"status":"ok","version":"0.1.0"}

# Или через smoke-тест
python scripts/smoke_test.py --base-url http://localhost:8000
```

### Полезные команды Docker

```bash
# Посмотреть логи приложения
docker compose logs -f app

# Посмотреть логи Ollama
docker compose logs -f ollama

# Перезапустить только приложение
docker compose restart app

# Остановить всё
docker compose down

# Остановить и удалить volumes (полный сброс данных)
docker compose down -v
```

---

## Способ 2 — Локальный запуск без Docker (для разработки)

### Требования

- Python 3.12+
- Ollama (отдельно, см. ниже) **или** Groq API-ключ

### Шаг 1 — Клонировать и создать виртуальное окружение

```bash
git clone https://github.com/zakrevskyimaksym/CodeSentinel.git
cd CodeSentinel

python -m venv .venv
source .venv/bin/activate          # macOS/Linux
# .venv\Scripts\activate           # Windows
```

### Шаг 2 — Установить зависимости

```bash
pip install -r requirements.txt

# Для разработки (тесты, линтер)
pip install -r requirements-dev.txt
```

### Шаг 3 — Создать `.env`

```bash
cp .env.example .env
```

Для локального запуска **без Docker** изменить `OLLAMA_BASE_URL`:

```dotenv
DATABASE_URL=sqlite:///./data/codesentinel.db
SECRET_KEY=<сгенерированный-ключ>
BASE_URL=http://localhost:8000

LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434   # ← локальный Ollama, не docker-сеть
OLLAMA_MODEL=qwen2.5-coder:7b-instruct

DEV_MODE=true

SMTP_HOST=
SMTP_FROM=noreply@localhost
STRIPE_SECRET_KEY=
MAX_DIFF_LINES=500
WORKER_POLL_INTERVAL=10
LLM_TIMEOUT=300
```

### Шаг 4 — Создать папку для SQLite и применить миграции

```bash
mkdir -p data

# Применить миграции Alembic (создаёт схему БД)
alembic upgrade head
```

### Шаг 5 — Установить и запустить Ollama локально

```bash
# macOS
brew install ollama
ollama serve &                          # запустить в фоне

# Linux
curl -fsSL https://ollama.com/install.sh | sh
ollama serve &

# Загрузить модель
ollama pull qwen2.5-coder:7b-instruct
```

> **Альтернатива Ollama** — использовать Groq (облачный API, быстрее, бесплатный tier):
> ```dotenv
> LLM_PROVIDER=groq
> GROQ_API_KEY=gsk_ваш_ключ_с_console.groq.com
> ```
> Groq не требует локальной установки и работает на любом железе.

### Шаг 6 — Запустить приложение

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Флаг `--reload` включает hot-reload при изменении файлов (только для разработки).

### Шаг 7 — Проверить работоспособность

```bash
curl http://localhost:8000/health
# {"status":"ok","version":"0.1.0"}
```

При включённом `DEV_MODE=true` доступны:
- **Swagger UI:** `http://localhost:8000/api/docs`
- **Быстрый вход без email:** `http://localhost:8000/auth/dev-login?email=admin@example.com`

---

## Первоначальная настройка приложения

### 1. Войти в систему

С `DEV_MODE=true`:
```
http://localhost:8000/auth/dev-login?email=admin@example.com
```

Без dev-режима — перейти на `http://localhost:8000/auth/login` и отправить magic link на email (требует настройки SMTP).

### 2. Добавить репозиторий

Перейти в **Dashboard → Repositories → Add Repository**, указать:
- Git-хост (GitHub / GitLab / Gitea)
- URL репозитория
- Access token с правами на чтение PR и создание комментариев

После сохранения появятся **Webhook URL** и **Webhook Secret** для настройки в git-хосте.

### 3. Настроить вебхук в GitHub/GitLab/Gitea

Подробная инструкция — в [`docs/webhook_setup.md`](webhook_setup.md).

> **Для локального сервера:** вебхуки из GitHub/GitLab не достигнут `localhost`. Нужен публичный URL — настроить Cloudflare Tunnel (инструкция в [`docs/cloudflare_tunnel.md`](cloudflare_tunnel.md)) или временно использовать ngrok:
> ```bash
> ngrok http 8000
> # Скопировать HTTPS-URL вида https://abc123.ngrok.io
> # Обновить BASE_URL в .env на этот URL
> ```

---

## Запуск тестов

```bash
# Активировать виртуальное окружение
source .venv/bin/activate

# Все тесты с покрытием
pytest --cov=app --cov-report=term-missing

# Конкретный файл
pytest tests/test_webhooks.py -v

# Smoke-тест против работающего сервера
python scripts/smoke_test.py --base-url http://localhost:8000
```

---

## Структура данных

```
data/
└── codesentinel.db     # SQLite база (создаётся автоматически)
```

База создаётся при первом запуске через `init_db()` в lifespan-хуке. При использовании Alembic — применять `alembic upgrade head` перед стартом.

---

## Типичные проблемы

### `SECRET_KEY must not be the default placeholder`
Сгенерировать и прописать ключ в `.env`:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Ollama недоступен / таймаут LLM
- Docker: проверить `docker compose logs ollama`, убедиться что модель загружена (`docker exec codesentinel_ollama ollama list`)
- Локально: убедиться что `ollama serve` запущен и `OLLAMA_BASE_URL=http://localhost:11434`

### `CSRF validation failed` при форм-сабмитах
`BASE_URL` в `.env` должен совпадать с тем URL, по которому открыт браузер (включая порт).

### Порт 80/443 занят (Docker + Caddy)
Либо остановить конкурирующий процесс, либо изменить порты в `docker-compose.yml`:
```yaml
ports:
  - "8080:80"
  - "8443:443"
```

### Миграции не применились
```bash
alembic upgrade head
# Или в Docker
docker exec codesentinel_app alembic upgrade head
```
