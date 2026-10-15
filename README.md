# Квитто — API приёма платежей

Небольшой сервис, через который онлайн-школа принимает оплату курса:
тарифы, промокоды, рассрочка, вебхук банка.

Три вещи, ради которых он написан:

- **Деньги — целые копейки.** Ни одного `float` ни в домене, ни в БД, ни в
  JSON. Тип `Money` отвергает нецелое на входе.
- **Повторы безопасны.** Тот же `Idempotency-Key` не создаёт второй платёж —
  это гарантируется уникальным индексом, а не проверкой «есть ли уже такой».
- **Статусы защищены.** Запрещённый переход не меняет статус, даже если
  запрос дошёл до середины обработки.

Тестов: **165**. Бонусные пункты из ТЗ: **6 из 6**.

---

## Содержание

- [Быстрый старт](#быстрый-старт)
- [Запуск через Docker](#запуск-через-docker)
- [Переменные окружения](#переменные-окружения)
- [Миграции](#миграции)
- [Проверка качества](#проверка-качества)
- [Справочник API](#справочник-api)
- [Деньги и рассрочка: как считается](#деньги-и-рассрочка-как-считается)
- [Архитектура](#архитектура)
- [Принятые допущения](#принятые-допущения)
- [Тесты](#тесты)
- [Решение по БД](#решение-по-бд)
- [Что сделано по бонусам](#что-сделано-по-бонусам)

---

## Быстрый старт

Нужен Python 3.11+.

```bash
git clone <репозиторий>
cd kvitto

python -m venv .venv
# Windows:      .venv\Scripts\activate
# Linux/macOS:  source .venv/bin/activate

pip install -r requirements-dev.txt

uvicorn kvitto.main:app --reload
```

Приложение поднимется на <http://127.0.0.1:8000>. Интерактивная
документация — <http://127.0.0.1:8000/docs> (и `/redoc`).

При первом старте:

1. выполняются миграции Alembic до последней ревизии;
2. в базу засеиваются три тарифа: `basic`, `standard`, `premium`.

База по умолчанию — файл `kvitto.db` в корне проекта. Повторный запуск
не дублирует ни схему, ни тарифы.

Проверить, что всё живо:

```bash
curl http://127.0.0.1:8000/health
# {"status":"ok"}
```

### Без Docker и без виртуального окружения

```bash
pip install -r requirements.txt     # без ruff и pytest
python -m kvitto                     # то же самое, что uvicorn kvitto.main:app
```

---

## Запуск через Docker

### Одной командой

```bash
docker compose up --build
```

Соберётся образ, создаст именованный том для базы, применит миграции,
засеет тарифы и поднимет сервис на <http://127.0.0.1:8000>.
Будет занят терминал — логи идут в него напрямую. Выйти: `Ctrl+C`.

### В фоне

```bash
docker compose up -d --build     # отсоединиться
docker compose ps                # статус и healthcheck
docker compose logs -f api       # смотреть логи
docker compose down              # остановить (данные сохранятся)
docker compose down -v           # остановить и удалить том с базой
```

### Что внутри

| Слой | Решение |
|---|---|
| Образ | `python:3.12-slim`, non-root-привилегий не требуется |
| Зависимости | отдельный слой с `pip install` — правка кода его не пересобирает |
| База | SQLite, файл `/data/kvitto.db` в именованном томе `kvitto-data` |
| Миграции | выполняются при старте приложения, отдельной командой не нужно |
| Healthcheck | `GET /health` каждые 10 с, 5 попыток |

`/data` — это **именованный том**, а не bind mount. Следствия:

- база переживает `docker compose down` и пересборку образа;
- путь к базе с хоста не нужен, всё внутри Docker;
- `docker compose down -v` удаляет данные безвозвратно — это способ
  начать с чистой базы.

### Пример полного цикла в Docker

```bash
# поднять с чистой базой
docker compose down -v
docker compose up -d --build

# создать платёж
PAYMENT=$(curl -s -X POST http://127.0.0.1:8000/payments \
  -H "Content-Type: application/json" \
  -d '{"tariff_id":"standard","email":"student@example.com","method":"card","promo_code":"kvitto10"}')
echo "$PAYMENT"

# подтвердить оплату
ID=$(echo "$PAYMENT" | python -c "import json,sys; print(json.load(sys.stdin)['id'])")
curl -s -X POST http://127.0.0.1:8000/webhooks/bank \
  -H "Content-Type: application/json" \
  -d "{\"payment_id\":$ID,\"status\":\"succeeded\"}"
# {"result":"ok"}

# посмотреть, что реально записалось
docker compose exec api python -c \
  "import sqlite3; c=sqlite3.connect('/data/kvitto.db'); print(c.execute('SELECT id,status,amount,discount FROM payments').fetchall())"
```

### С секретом для подписи вебхуков

```bash
# Linux/macOS
export WEBHOOK_SECRET="my-secret"
docker compose up -d --build

# Windows (PowerShell)
$env:WEBHOOK_SECRET = "my-secret"
docker compose up -d --build
```

После этого неподписанные запросы на `/webhooks/bank` будут получать `401`.
Остальные ручки работают как обычно. Подробности — в
[справочнике API](#справочник-api).

Если секрет не задан, проверка подписи выключена: сервис поднимается и
работает без единой переменной окружения.

### Docker без `compose`

```bash
docker build -t kvitto .
docker run -p 8000:8000 -v kvitto-data:/data -e WEBHOOK_SECRET=my-secret kvitto
```

### Если что-то пошло не так

| Симптом | Причина |
|---|---|
| Порт 8000 занят | смените `"8000:8000"` на `"8080:8000"` в `docker-compose.yml` |
| `exec /data` permission denied | том создался от root — `docker compose down -v` и поднять заново |
| Изменения в коде не видны | в compose нет монтирования исходников, нужен `docker compose up --build` |
| Не задан `WEBHOOK_SECRET` — подпись не проверяется | это ожидаемое поведение, задайте переменную |

---

## Переменные окружения

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./kvitto.db` | Любая строка подключения SQLAlchemy 2.0 |
| `WEBHOOK_SECRET` | пусто | Секрет HMAC-SHA256 для вебхуков. Пусто — проверка выключена |

Пример для PostgreSQL:

```bash
DATABASE_URL="postgresql+psycopg://kvitto:secret@localhost:5432/kvitto" \
  uvicorn kvitto.main:app
```

Пакет `psycopg` нужно доустановить отдельно — он не в зависимостях, чтобы
не тянуть драйвер СУБД тем, кто работает на SQLite.

---

## Миграции

Alembic настроен, при старте приложение само выполняет `upgrade head`
(`kvitto/infrastructure/db/schema.py`). Вручную:

```bash
alembic upgrade head                      # применить
alembic downgrade -1                      # откатить на шаг назад
alembic current                           # текущая ревизия
alembic revision --autogenerate -m "текст"   # создать миграцию
alembic history                           # список ревизий
```

Новые файлы миграций автоматически приводятся к стилю проекта
пост-хуком `ruff` из `alembic.ini`.

**Почему схему нельзя создавать двумя способами.** Изначально приложение
вызывало `create_all()` при старте, а Alembic обновлял ту же базу. Если
сначала отработал `create_all`, последующий `alembic upgrade head` падал на
уже существующих таблицах. Сейчас путь один: миграции, а `create_all()`
используется только как запасной вариант, если Alembic недоступен.
Тест `tests/test_migrations.py` сверяет схему из миграций со схемой из
моделей, чтобы они не разошлись.

---

## Проверка качества

```bash
pytest                                   # 165 тестов, ~8 с
pytest -v                                # подробно
pytest tests/test_installment.py         # один файл
pytest -k idempotency                    # по подстроке в имени
ruff check .                             # линтер
ruff format --check .                    # проверка форматирования
ruff check . --fix                       # починить автоматически
```

В CI (`.github/workflows/ci.yml`) на каждый push в `main` и на каждый PR
прогоняются `ruff check`, `ruff format --check` и `pytest` на Python 3.12.

---

## Справочник API

Все денежные значения — **целые числа копеек**. `19900 ₽` → `1990000`.

### `GET /tariffs`

Каталог тарифов.

```bash
curl http://127.0.0.1:8000/tariffs
```

```json
[
  {"id": 1, "code": "basic",    "title": "Базовый",  "price": 990000},
  {"id": 2, "code": "standard", "title": "Стандарт", "price": 1990000},
  {"id": 3, "code": "premium",  "title": "Премиум",  "price": 2990000}
]
```

| Поле | Тип | Описание |
|---|---|---|
| `id` | int | идентификатор тарифа |
| `code` | str | `basic` / `standard` / `premium` |
| `title` | str | название для интерфейса |
| `price` | int | полная цена в копейках |

Коды: `200`.

---

### `POST /payments`

Создаёт платёж в статусе `pending`.

**Тело запроса**

| Поле | Тип | Обяз. | Описание |
|---|---|---|---|
| `tariff_id` | int \| str | да | id тарифа или его код: `2` или `"standard"` |
| `email` | str | да | валидный email плательщика |
| `method` | str | да | `card`, `sbp` или `installment` |
| `installment_months` | int \| null | для `installment` | только `3`, `6` или `12` |
| `promo_code` | str \| null | нет | например `KVITTO10`, регистр не важен |

Лишние поля в теле приводят к `422`.

**Заголовки**

| Заголовок | Описание |
|---|---|
| `Idempotency-Key` | необязательный, до 255 символов. Повтор с тем же ключом вернёт `200` и существующий платёж |

**Тело ответа `201`**

```json
{
  "id": 1,
  "status": "pending",
  "tariff_id": 2,
  "tariff_code": "standard",
  "amount": 1990000,
  "discount": 199000,
  "amount_due": 1791000,
  "method": "installment",
  "installment_months": 3,
  "schedule": [597000, 597000, 597000],
  "email": "student@example.com",
  "created_at": "2026-10-15T14:42:12.572111Z"
}
```

| Поле | Тип | Описание |
|---|---|---|
| `id` | int | идентификатор платежа |
| `status` | str | `pending` / `succeeded` / `failed` / `refunded` |
| `tariff_id` | int | id тарифа |
| `tariff_code` | str \| null | код тарифа (удобство поверх обязательного `tariff_id`) |
| `amount` | int | полная цена тарифа, копейки |
| `discount` | int | размер скидки, копейки |
| `amount_due` | int | к оплате: `amount - discount`, копейки |
| `method` | str | способ оплаты |
| `installment_months` | int \| null | срок рассрочки; `null` для `card`/`sbp` |
| `schedule` | list[int] \| null | график рассрочки в копейках; `null` для `card`/`sbp` |
| `email` | str | email плательщика |
| `created_at` | str | ISO 8601 в UTC |

**Коды ответа**

| Код | Когда |
|---|---|
| `201` | платёж создан |
| `200` | повтор с тем же `Idempotency-Key` — вернулся существующий платёж |
| `404` | тариф не найден |
| `422` | ошибка валидации или неизвестный промокод |

```bash
# карта с промокодом (регистр не важен)
curl -X POST http://127.0.0.1:8000/payments \
  -H "Content-Type: application/json" \
  -d '{"tariff_id":"standard","email":"student@example.com","method":"card","promo_code":"kvitto10"}'
# 201: amount=1990000, discount=199000, amount_due=1791000, schedule=null

# рассрочка на 3 месяца
curl -X POST http://127.0.0.1:8000/payments \
  -H "Content-Type: application/json" \
  -d '{"tariff_id":2,"email":"student@example.com","method":"installment","installment_months":3}'
# 201: schedule=[663334,663333,663333] — в сумме ровно 1990000

# повтор с тем же ключом
curl -i -X POST http://127.0.0.1:8000/payments \
  -H "Content-Type: application/json" -H "Idempotency-Key: order-42" \
  -d '{"tariff_id":2,"email":"student@example.com","method":"card"}'
curl -i -X POST http://127.0.0.1:8000/payments \
  -H "Content-Type: application/json" -H "Idempotency-Key: order-42" \
  -d '{"tariff_id":2,"email":"student@example.com","method":"card"}'
# первый — 201, второй — 200, id одинаковый
```

---

### `GET /payments/{payment_id}`

Возвращает платёж по id — с тем же телом ответа, что и `POST /payments`.

```bash
curl http://127.0.0.1:8000/payments/1
curl http://127.0.0.1:8000/payments/999999
# 404 {"detail":"Платёж 999999 не найден"}
```

| Код | Когда |
|---|---|
| `200` | платёж найден |
| `404` | платежа нет |
| `422` | `payment_id` не положительное целое число |

---

### `GET /payments`

Список платежей с фильтрами. Бонусное требование.

| Параметр | Тип | По умолчанию | Описание |
|---|---|---|---|
| `email` | str | — | точное совпадение |
| `status` | str | — | `pending` / `succeeded` / `failed` / `refunded` |
| `limit` | int | `50` | 1…200 |
| `offset` | int | `0` | смещение |

Сортировка — от свежих к старым. Фильтры можно комбинировать.

```bash
curl "http://127.0.0.1:8000/payments?email=student@example.com"
curl "http://127.0.0.1:8000/payments?status=succeeded"
curl "http://127.0.0.1:8000/payments?email=student@example.com&status=succeeded&limit=10"
```

| Код | Когда |
|---|---|
| `200` | список платежей (возможно пустой) |
| `422` | неизвестный статус или некорректные `limit`/`offset` |

---

### `POST /webhooks/bank`

Банк сообщает об изменении статуса.

**Тело запроса**

| Поле | Тип | Обяз. | Описание |
|---|---|---|---|
| `payment_id` | int | да | id платежа |
| `status` | str | да | новый статус |

**Разрешённые переходы**

```
pending ──► succeeded ──► refunded
   │
   └────► failed
```

Всё остальное запрещено.

**Тело ответа `200`**

```json
{"result": "ok"}
```

| Код | Когда | Тело |
|---|---|---|
| `200` | статус обновлён | `{"result":"ok"}` |
| `401` | неверная подпись (если задан `WEBHOOK_SECRET`) | `{"detail":"Неверная подпись вебхука"}` |
| `404` | платежа нет | `{"detail":"Платёж 42 не найден"}` |
| `409` | переход запрещён, статус **не изменился** | `{"error":"invalid_transition"}` |
| `422` | неизвестный статус или ошибка тела | стандартный ответ FastAPI |

```bash
curl -X POST http://127.0.0.1:8000/webhooks/bank \
  -H "Content-Type: application/json" \
  -d '{"payment_id":1,"status":"succeeded"}'
# 200 {"result":"ok"}

# тот же запрос повторно — 409, статус остаётся succeeded
```

**Проверка подписи (бонус).** Если задан `WEBHOOK_SECRET`, запрос обязан
содержать `X-Signature` — HMAC-SHA256 от сырого тела запроса, hex-дайджест.
Префикс `sha256=` тоже принимается. Сравнение постоянного времени
(`hmac.compare_digest`). Проверка выполняется до разбора тела, поэтому
неподписанный запрос получает `401` и не раскрывает состояние платежа.

```bash
export WEBHOOK_SECRET="my-secret"
BODY='{"payment_id":1,"status":"succeeded"}'
SIG=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" -r | cut -d' ' -f1)

curl -X POST http://127.0.0.1:8000/webhooks/bank \
  -H "Content-Type: application/json" -H "X-Signature: $SIG" -d "$BODY"
# 200 {"result":"ok"}

curl -i -X POST http://127.0.0.1:8000/webhooks/bank \
  -H "Content-Type: application/json" -H "X-Signature: wrong" -d "$BODY"
# 401
```

> Подпись считается от **байтов тела**. Если банк прислал другое
> форматирование JSON, чем подписал, подпись не сойдётся — это ожидаемо.

---

### `GET /health`

```json
{"status": "ok"}
```

Используется healthcheck-ом в Docker. Базу не трогает.

---

### Формат ошибок

| Тип | Тело |
|---|---|
| Ошибка валидации запроса | `{"detail":[{"type":"...","loc":["body","field"],"msg":"..."}]}` — стандартный ответ FastAPI |
| Неизвестный промокод | `{"detail":"Неизвестный промокод: 'SUMMER'"}` |
| Недопустимый срок рассрочки | `{"detail":"Недопустимый срок рассрочки: 5"}` |
| Не найдено | `{"detail":"Платёж 42 не найден"}` |
| Запрещённый переход | `{"error":"invalid_transition"}` — формат зафиксирован в ТЗ |
| Неверная подпись | `{"detail":"Неверная подпись вебхука"}` |

Формат `409` — единственный нестандартный, он требуется ТЗ. Остальное
совпадает с тем, что FastAPI возвращает сам, поэтому отдельный формат не
придумывался.

---

## Деньги и рассрочка: как считается

### Хранение и выдача

Один рубль — `100` копеек. Тариф «Стандарт» (`19 900 ₽`) хранится как
`1990000` в колонке `BIGINT` и выдаётся как `1990000`.

`float` не используется нигде. В домене тип `Money` проверяет это в
конструкторе и бросает `TypeError`, а Pydantic для денежных полей не
применяется — иначе `1990000.0` молча превратился бы в `1990000`.

### Промокод

`KVITTO10` даёт скидку 10%. Регистр и лишние пробелы игнорируются:
`kvitto10`, `KVITTO10`, `  KvItTo10  ` — один и тот же код.

```python
discount = amount * 10 // 100  # только целочисленная арифметика
```

Округление всегда вниз. Для тарифов каталога 10% делятся ровно
(`990000 → 99000`, `1990000 → 199000`, `2990000 → 299000`), так что правило
на них не влияет и зафиксировано явно. Неизвестный код — `422`.

### Рассрочка

Сумма к оплате делится на срок, остаток копеек раздаётся по одной в первые
платежи:

```python
base, remainder = divmod(amount_due, months)
schedule = [base + 1] * remainder + [base] * (months - remainder)
```

Пример из ТЗ — «Стандарт» без промокода на 3 месяца:

```
1990000 = 663334 + 663333 + 663333     # ровно 1990000
```

С промокодом сумма к оплате 1 791 000, на 3 месяца делится ровно:
`[597000, 597000, 597000]`. На 6 и 12 месяцев суммы тоже сходятся, это
проверено параметризованными тестами.

Инвариант держит конструктор `InstallmentPlan`: если сумма графика не равна
сумме к оплате, объект не создастся.

### Статусы

Таблица переходов одна, в `domain/status.py`. Её читает
`Payment.change_status()`, который **бросает исключение до изменения поля** —
поэтому запрещённый переход физически не может оставить платёж в
промежуточном состоянии, даже если подтверждение ответа упадёт по сети.

### Идемпотентность

`Idempotency-Key` хранится в колонке с уникальным индексом. Проверка «есть ли
уже такой платёж» — оптимизация, а не гарантия: два параллельных запроса
с одним ключом пройдут её одновременно, и второй упрётся в индекс. Репозиторий
переводит `IntegrityError` в `DuplicateIdempotencyKey`, сценарий ловит его
и возвращает платёж победителя. Транзакция на запрос одна — при ошибке
делается откат, поэтому «наполовину применённый» переход статуса невозможен.

---

## Архитектура

```
kvitto/
├── domain/                   бизнес-правила. Ноль внешних импортов
│   ├── money.py              Money — целые копейки, float отвергается
│   ├── promo.py              PromoCode — регистр не важен
│   ├── tariff.py             Tariff и каталог по умолчанию
│   ├── installment.py        InstallmentPlan: сумма графика == сумма к оплате
│   ├── pricing.py            QuoteCalculator: промокод → скидка → к оплате
│   ├── payment.py            Payment — агрегатный корень, единственное место смены статуса
│   ├── status.py             PaymentStatus и таблица переходов
│   ├── events.py             PaymentStatusChanged
│   ├── exceptions.py         ошибки домена
│   └── ports.py              интерфейсы репозиториев (ABC)
│
├── application/              сценарии. Знают про домен и порты, но не про SQLAlchemy
│   ├── dto.py                команды и результаты (dataclass)
│   ├── clock.py              время как зависимость — тесты не зависят от системных часов
│   ├── create_payment.py     идемпотентность → тариф → промокод → рассрочка → сохранение
│   ├── get_payment.py
│   ├── list_tariffs.py
│   ├── change_payment_status.py
│   └── list_payments.py
│
├── infrastructure/           адаптеры внешнего мира
│   └── db/
│       ├── models.py         таблицы SQLAlchemy
│       ├── repositories.py   реализации портов + маппинг домен ↔ строки
│       ├── session.py        движок, сессии, unit of work
│       ├── schema.py         миграции при старте
│       └── seed.py           каталог тарифов, идемпотентно
│
└── api/                      HTTP
    ├── app.py                create_app: фабрика + lifespan
    ├── schemas.py            Pydantic: единственное место валидации JSON
    ├── errors.py             доменная ошибка → код ответа
    ├── deps.py               сессия на запрос, проверка подписи
    ├── security.py           HMAC-SHA256
    ├── settings.py           настройки из окружения
    ├── container.py          сборка зависимостей (composition root)
    └── routers/              tariffs.py · payments.py · webhooks.py

migrations/                   Alembic
tests/                        pytest
```

Правило зависимостей — только внутрь:

```
api ──────────────► application ──► domain
infrastructure ───────────────────► domain
```

Проверяется тестом `tests/test_architecture.py` через AST-разбор импортов:
в `domain` не может появиться `sqlalchemy`, `fastapi` или `pydantic`, а в
`application` — что-либо кроме `domain`. Нарушение границы роняет сборку,
а не только тесты.

### Где какое правило живёт

| Вопрос | Ответ даёт |
|---|---|
| Сколько стоит и какая скидка | `domain/pricing.py` |
| Как делится сумма на платежи | `domain/installment.py` |
| Можно ли менять статус | `domain/status.py` + `Payment.change_status()` |
| Что означает `amount` / `discount` | `domain/pricing.py` + `Payment.amount_due` |
| Валидация формы запроса | `api/schemas.py` |
| Какой код вернуть | `api/errors.py` |
| Что делает репозиторий | `infrastructure/db/repositories.py` |
| Что подставлять в сценарии | `api/container.py` |

Домен не знает про HTTP: он бросает `InvalidStatusTransition`, а
`api/errors.py` превращает это в `409`.

### Почему Pydantic только на границе

| Слой | Чем | Почему |
|---|---|---|
| `api/schemas.py` | Pydantic v2 | валидация данных из сети, стандартные `422` |
| `application/dto.py` | `dataclass` | внутренний контракт роутер ↔ сценарий, данные уже проверены |
| `domain/*` | `dataclass` + `StrEnum` | ноль внешних зависимостей |

`Money` — `frozen=True, slots=True`: неизменяемый, хешируемый, без
`__dict__`. Тот же набор даёт value-объектам гарантию, что цену нельзя
случайно изменить после расчёта.

---

## Принятые допущения

ТЗ местами неоднозначно. Решения зафиксированы явно, чтобы результат был
предсказуемым:

1. **Тип `tariff_id`.** Каталог отдаёт `id` (число) и `code`. **На вход
   принимается и то, и другое**: `2` и `"standard"` работают одинаково. В
   ответе платежа `tariff_id` всегда число, дополнительно есть `tariff_code`.

2. **`amount` и `discount`.** `amount` — полная цена тарифа, `discount` —
   размер скидки, `amount_due` — сумма к оплате (`amount - discount`).
   График рассрочки суммируется именно в `amount_due`. В ТЗ это не
   разъяснено; добавлено поле `amount_due`, чтобы не гадать.

3. **`installment_months` вместе с `card`/`sbp`.** ТЗ об этом молчит:
   сказано только, что для рассрочки поле обязательно. Принято терпимое
   поведение — поле игнорируется, в ответе `installment_months` и `schedule`
   равны `null`. Ошибкой считается обратный случай: `installment` без поля.

4. **Повторный вебхук.** По ТЗ `pending → succeeded` дважды даёт `409`, и
   это так и работает. В реальной интеграции банк может повторять доставку;
   там повтор того же статуса стоило бы считать успехом — но это изменение
   поведения, а не реализации.

5. **Тот же `Idempotency-Key` с другим телом.** По ТЗ возвращается
   существующий платёж и `200` — даже если тело отличается. В реальном
   платёжном API такой запрос стоило бы отклонять с `409`, чтобы не
   спрятать опечатку клиента.

6. **Округление скидки** — всегда вниз (`// 100`). Для тарифов каталога 10%
   делятся ровно, так что правило на них не влияет.

7. **Даты платежей рассрочки** не возвращаются: ТЗ говорит, что они не нужны.

8. **Лишние поля в теле запроса** отвергаются с `422` (`extra="forbid"`),
   чтобы опечатка вроде `promocode` не проходила молча.

---

## Тесты

165 тестов, `pytest`, ~8 секунд. Каждый интеграционный тест получает
свою временную базу, поэтому состояние не протекает между тестами.

| Область | Файл | Что проверяет |
|---|---|---|
| Деньги | `test_money.py` | перевод рублей в копейки, отказ от `float` и `bool`, точность процентов |
| Промокоды | `test_pricing.py` | регистр, пробелы, все три тарифа, неизвестный код |
| Рассрочка | `test_installment.py` | сумма графика равна сумме к оплате для 3/6/12 месяцев, остаток в первых платежах |
| Агрегат | `test_payment.py` | создание, инварианты, разрешённые и запрещённые переходы |
| Границы слоёв | `test_architecture.py` | в домен нельзя импортировать фреймворки |
| Каталог | `test_api_tariffs.py` | сид при старте, отсутствие дублей при перезапуске |
| Создание платежа | `test_api_payments.py` | промокод, рассрочка, `int`-ность денег, 422 |
| Чтение | `test_api_payments.py` | `GET /payments/{id}`, 404, сверка с содержимым БД |
| Идемпотентность | `test_idempotency.py` | повтор → 200 и тот же `id`, в БД одна строка |
| Вебхук | `test_api_webhooks.py` | все переходы, 409 не меняет статус, проверка по БД |
| Подпись *(бонус)* | `test_api_webhook_signature.py` | верная и неверная подпись, 401 до разбора тела |
| Фильтры *(бонус)* | `test_api_list_payments.py` | фильтры по `email`/`status`, пагинация |
| Миграции *(бонус)* | `test_migrations.py` | схема из миграций совпадает со схемой из моделей |

Тесты проверяют **результат**, а не только код ответа:

```python
def test_forbidden_transition_does_not_touch_database(client, read_payments):
    payment_id = make_payment(client)
    send(client, payment_id, "succeeded")

    assert send(client, payment_id, "failed").status_code == 409

    stored = read_payments()  # читаем БД, а не тело ответа
    assert len(stored) == 1
    assert stored[0].status.value == "succeeded"
```

---

## Решение по БД

По умолчанию **SQLite**: ТЗ допускает обе СУБД, а SQLite позволяет запустить
проект одной командой без настройки — это прямо оценивается в критериях.
Миграции, модели и репозитории от СУБД не зависят: переход на PostgreSQL —
это `DATABASE_URL` и `pip install psycopg[binary]`, код менять не нужно.

Почему отдельный контейнер БД не добавлен: он даёт credentials, healthcheck
зависимость и ожидание готовности, а бонусные баллы за compose ограничены.
Ценность PostgreSQL здесь — в возможности переехать, а не в её наличии в
compose.

Что проверено: весь цикл в Docker (сборка, старт, миграции, том, рестарт,
подпись вебхуков) прогнан на SQLite. На PostgreSQL проект не запускался.

---

## Что сделано по бонусам

| Бонус | Реализация |
|---|---|
| `docker compose up` | Dockerfile + compose, healthcheck, именованный том, проверено от `down -v` до смоук-теста |
| Проверка подписи `X-Signature` | HMAC-SHA256 от сырого тела, `compare_digest`, 401 до разбора тела |
| Миграции Alembic | начальная миграция, автозапуск при старте, тест на отсутствие дрейфа со схемой моделей |
| `GET /payments` с фильтрами | `email`, `status`, `limit`, `offset` |
| GitHub Actions | `ruff check`, `ruff format --check`, `pytest` на каждый push и PR |
| Правила для ассистента | `CLAUDE.md` — что нельзя делать в домене и почему |