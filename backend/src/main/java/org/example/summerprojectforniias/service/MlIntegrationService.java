package org.example.summerprojectforniias.service;

import lombok.RequiredArgsConstructor;
import org.example.summerprojectforniias.dto.MlResultDto;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.HttpEntity;
import org.springframework.http.MediaType;
import org.springframework.http.client.MultipartBodyBuilder;
import org.springframework.stereotype.Service;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestClient;

@Service
@RequiredArgsConstructor
public class MlIntegrationService {

    private final RestClient mlRestClient;

    public MlResultDto extractData(byte[] fileData, String fileName) {
        ByteArrayResource fileResource = new ByteArrayResource(fileData);

        MultipartBodyBuilder builder = new MultipartBodyBuilder();

        builder.part("file", fileResource)
                .filename(fileName)
                .contentType(MediaType.APPLICATION_OCTET_STREAM);

        MultiValueMap<String, HttpEntity<?>> body = builder.build();

        return mlRestClient.post()
                .uri("/ocr")
                .body(body)
                .retrieve()
                .body(MlResultDto.class);
    }
}