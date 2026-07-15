package org.example.summerprojectforniias.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.client.RestClient;

@Configuration
public class RestClientConfig {

    @Value("${app.ml-service-url:http://localhost:8000}")
    private String mlServiceUrl;

    // Объявляем бин RestClient, который Spring внедрит в MlIntegrationService
    @Bean
    public RestClient mlRestClient() {
        return RestClient.builder()
                .baseUrl(mlServiceUrl)
                .build();
    }

    @Bean
    public ObjectMapper objectMapper() {
        return new ObjectMapper();
    }
}