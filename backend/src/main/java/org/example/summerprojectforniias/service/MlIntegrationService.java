package org.example.summerprojectforniias.service;

import lombok.RequiredArgsConstructor;
import org.example.summerprojectforniias.dto.MlResultDto;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.web.client.RestClient;

@Service
@RequiredArgsConstructor
public class MlIntegrationService {

    private final RestClient mlRestClient;

    public MlResultDto extractData(byte[] fileData, String fileName) {
        // 1. Создаем ресурс файла с переопределенным именем
        ByteArrayResource fileResource = new ByteArrayResource(fileData) {
            @Override
            public String getFilename() {
                return fileName;
            }
        };

        // 2. Явно настраиваем заголовки для части запроса с файлом
        HttpHeaders partHeaders = new HttpHeaders();
        partHeaders.setContentType(MediaType.APPLICATION_OCTET_STREAM);
        HttpEntity<ByteArrayResource> fileEntity = new HttpEntity<>(fileResource, partHeaders);

        // 3. Используем классический LinkedMultiValueMap (самый стабильный способ в истории Spring)
        LinkedMultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
        body.add("file", fileEntity);

        // 4. Отправляем строго как MULTIPART_FORM_DATA
        return mlRestClient.post()
                .uri("/ocr")
                .contentType(MediaType.MULTIPART_FORM_DATA)
                .body(body)
                .retrieve()
                .body(MlResultDto.class);
    }
}