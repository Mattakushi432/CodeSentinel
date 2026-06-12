Фаза 0 — Зафиксированные параметры

Сервер: Intel i7 4C/8T, 16 GB RAM, GPU 1 GB (unusable for LLM — treated as CPU-only).

Критичное следствие: Local LLM inference на этом железе = ~3-5 tokens/sec. Все LLM-задачи обязаны быть асинхронными с очередью. Любой продукт, требующий real-time стриминга ответа для пользователей — не пройдёт.

Доступная RAM после OS + app + Ollama: ~6-8 GB резерва. Сервер справится, но только с одной LLM-задачей одновременно.

---
Фаза 1 — 7 Идей и Матрица Оценок

Идеи

┌─────┬────────────────────────────┬──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│  #  │          Продукт           │                                                         Суть                                                         │
├─────┼────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────┤
│ 1   │ Self-hosted AI PR Reviewer │ GitHub/GitLab/Gitea webhook → LLM анализирует diff → комментарий к PR. Дифференциатор: data never leaves your infra. │
├─────┼────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────┤
│ 2   │ AI Log Anomaly Detector    │ SIEM-лёгкий: загружаешь app logs → LLM объясняет аномалии + классифицирует ошибки. Self-hosted, async.               │
├─────┼────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────┤
│ 3   │ AI Unit Test Generator     │ Принимает Python/JS файл → генерирует пропущенные тесты. CLI + web SaaS.                                             │
├─────┼────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────┤
│ 4   │ AI Changelog Generator     │ git log → семантический changelog с группировкой по breaking/features/fixes. CLI + hosted service.                   │
├─────┼────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────┤
│ 5   │ AI Technical Doc Writer    │ Принимает codebase → генерирует README, docstrings, API docs. Async job, результат на email.                         │
├─────┼────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────┤
│ 6   │ AI SEO Content Brief       │ Keyword → SERP scraping (Brave Search API free) → структурированный бриф. B2B: SEO-агентства.                        │
├─────┼────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────┤
│ 7   │ AI Email Triage            │ IMAP → классификация → авто-черновик ответа. Async, self-hosted, privacy-first для SMB.                              │
└─────┴────────────────────────────┴─────────────────────────────────────────────────────────────────────────────────────────┘

Матрица оценок

Веса: Pain+WTP 25%, Solo-60d 20%, $0-Infra 15%, Speed-$ 20%, Clone-resist 10%,

┌──────────────────┬──────────┬──────────┬──────────┬─────────┬──────────────┬
│        #         │ Pain+WTP │ Solo-60d │ $0-Infra │ Speed-$ │ Clone-resist │ Scale │ Взвеш. балл │
├──────────────────┼──────────┼──────────┼──────────┼─────────┼──────────────┼
│ 1 AI PR Reviewer │ 8        │ 7        │ 9        │ 7       │ 8            │ 8     │ 7.75        │
├──────────────────┼──────────┼──────────┼──────────┼─────────┼──────────────┼
│ 2 Log Anomaly    │ 7        │ 5        │ 8        │ 5       │ 7            │ 8     │ 6.45        │
├──────────────────┼──────────┼──────────┼──────────┼─────────┼──────────────┼
│ 3 Test Generator │ 8        │ 7        │ 9        │ 7       │ 5            │ 7     │ 7.25        │
├──────────────────┼──────────┼──────────┼──────────┼─────────┼──────────────┼
│ 4 Changelog Gen  │ 6        │ 9        │ 9        │ 8       │ 4            │ 6     │ 7.25        │
├──────────────────┼──────────┼──────────┼──────────┼─────────┼──────────────┼
│ 5 Doc Writer     │ 7        │ 7        │ 9        │ 6       │ 5            │ 7     │ 6.90        │
├──────────────────┼──────────┼──────────┼──────────┼─────────┼──────────────┼
│ 6 SEO Brief      │ 7        │ 8        │ 7        │ 9       │ 5            │ 8     │ 7.50        │
├──────────────────┼──────────┼──────────┼──────────┼─────────┼──────────────┼
│ 7 Email Triage   │ 8        │ 5        │ 8        │ 6       │ 7            │ 8     │ 6.90        │
└──────────────────┴──────────┴──────────┴──────────┴─────────┴──────────────┴

