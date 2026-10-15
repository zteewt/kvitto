# Квитто — API приёма платежей

Небольшой сервис, через который онлайн-школа принимает оплату курса:
тарифы, промокоды, рассрочка, вебхук банка. Деньги везде — **целые
копейки**, без `float`.

## Быстрый старт

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   |  Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt

uvicorn kvitto.main:app --reload
```

Приложение поднимется на <http://127.0.0.1:8000>, документация — на
`/docs`. База — SQLite-файл `kvitto.db`, каталог тарифов создаётся при
старте (идемпотентно, повторный запуск не дублирует).

### Проверка

```bash
pytest                 # 165 тестов
ruff check . && ruff format --check .
```

### Docker

```bash
docker compose up --build      # http://127.0.0.1:8000
```

### Переменные окружения

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./kvitto.db` | Любая SQLAlchemy-строка, например `postgresql+psycopg://user:pass@localhost/kvitto` |
| `WEBHOOK_SECRET` | пусто | HMAC-SHA256-подпись вебхука. Пусто — проверка выключена |

### Миграции

Alembic подключён; при старте приложение само выполняет `upgrade head`
(`kvitto/infrastructure/db/schema.py`). Вручную:

```bash
alembic upgrade head
alembic revision --autogenerate -m "описание"
```

Схему нельзя одновременно создавать двумя способами — раньше это приводило
к падению `alembic upgrade head` на уже существующих таблицах, теперь
путь один.

---

## API

| Метод | Путь | Что делает |
|---|---|---|
| `GET` | `/tariffs` | каталог тарифов |
| `POST` | `/payments` | создать платёж (201), повтор по ключу — 200 |
| `GET` | `/payments/{id}` | платёж; 404, если нет |
| `GET` | `/payments?email=&status=&limit=&offset=` | список с фильтрами *(бонус)* |
| `POST` | `/webhooks/bank` | смена статуса от банка |
| `GET` | `/health` | проверка живости |

### Переходы статусов

```
pending ──► succeeded ──► refunded
   │
   └────► failed
```

Всё остальное — `409 {"error": "invalid_transition"}`, статус не меняется.

### Примеры

```bash
# Каталог
curl http://127.0.0.1:8000/tariffs
# [{"id":1,"code":"basic","title":"Базовый","price":990000},
#  {"id":2,"code":"standard","title":"Стандарт","price":1990000},
#  {"id":3,"code":"premium","title":"Премиум","price":2990000}]

# Оплата картой с промокодом (регистр не важен)
curl -X POST http://127.0.0.1:8000/payments \
  -H "Content-Type: application/json" \
  -d '{"tariff_id":"standard","email":"student@example.com","method":"card","promo_code":"kvitto10"}'
# 201: amount=1990000, discount=199000, amount_due=1791000, schedule=null

# Рассрочка на 3 месяца
curl -X POST http://127.0.0.1:8000/payments \
  -H "Content-Type: application/json" \
  -d '{"tariff_id":2,"email":"student@example.com","method":"installment","installment_months":3}'
# 201: schedule=[663334,663333,663333] — сумма графика ровно 1990000

# Повтор с тем же ключом: 200 и тот же платёж, второй не создаётся
curl -X POST http://127.0.0.1:8000/payments \
  -H "Content-Type: application/json" -H "Idempotency-Key: order-42" \
  -d '{"tariff_id":2,"email":"student@example.com","method":"card"}'

# Банк подтвердил оплату
curl -X POST http://127.0.0.1:8000/webhooks/bank \
  -H "Content-Type: application/json" \
  -d '{"payment_id":1,"status":"succeeded"}'
# 200 {"result":"ok"}; повтор того же запроса — 409

# Вебхук с подписью (если задан WEBHOOK_SECRET)
BODY='{"payment_id":1,"status":"succeeded"}'
SIG=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" -r | cut -d' ' -f1)
curl -X POST http://127.0.0.1:8000/webhooks/bank \
  -H "Content-Type: application/json" -H "X-Signature: $SIG" -d "$BODY"
```

---

## Структура

