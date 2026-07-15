package org.example.summerprojectforniias.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.JdkClientHttpRequestFactory; // Добавлен импорт
import org.springframework.web.client.RestClient;

import java.net.http.HttpClient; // Добавлен импорт

@Configuration
public class RestClientConfig {

    @Value("${app.ml-service-url:http://localhost:8000}")
    private String mlServiceUrl;

    // Объявляем бин RestClient с принудительной версией HTTP/1.1
    @Bean
    public RestClient mlRestClient() {
        // Настраиваем встроенный JDK клиент строго на версию HTTP/1.1,
        // чтобы отключить некорректный для Uvicorn h2c-апгрейд
        HttpClient httpClient = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .build();

        JdkClientHttpRequestFactory requestFactory = new JdkClientHttpRequestFactory(httpClient);

        return RestClient.builder()
                .baseUrl(mlServiceUrl)
                .requestFactory(requestFactory)
                .build();
    }

    @Bean
    public ObjectMapper objectMapper() {
        return new ObjectMapper();
    }
}