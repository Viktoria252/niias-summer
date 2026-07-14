package org.example.summerprojectforniias.service;

import lombok.RequiredArgsConstructor;
import org.example.summerprojectforniias.dto.MlResultDto;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestClient;

@Service
@RequiredArgsConstructor
public class MlIntegrationService {

    private final RestClient mlRestClient;

    public MlResultDto extractData(byte[] fileData, String fileName) {
        // Оборачиваем массив байт в ByteArrayResource, переопределяя getFilename
        ByteArrayResource fileResource = new ByteArrayResource(fileData) {
            @Override
            public String getFilename() {
                return fileName;
            }
        };

        MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
        body.add("file", fileResource);

        // POST запрос к FastAPI (/api/v1/extract) формата multipart/form-data
        return mlRestClient.post()
                .uri("/ocr")
                .contentType(MediaType.MULTIPART_FORM_DATA)
                .body(body)
                .retrieve()
                .body(MlResultDto.class);
    }
}