```
kvitto/
├── domain/           бизнес-правила. Ноль внешних импортов
│   ├── money.py            Money — целые копейки, float отвергается
│   ├── promo.py            PromoCode — регистр не важен
│   ├── tariff.py           Tariff + каталог по умолчанию
│   ├── installment.py      InstallmentPlan: сумма графика == сумма к оплате
│   ├── pricing.py          QuoteCalculator: промокод → скидка → сумма к оплате
│   ├── payment.py          Payment — агрегатный корень, единственное место смены статуса
│   ├── status.py           PaymentStatus + таблица переходов
│   └── ports.py            интерфейсы репозиториев
├── application/      сценарии: знают про домен и порты, но не про SQLAlchemy
├── infrastructure/   репозитории SQLAlchemy, миграции, сид тарифов
└── api/              HTTP: Pydantic-схемы, роутеры, маппинг ошибок, сборка зависимостей
```

Правило зависимостей — только внутрь:

```
api ──────────► application ──► domain
infrastructure ────────────────► domain
```

Его проверяет `tests/test_architecture.py`: если в `domain` попадёт
`sqlalchemy` или `fastapi`, тест упадёт.

### Где живут правила

| Вопрос | Ответ даёт |
|---|---|
| Сколько стоит и какая скидка | `domain/pricing.py` |
| Как делится сумма на платежи | `domain/installment.py` |
| Можно ли менять статус | `domain/status.py` + `Payment.change_status()` |
| Валидация формы запроса (422) | `api/schemas.py` |
| Какой код вернуть | `api/errors.py` |
| Что делает репозиторий | `infrastructure/db/repositories.py` |

Домен не знает про HTTP: он бросает `InvalidStatusTransition`, а `api/errors.py`
превращает это в `409`.

---

## Принятые допущения

ТЗ местами неоднозначно. Решения зафиксированы, чтобы результат был
предсказуемым:

1. **Тип `tariff_id`.** Каталог отдаёт `id` (число) и `code`
   (`basic`/`standard`/`premium`). **На вход принимается и то, и другое** —
   `2` и `"standard"` работают одинаково. В ответе платежа `tariff_id`
   всегда число, дополнительно есть `tariff_code`.

2. **`amount` и `discount`.** `amount` — полная цена тарифа, `discount` —
   размер скидки, `amount_due` — сумма к оплате (`amount - discount`).
   График рассрочки суммируется именно в `amount_due`.

3. **`installment_months` вместе с `card`/`sbp`.** ТЗ об этом молчит.
   Принято: поле игнорируется, в ответе `installment_months` и `schedule`
   равны `null`. Ошибкой считается обратный случай — `installment` без поля.

4. **Повторный вебхук.** По ТЗ `pending → succeeded` дважды даёт `409`,
   и это так и работает. В реальной интеграции банк может повторять
   доставку; там повтор того же статуса стоит считать успехом.

5. **Тот же `Idempotency-Key` с другим телом.** По ТЗ возвращается
   существующий платёж и `200` — даже если тело отличается.

6. **Округление скидки** — всегда вниз (`// 100`). Для тарифов каталога
   10% делятся ровно, так что на них правило не влияет.

7. **Даты платежей рассрочки** не возвращаются: ТЗ говорит, что они не
   нужны.

---

## Тесты

165 тестов, `pytest`. Основное:

| Область | Файлы |
|---|---|
| Деньги, промокоды, рассрочка, статусы | `test_money.py`, `test_pricing.py`, `test_installment.py`, `test_payment.py` |
| Границы слоёв | `test_architecture.py` |
| API: создание, чтение, рассрочка | `test_api_payments.py`, `test_api_tariffs.py` |
| Идемпотентность | `test_idempotency.py` |
| Вебхук и переходы статусов | `test_api_webhooks.py` |
| Подпись вебхука *(бонус)* | `test_api_webhook_signature.py` |
| Фильтры списка *(бонус)* | `test_api_list_payments.py` |
| Миграции *(бонус)* | `test_migrations.py` |

Тесты проверяют результат, а не только код ответа: например, после
запрещённого перехода платёж перечитывается из базы, а после повтора с
тем же ключом считается количество строк.

---

## Что сделано по бонусам

| Бонус | Статус |
|---|---|
| `docker compose up` | Dockerfile + compose, схема едет в том |
| Проверка подписи `X-Signature` | HMAC-SHA256 от сырого тела, `compare_digest`, 401 |
| Миграции Alembic | одна начальная миграция, автозапуск при старте |
| `GET /payments` с фильтрами | `email`, `status`, `limit`, `offset` |
| GitHub Actions | ruff + pytest на каждом push |
| Правила для ассистента | `CLAUDE.md` |