Победитель: Идея #1 — Self-hosted AI Code Reviewer

Название продукта: CodeSentinel — "AI Code Review that runs on YOUR infrastruc

Обоснование:
- Реальный дифференциатор существует: CodeRabbit (главный конкурент) имеет щедрый free tier, но код покидает инфраструктуру клиента. Для EU/GDPR, fintech, healthcare, gov-контракторов это
 блокер.
- Async по природе: PR review — не real-time операция. 1-5 минут ожидания — норма. Это идеальный матч с медленным CPU-inference.
- Open-source as marketing: MIT-лицензия → GitHub stars → "Show HN" → органиче/Umami.
- Python-dev строит для Python/dev аудитории: не нужна экспертиза в чужой нише.
- qwen2.5-coder-7b-instruct: специализированная code-модель, ~4.5 GB RAM, exceal llama-3.1-8b для этой задачи.

3 главных риска и митигация:

┌──────────────────────────────────────────────────────────────────────┬──────────────────────────────────────────────────────────────────┐
│                                 Риск                                 │                                           Митигация                                           │
├──────────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────┤
│ CodeRabbit бесплатно для public repos → сложно продать в open-source │ Фокус на self-hosted GitLab/Gitea (нет в CodeRabbit), enterprise compliance, flat pricing     │
├──────────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────┤
│ LLM quality 7B < GPT-4 → пользователи видят "тупые" комментарии      │ Узкий промпт на конкретный язык + правила команды; показывать severity только высокий/средний │
├──────────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────┤
│ "Установи сам" — friction для покупки                                │ Предлагать cloud-hosted версию: "Start in 30 seconds without self-hosting"                    │
└──────────────────────────────────────────────────────────────────────┴──────────────────────────────────────────────────────────────────┘

---
Фаза 2 — Архитектура

C4 Level 1 — System Context

C4Context
    title CodeSentinel — System Context

    Person(dev, "Developer", "Creates PRs, reads reviews")
    Person(admin, "Team Admin", "Configures repos and rules")
    System(cs, "CodeSentinel", "Self-hosted async AI code review platform")
    System_Ext(github, "GitHub / GitLab / Gitea", "Git hosting (self-hosted or SaaS)")
    System_Ext(stripe, "Stripe", "Subscription billing (free to integrate)")
    System_Ext(smtp, "SMTP", "Transactional email (Resend free: 3k/mo)")

    Rel(github, cs, "PR webhook event (HTTPS)")
    Rel(cs, github, "Post review comment (REST API)")
    Rel(cs, stripe, "Create subscription, handle events")
    Rel(cs, smtp, "Send review notifications")
    Rel(dev, cs, "View dashboard (HTTPS)")
    Rel(admin, cs, "Configure repos, rules, billing")

C4 Level 2 — Container

