package org.example.summerprojectforniias.service;

import lombok.RequiredArgsConstructor;
import org.example.summerprojectforniias.dto.MlResultDto;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.web.client.RestClient;

@Service
@RequiredArgsConstructor
public class MlIntegrationService {

    private final RestClient mlRestClient;

    public MlResultDto extractData(byte[] fileData, String fileName) {
        // 1. Создаем ресурс с переопределенным методом getFilename()
        ByteArrayResource fileResource = new ByteArrayResource(fileData) {
            @Override
            public String getFilename() {
                return fileName;
            }
        };

        // 2. Используем классический LinkedMultiValueMap.
        // Передаем ресурс НАПРЯМУЮ без обертки в HttpEntity!
        // Это гарантирует, что Spring задействует ResourceHttpMessageConverter, а не превратит объект в текст.
        LinkedMultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
        body.add("file", fileResource);

        return mlRestClient.post()
                .uri("/ocr")
                .contentType(MediaType.MULTIPART_FORM_DATA)
                .body(body)
                .retrieve()
                .body(MlResultDto.class);
    }
}