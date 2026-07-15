# Интеллектуальное автозаполнение инцидентов поломок локомотивов (ОАО «НИИАС»)

Проект представляет собой асинхронный оркестратор на базе Spring Boot, интегрированный с веб-интерфейсом на React и аналитическим ML-конвейером (FastAPI + vLLM) для автоматического извлечения структурированных данных из сканированных протоколов поломок локомотивов.

---

## 1. Архитектура системы и порты

Система разворачивается в изолированном Docker-окружении и состоит из **5 контейнеров**, объединенных в единую сеть `locomotive_network`:

| Контейнер | Название сервиса в Docker | Порт на хосте | Роль в системе |
| :--- | :--- | :--- | :--- |
| **Frontend** | `locomotive_frontend` | `80` (HTTP) | Раздача статики React через веб-сервер Nginx + Reverse Proxy |
| **Backend** | `locomotive_backend` | `8080` | Оркестратор на Spring Boot (Java 21, Virtual Threads) |
| **Database** | `locomotive_postgres` | `5432` | СУБД PostgreSQL 16 (хранение BYTEA, JSONB и Flyway-миграции) |
| **FastAPI** | `fastapi-server` | `8001` | Аналитический модуль на Python 3.11 |
| **vLLM** | `vllm-server` | `8000` | Движок инференса локальных моделей (Qianfan-OCR, Qwen) |

---

## 2. Локальная разработка и переключатель симуляции (Mock)

Бэкенд поддерживает бесшовный переключатель режима работы с ИИ-моделью с помощью переменной **`APP_ML_MOCK_ENABLED`**:

* **`true` (Режим симуляции):** Бэкенд работает автономно на точных заглушках, имитируя задержку сети. Нейросети запускать не нужно.
* **`false` (Боевой режим):** Бэкенд отправляет реальные бинарные файлы (формат `multipart/form-data`) в FastAPI по адресу `http://fastapi:8001/ocr`.

Управлять переменной можно прямо в файле `compose.yaml` (блок `environment` сервиса `backend`) без необходимости пересборки Java-кода.

---

## 3. Быстрый запуск проекта через Docker Compose

Убедитесь, что порты `80`, `8080`, `8001`, `8000` и `5432` свободны на вашем хосте.

### Запуск всей системы (Боевой режим):
docker compose up -d

### Запуск с принудительной пересборкой (При изменении кода):
docker compose up --build -d

### Запуск ТОЛЬКО базы данных и бэкенда (Для экономии ОЗУ разработчика):
docker compose up postgres backend --build -d

### Полная остановка системы:
docker compose down

---

## 4. Мониторинг логов и отладка

### Просмотр статуса запущенных контейнеров:
docker compose ps

### Просмотр логов всей системы в реальном времени:
docker compose logs -f

### Просмотр логов только бэкенда:
docker compose logs -f backend

### Просмотр логов сервера нейросетей vLLM:
docker compose logs -f vllm

---

## 5. Полный сброс базы данных
docker compose down -v

---

## 6. Офлайн-развертывание на закрытом сервере (Air-Gapped)
Шаг А (на компьютере разработчиков с интернетом)
    1. Соберите все образы системы локально:
        docker compose build
    2. Экспортируйте образы в архивы:
        docker save -o postgres.tar postgres:16-alpine
        docker save -o backend.tar summerpracticniias-backend:latest
        docker save -o fastapi.tar summerpracticniias-fastapi:latest
        docker save -o frontend.tar summerpracticniias-frontend:latest
        docker save -o vllm.tar vllm/vllm-openai:latest
    3. Скопируйте файлы архивов и корневой файл compose.yaml на защищенный внешний накопитель

Шаг Б (На закрытом сервере )
    1. Скопируйте файлы с накопителя и импортируйте образы в Docker
        docker load -i postgres.tar
        docker load -i backend.tar
        docker load -i fastapi.tar
        docker load -i frontend.tar
        docker load -i vllm.tar
    2. Запустите систему из папки с файлом compose.yaml
        docker compose up -d