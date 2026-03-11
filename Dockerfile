# FILE: Dockerfile
FROM python:3.12-slim

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Копируем файлы зависимостей
COPY requirements.txt .

# Устанавливаем зависимости (включая только production-зависимости)
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь исходный код приложения
COPY . .

# Создаем директорию для данных (на случай, если volume не подключен)
RUN mkdir -p /app/data

# Команда для запуска бота
CMD ["python", "bot.py"]