C4Container
    title CodeSentinel — Container Diagram

    Person(admin, "Admin / Developer")
    System_Ext(git, "GitHub / GitLab / Gitea")
    System_Ext(stripe, "Stripe")

    Container(app, "Web Application", "FastAPI + Jinja2 + HTMX", "Dashboard, webhook handler, auth, billing")
    Container(worker, "Review Worker", "Python asyncio", "Dequeues jobs, calls
    ContainerDb(db, "Database", "SQLite → PostgreSQL (SQLAlchemy)", "Users, repos, jobs, reviews, rules")
    ContainerDb(queue, "Job Queue", "SQLite-backed (arq)", "Pending/running re
    Container(ollama, "Ollama Service", "Docker: ollama/ollama", "qwen2.5-coder-7b-instruct inference")
    Container(caddy, "Reverse Proxy", "Caddy 2", "TLS termination, routing")
    System_Ext(cf, "Cloudflare Tunnel", "cloudflared", "Exposes server without port forward")

    Rel(admin, caddy, "HTTPS")
    Rel(caddy, app, "HTTP :8000")
    Rel(git, caddy, "Webhook HTTPS")
    Rel(app, queue, "Enqueue PR job")
    Rel(worker, queue, "Dequeue job")
    Rel(worker, ollama, "POST /api/generate (HTTP :11434)")
    Rel(worker, db, "Store review result")
    Rel(worker, git, "POST review comment")
    Rel(app, db, "Read/write data")
    Rel(app, stripe, "Create checkout session")
    Rel(cf, caddy, "Tunnel")

C4 Level 3 — Review Worker Components

C4Component
    title Review Worker — Component Diagram

    Component(dispatcher, "Job Dispatcher", "asyncio loop", "Polls queue every
    Component(fetcher, "PR Fetcher", "httpx + GitHub/GitLab/Gitea clients", "Fetches diff, file list, PR metadata")
    Component(limiter, "Size Guard", "Python", "Skips diffs >500 lines; splits
    Component(prompter, "Prompt Builder", "Python", "Injects diff + org rules into system prompt")
    Component(llm_client, "LLM Client", "httpx", "Calls Ollama, retries on tim
    Component(parser, "Response Parser", "Python + regex", "Extracts JSON: [{file, line, severity, message}]")
    Component(poster, "Comment Poster", "httpx", "Formats markdown comment, PO
    Component(notifier, "Email Notifier", "smtplib", "Optional: sends summary to PR author")

    Rel(dispatcher, fetcher, "pr_url, token")
    Rel(fetcher, limiter, "raw diff")
    Rel(limiter, prompter, "filtered diff chunks")
    Rel(prompter, llm_client, "prompt string")
    Rel(llm_client, parser, "raw LLM text")
    Rel(parser, poster, "structured issues list")
    Rel(poster, notifier, "job complete event")

Trade-off таблица стека

┌───────────────────┬─────────────────────────────────────────┬─────────────────────────────┬────────────────────────────────────────────────────────────────────────────┐
│       Слой        │                  Выбор                  │        Альтерн                 Почему выбрали                               │
├───────────────────┼─────────────────────────────────────────┼─────────────────────────────┼────────────────────────────────────────────────────────────────────────────┤
│ Backend framework │ FastAPI                                 │ Django        е, не нужна ORM-магия; FastAPI + asyncio = нативная очередь   │
├───────────────────┼─────────────────────────────────────────┼─────────────────────────────┼────────────────────────────────────────────────────────────────────────────┤
│ DB (MVP)          │ SQLite (SQLAlchemy)                     │ PostgreSQL    e backup = cp, достаточно до 200+ одновременных пользователей │
├───────────────────┼─────────────────────────────────────────┼─────────────────────────────┼────────────────────────────────────────────────────────────────────────────┤
│ LLM               │ qwen2.5-coder-7b Q4_K_M                 │ codellama-7b /y/RAM trade-off для code review; 4.5 GB RAM                   │
├───────────────────┼─────────────────────────────────────────┼─────────────────────────────┼────────────────────────────────────────────────────────────────────────────┤
│ Job queue         │ arq (Redis-compatible, SQLite fallback) │ Celery/RQ     ее Celery; можно стартовать без Redis                         │
├───────────────────┼─────────────────────────────────────────┼─────────────────────────────┼────────────────────────────────────────────────────────────────────────────┤
│ Frontend          │ Jinja2 + HTMX                           │ React/Next.js о build-процесса; Python-dev сам поддерживает                 │
├───────────────────┼─────────────────────────────────────────┼─────────────────────────────┼────────────────────────────────────────────────────────────────────────────┤
│ Auth              │ Email + magic links                     │ GitHub OAuth   GitHub (нужно поддерживать Gitea/GitLab тоже)                │
├───────────────────┼─────────────────────────────────────────┼─────────────────────────────┼────────────────────────────────────────────────────────────────────────────┤
│ Reverse proxy     │ Caddy 2                                 │ Nginx         имальный конфиг (2 строки vs 20)                              │
├───────────────────┼─────────────────────────────────────────┼─────────────────────────────┼────────────────────────────────────────────────────────────────────────────┤
│ External access   │ Cloudflare Tunnel                       │ Port forwardinботает за NAT, без открытых входящих портов                   │
├───────────────────┼─────────────────────────────────────────┼─────────────────────────────┼────────────────────────────────────────────────────────────────────────────┤
│ Payments          │ Stripe                                  │ Paddle/Lemon S; 2.9%+30¢ только с транзакций                                │
├───────────────────┼─────────────────────────────────────────┼─────────────────────────────┼────────────────────────────────────────────────────────────────────────────┤
│ Container         │ Docker Compose                          │ bare metal    ty; простой переезд в облако                                  │
└───────────────────┴─────────────────────────────────────────┴─────────────────────────────┴────────────────────────────────────────────────────────────────────────────┘

ADR

ADR-001: SQLite сейчас → PostgreSQL при переезде

Решение: Использовать SQLite через SQLAlchemy с дня 1. Переход на PostgreSQL = смена DATABASE_URL без изменения кода.
Триггер миграции: >100 concurrent users ИЛИ переезд в облако (whichever first)

ADR-002: Локальный Ollama — единственный LLM provider на старте

Решение: Все inference запросы идут через абстрактный LLMClient interface. Реапереезде добавить GroqProvider / TogetherProvider без изменения логики.
Ограничение: 1 job одновременно; queue latency 1-5 min — приемлемо для async PR review.
Groq free fallback: активировать если queue > 30 pending jobs (14,400 tok/min

ADR-003: Монолит навсегда (пока не доказано иное)

Решение: FastAPI app + arq worker в одном docker-compose.yml. Один процесс сер
Запрещено: отдельные микросервисы до >1000 DAU. Kafka запрещена категорически.

ADR-004: Jinja2+HTMX вместо React/Next.js

Решение: Server-side rendering. HTMX для динамики (polling статуса job'а, live-обновление таблицы reviews).
Upgrade-триггер: пользователи требуют code editor / real-time collaboration →

ADR-005: Open-source core, paid cloud-hosted

Решение: Репозиторий MIT. Cloud-hosted версия (codesentinel.cloud) = тот же ко
Ценообразование: Free (1 repo, public only) | Pro $29/mo (5 repos) | Team $99/mo (unlimited).

ADR-006: Webhook security

Решение: Каждый подключённый репозиторий имеет уникальный webhook_secret. Все входящие webhook'и валидируются HMAC-SHA256 signature. Без signature = 401, логируется.

ADR-007: Миграция локальный сервер → облако

Шаги (нет переписывания кода):
1. Все сервисы уже в docker-compose.yml — работает локально
2. Загрузить тот же compose на Fly.io (fly launch --dockerfile docker-compose.yml) или Railway
3. DATABASE_URL=postgresql://... → SQLAlchemy автоматически переключается
4. LLM_PROVIDER=groq → GroqProvider подхватывает (уже реализован параллельно)
5. Cloudflare Tunnel → стандартный DNS CNAME на облачный IP
6. Резервная копия: sqlite-to-postgres скрипт (готовый open-source инструмент)

Целевые платформы при переезде: Fly.io ($5-15/mo), Railway ($5/mo), Render (free tier → $7/mo).

Модель данных

-- Пользователи / подписчики
users             (id, email, password_hash, plan ENUM, stripe_customer_id, cr

-- Организации (B2B unit)
organizations     (id, name, owner_id→users, plan, stripe_subscription_id, created_at)

-- Подключённые репозитории
repositories      (id, org_id→orgs, git_host ENUM(github|gitlab|gitea),
                   repo_full_name, base_url, webhook_secret, active BOOL, created_at)

-- Очередь и история review-задач
review_jobs       (id, repo_id→repos, pr_number INT, pr_title, pr_url,
                   diff_lines INT, status ENUM(pending|processing|done|error),
                   error_msg, model_used, created_at, started_at, finished_at)

-- Результаты анализа
reviews           (id, job_id→review_jobs, issues_json JSON,
                   severity_high INT, severity_med INT, severity_low INT,
                   posted_comment_id, raw_llm_output TEXT, created_at)

-- Правила проверок (кастомизация per-org)
rules             (id, org_id→orgs, name, description, prompt_snippet TEXT,
                   language VARCHAR, enabled BOOL, created_at)

-- API ключи для webhook-аутентификации
api_keys          (id, org_id→orgs, key_hash, label, created_at, last_used_at)

---
Фаза 3 — План работ с оркестрацией скилов

┌────────────────────┬───────────────────┬─────────────────────────────────────────────────────┬──────────────────────────────────────────────────┬────────────────────────────┬──────┐
│        Этап        │       Цель        │                     Deliverable                DoD                        │            Скил            │ Дней │
├────────────────────┼───────────────────┼─────────────────────────────────────────────────────┼──────────────────────────────────────────────────┼────────────────────────────┼──────┤
│                    │ Сервер готов к    │ Docker, Ollama, Caddy, Cloudflare Turdomain.com отвечает; ollama pull     │                            │      │
│ 0. Инфраструктура  │ разработке        │ Actions                                             │ qwen2.5-coder:7b-instruct ОК; CI pipeline        │ /senior-devops             │ 3    │
│                    │                   │                                                                           │                            │      │
├────────────────────┼───────────────────┼─────────────────────────────────────────────────────┼──────────────────────────────────────────────────┼────────────────────────────┼──────┤
│ 1. Скелет монолита │ Auth + DB +       │ FastAPI app в Docker; login/dashboaотает; dashboard загружается;          │ /senior-fullstack          │ 7    │
│                    │ базовые роуты     │ страницы; SQLAlchemy + SQLite; arq worker           │ docker-compose up поднимает всё                  │                            │      │
├────────────────────┼───────────────────┼───────────────────────────────────────────────────────────────────────────┼────────────────────────────┼──────┤
│ 2. Webhook + LLM   │ PR review         │ GitHub webhook handler; очередь; Ollama вызов; PR   │ Создаю PR в тест-репо → через ≤5 мин вижу review │                            │      │
│ pipeline           │ работает          │ comment                             issues                                │ /senior-backend            │ 7    │
│                    │ end-to-end        │                                                     │                                                  │                            │      │
├────────────────────┼───────────────────┼───────────────────────────────────────────────────────────────────────────┼────────────────────────────┼──────┤
│ 3. Web Dashboard   │ Конфигурация      │ Jinja2+HTMX: список repos, jobs, reviews, rules;    │ Могу добавить репо, видеть историю всех          │ /senior-frontend           │ 6    │
│ UI                 │ через браузер     │ real-time job status               редактировать правила                  │                            │      │
├────────────────────┼───────────────────┼─────────────────────────────────────────────────────┼──────────────────────────────────────────────────┼────────────────────────────┼──────┤
│ 4. Security        │ Продукт безопасен │ Threat model; webhook HMAC validatiel задокументирован; fail2ban активен; │ /senior-security →         │ 5    │
│ hardening          │  для публики      │ security; Ubuntu hardening                          │  все webhook'и валидируются                      │ /senior-secops             │      │
├────────────────────┼───────────────────┼───────────────────────────────────────────────────────────────────────────┼────────────────────────────┼──────┤
│ 5. Stripe +        │ Монетизация       │ Subscription plans Free/Pro/Team; Stripe webhook    │ Можно оформить подписку → получить доступ →      │ /senior-backend            │ 7    │
│ billing            │ работает          │ handler; usage limits по плану      downgrade работает                    │                            │      │
├────────────────────┼───────────────────┼─────────────────────────────────────────────────────┼──────────────────────────────────────────────────┼────────────────────────────┼──────┤
│ 6. Prompt          │ Review quality    │ Optimized system prompt для qwen2.5PRs reviewed → ≥7/10 issues помечены   │ /senior-prompt-engineer    │ 6    │
│ optimization       │ приемлемо         │ output schema; severity calibration                 │ корректно по severity                            │                            │      │
├────────────────────┼───────────────────┼───────────────────────────────────────────────────────────────────────────┼────────────────────────────┼──────┤
│ 7. Tests + CI      │ Нет регрессий при │ Unit tests: webhook handler, LLM client, parser;    │ >80% coverage critical paths; pytest green в CI  │ /senior-qa + /tdd-guide    │ 5    │
│                    │  деплое           │ integration test E2E; CI проверяет                                        │                            │      │
├────────────────────┼───────────────────┼─────────────────────────────────────────────────────┼──────────────────────────────────────────────────┼────────────────────────────┼──────┤
│ 8. GitLab + Gitea  │ Расширение ICP    │ Абстрактный GitHostClient интерфейс self-hosted GitLab создаёт review     │ /senior-backend            │ 6    │
│ support            │                   │ GitLabProvider; GiteaProvider                       │ comment корректно                                │                            │      │
├────────────────────┼───────────────────┼───────────────────────────────────────────────────────────────────────────┼────────────────────────────┼──────┤
│ 9. OSS + Launch    │ Публичный релиз   │ README с 1-min setup; CONTRIBUTING.md; cloud        │ Репо публичный; cloud instance на                │ /code-reviewer             │ 4    │
│ prep               │                   │ instance; код проревьюен           el.io работает; Stripe live mode       │                            │      │
├────────────────────┼───────────────────┼─────────────────────────────────────────────────────┼──────────────────────────────────────────────────┼────────────────────────────┼──────┤
│ 10. Analytics +    │ Видим что         │ Prometheus metrics (review_jobs_tot                                       │                            │      │
│ monitoring         │ происходит        │  llm_latency_seconds); Grafana dashboard; product   │ Знаем DAU, MRR, error rate в реальном времени    │ /senior-data-engineer      │ 5    │
│                    │                   │ analytics                                                                 │                            │      │
└────────────────────┴───────────────────┴─────────────────────────────────────────────────────┴──────────────────────────────────────────────────┴────────────────────────────┴──────┘

Итого: ~61 день при 40+ часах в неделю. Буфер на неожиданное: +2 недели.

---
Фаза 4 — Дорожная карта 90 дней

Недели 1–4: Строим (Days 1–28)

┌────────┬───────────────────────────────────────────────────────────────┬─────────┐
│ Неделя │                          Что строим                           │              Milestone               │
├────────┼───────────────────────────────────────────────────────────────┼─────────┤
│ 1      │ Docker, Ollama, Caddy, Cloudflare Tunnel; skелет FastAPI      │ Сервер работает внешне               │
├────────┼───────────────────────────────────────────────────────────────┼─────────┤
│ 2      │ Webhook handler + job queue + Ollama pipeline                 │ E2E review работает на тестовом репо │
├────────┼───────────────────────────────────────────────────────────────┼─────────┤
│ 3      │ Web dashboard (Jinja2/HTMX); multi-repo support               │ Можно подключить второй репо из UI   │
├────────┼───────────────────────────────────────────────────────────────┼─────────┤
│ 4      │ Security: HMAC, fail2ban, hardening; начало работы над Stripe │ Сервер hardened, billing-код начат   │
└────────┴───────────────────────────────────────────────────────────────┴─────────┘

Метрики: работает ли pipeline? error rate < 5%?

Недели 5–8: Доводим до качества (Days 29–56)

┌────────┬──────────────────────────────────────────────────────┬─────────────
│ Неделя │                      Что строим                      │              Milestone              │
├────────┼──────────────────────────────────────────────────────┼─────────────
│ 5      │ Stripe integration (checkout, webhooks, plan limits) │ Платная подписка оформляется        │
├────────┼──────────────────────────────────────────────────────┼─────────────
│ 6      │ Prompt optimization; review quality benchmark        │ 7/10 на sample PRs                  │
├────────┼──────────────────────────────────────────────────────┼─────────────
│ 7      │ Тесты; CI pipeline; GitLab support                   │ CI зелёный; GitLab webhook работает │
├────────┼──────────────────────────────────────────────────────┼─────────────
│ 8      │ Gitea support; README; 1-min self-hosted setup doc   │ Полная документация готова          │
└────────┴──────────────────────────────────────────────────────┴─────────────

День 45 — Checkpoint: Pivot / Persevere

Persevere если:
- ≥3 человека установили self-hosted версию и дали обратную связь
- GitHub stars > 30 (органика без анонса)
- Хотя бы 1 человек спросил "сколько стоит?"

Pivot-сигнал:
- Review quality стабильно плохой на всех тестах (qwen2.5-coder не справляется
- Нет интереса даже к бесплатной версии
- →Тогда: пивот на Идею #4 (AI Changelog Generator) — более простой LLM-task,

Недели 9–13: Запуск и первые деньги (Days 57–91)

┌────────┬────────────────────────────────────────────────────────────────────────────┬───────────────────────────────────────────────────────────────────┐
│ Неделя │                                                Действие                                                 │                        Ожидаемый результат                        │
├────────┼────────────────────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────┤
│ 9      │ Make repo public на GitHub; написать dev.to пост "How I built a self-hosted AI code reviewer in 60      │ 50-200 GitHub stars; 10-50 самостоятельных установок              │
│        │ days"                                                                      │                                                                   │
├────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────┤
│ 9      │ Post to r/selfhosted: "Built an open-source AI code reviewer you ca        │ 100-500 upvotes → trial users                                     │
├────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────┤
│ 10     │ Show HN: "Show HN: CodeSentinel – self-hosted AI code review, code )"      │ Если попасть в top-5: 300-1000 посещений; 3-15 trial cloud        │
│        │                                                                                                         │ signups                                                           │
├────────┼────────────────────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────┤
│ 10     │ Post to r/devops, r/programming с compliance/privacy углом                                              │ Дополнительный трафик                                             │
├────────┼────────────────────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────┤
│ 11     │ Product Hunt launch (надо готовить 1 неделю заранее: hunter, assets, timing)                            │ 200-800 upvotes если хорошо подготовлено                          │
├────────┼────────────────────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────┤
│ 11     │ Холодный outreach: 30 CTOs self-hosted GitLab компаний (поиск через GitHub API: gitlab.yml в конфигах)  │ 2-5 ответов → demo calls                                          │
├────────┼────────────────────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────┤
│ 12-13  │ Итерация по фидбеку первых пользователей                                                                │ Fix top-3 issues; improve onboarding                              │
└────────┴────────────────────────────────────────────────────────────────────────────┴───────────────────────────────────────────────────────────────────┘

Как получить первых 10 платящих пользователей (без бюджета)

1. Open-source → GitHub stars → trust. Звёзды — социальное доказательство при
2. "Show HN" is king для dev-tools. Один хороший HN пост > месяц SEO.
3. r/selfhosted (1.8M members) любит privacy-first инструменты. Пост без продаработает лучше рекламы.
4. Niche: self-hosted GitLab users. У GitHub нет CodeRabbit-проблемы (CodeRabbit работает с GitLab SaaS). У self-hosted GitLab пользователей — есть. Найти их: GitHub поиск по gitlab-ce
docker-compose, Reddit r/gitlab.
5. Free tier как онбординг. Первый репо бесплатно → friction near-zero → конвертируются через 7-14 дней использования.

Метрики (отслеживать с Day 1)

┌──────────────────────┬───────────────────────┬─────────────┬───────────────┐
│       Метрика        │      Инструмент       │ Цель Day-45 │  Цель Day-90  │
├──────────────────────┼───────────────────────┼─────────────┼───────────────┤
│ GitHub Stars         │ GitHub                │ >50         │ >200          │
├──────────────────────┼───────────────────────┼─────────────┼───────────────┤
│ Self-hosted installs │ opt-in telemetry ping │ >10         │ >50           │
├──────────────────────┼───────────────────────┼─────────────┼───────────────┤
│ Cloud trial signups  │ DB                    │ >5          │ >30           │
├──────────────────────┼───────────────────────┼─────────────┼───────────────┤
│ MRR                  │ Stripe dashboard      │ $0          │ $290 (10×$29) │
├──────────────────────┼───────────────────────┼─────────────┼───────────────┤
│ Review quality score │ internal benchmark    │ 7/10        │ 8/10          │
├──────────────────────┼───────────────────────┼─────────────┼───────────────┤
│ Queue latency P95    │ Prometheus            │ <10 min     │ <5 min        │
├──────────────────────┼───────────────────────┼─────────────┼───────────────┤
│ Churn                │ Stripe                │ —           │ <10% mo       │
└──────────────────────┴───────────────────────┴─────────────┴───────────────┘

---
Честные предупреждения

1. 16 GB RAM — жёсткий лимит. При пиковой нагрузке (Ollama 4.5 GB + app 400 MBтолько 9 GB. Не запускай PostgreSQL + Redis одновременно на MVP. SQLite +in-process queue первые 3 месяца — правильно.
2. Платёжные инструменты: Stripe работает в большинстве стран, но если ты в стaddle или Lemon Squeezy (оба work worldwide, $0 setup, % комиссия).
3. LLM quality bar: qwen2.5-coder-7b даст ~70-80% полезных комментариев. Этого достаточно для early adopters. GPT-4-level качество невозможно без платного API — скажи это пользователям
честно и цени ниже соответственно.
4. "Show HN" не гарантирован. Если первые 30 минут нет momentum — пост умирает. Готовь запас друзей/коллег для раннего upvote, планируй в 09:00 ET.

---
Следующий шаг: вызывай /senior-devops с этим контекстом и начинай с Milestone абочий сервер с Ollama, готовый к коду.