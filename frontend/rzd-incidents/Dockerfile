# Шаг 1: Сборка статических файлов React
FROM node:20-alpine AS builder
WORKDIR /app

# Копируем package.json и package-lock.json для установки зависимостей
COPY package*.json ./
RUN npm ci --silent

# Копируем весь исходный код фронтенда и собираем его
COPY . .
RUN npm run build

# Шаг 2: Раздача статики через легковесный веб-сервер Nginx
FROM nginx:1.25-alpine

# Копируем наш кастомный конфиг Nginx в контейнер
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Копируем собранные файлы React из предыдущего шага в папку статики Nginx
COPY --from=builder /app/build /usr/share/nginx/html

# Открываем стандартный HTTP-порт
EXPOSE 80

# Запуск Nginx
CMD ["nginx", "-g", "daemon off;"]