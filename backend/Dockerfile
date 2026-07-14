# Шаг 1: Сборка приложения через Maven
FROM maven:3.9.6-eclipse-temurin-21-alpine AS builder
WORKDIR /app

# Копируем pom.xml и скачиваем зависимости (чтобы закэшировать этот шаг)
COPY pom.xml .
RUN mvn dependency:go-offline -B

# Копируем исходники и собираем исполняемый jar-файл
COPY src ./src
RUN mvn clean package -DskipTests

# Шаг 2: Создание легковесного рантайма с JRE
FROM eclipse-temurin:21-jre-alpine
WORKDIR /app

# Копируем собранный jar-файл из предыдущего шага
COPY --from=builder /app/target/*.jar app.jar

# Открываем порт 8080 для Спринга
EXPOSE 8080

# Запускаем приложение
ENTRYPOINT ["java", "-jar", "app.jar"]