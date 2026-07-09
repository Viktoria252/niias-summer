## Требования
- Docker и Docker Compose
- NVIDIA драйверы и nvidia-container-toolkit

## Запуск
1. Клонируйте репозиторий.
2. Убедитесь, что в `.env` указаны корректные переменные (особенно `VLLM_URL=http://vllm:8000`).
3. Выполните:
   ```bash
   docker-compose up -d
4. Проверьте работоспособность:
    ```bash
   curl http://localhost:8001/health
5. Отправьте изображение:
    ```bash
   curl -X POST http://localhost:8001/ocr -F "file=@doc.png"
6. Остановка
    ```bash
    docker-compose down
7. Логи 
     ```bash
    docker-compose logs -f fastapi
    docker-compose logs -f vllm