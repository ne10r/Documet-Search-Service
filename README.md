# Document Search Service

Простой поисковик: **FastAPI + PostgreSQL + Elasticsearch**.

## Запуск

```bash
cp .env.example .env
docker compose up -d --build
docker compose --profile populate run --rm populate
```

Параметры PostgreSQL (`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`) задаются в `.env`.

> После замены `data/posts.csv` нужно снова запустить `populate` — данные берутся из локальной папки `data/`, а не из образа Docker.

API: http://localhost:8000  
Swagger: http://localhost:8000/docs

## Остановка

```bash
# Остановить контейнеры (данные в volume сохранятся)
docker compose down

# Остановить и удалить volume PostgreSQL/Elasticsearch
docker compose down -v
```

## Эндпоинты

```bash
# Поиск (до 20 документов, сортировка по created_date)
curl "http://localhost:8000/posts/search?text=python"

# Поиск на кириллице
curl -G "http://localhost:8000/posts/search" --data-urlencode "text=документ"

# Удаление
curl -X DELETE "http://localhost:8000/posts/delete" \
  -H "Content-Type: application/json" \
  -d '{"id": 1}'
```

## Файлы

- `src/main.py` — API-сервис
- `src/populate.py` — загрузка CSV в PostgreSQL и Elasticsearch
- `src/config.py` — конфигурация из переменных окружения
- `data/posts.csv` — тестовые данные
- `docs.json` — OpenAPI-документация

## CSV-формат

```csv
text,created_date,rubrics
"Текст","2024-03-10 12:00:00","['рубрика1']"
```

## Тесты

```bash
pytest -v -m integration
```
