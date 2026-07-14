package org.example.summerprojectforniias.service;

import lombok.RequiredArgsConstructor;
import org.example.summerprojectforniias.dto.IncidentUploadResponse;
import org.example.summerprojectforniias.model.Document;
import org.example.summerprojectforniias.model.DocumentStatus;
import org.example.summerprojectforniias.model.Incident;
import org.example.summerprojectforniias.model.IncidentStatus;
import org.example.summerprojectforniias.repository.DocumentRepository;
import org.example.summerprojectforniias.repository.IncidentRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class IncidentService {

    private final IncidentRepository incidentRepository;
    private final DocumentRepository documentRepository;
    private final IncidentProcessor incidentProcessor;

    @Transactional
    public IncidentUploadResponse uploadIncidents(MultipartFile[] files) throws IOException {
        UUID incidentId = UUID.randomUUID();

        // 1. Создаем и сохраняем карточку инцидента со статусом PENDING
        Incident incident = Incident.builder()
                .id(incidentId)
                .status(IncidentStatus.PENDING)
                .build();
        incidentRepository.save(incident);

        // 2. Сохраняем загруженные файлы в BYTEA СУБД
        for (MultipartFile file : files) {
            Document document = Document.builder()
                    .id(UUID.randomUUID())
                    .incident(incident)
                    .fileName(file.getOriginalFilename())
                    .fileData(file.getBytes())
                    .status(DocumentStatus.NEW)
                    .build();
            documentRepository.save(document);
        }

        // 3. Вызываем ВНЕШНИЙ асинхронный бин для фоновой обработки
        incidentProcessor.processIncidentAsync(incidentId);

        // 4. Мгновенно возвращаем ID созданного инцидента
        return new IncidentUploadResponse(incidentId);
    }

    @Transactional
    public void saveCorrection(UUID incidentId, String correctedData) {
        Incident incident = incidentRepository.findById(incidentId)
                .orElseThrow(() -> new IllegalArgumentException("Инцидент не найден"));
        incident.setCorrectedData(correctedData);
        incidentRepository.save(incident);
    }
    @Transactional(readOnly = true)
    public Incident getIncident(UUID id) {
        return incidentRepository.findById(id).orElse(null);
    }

    @Transactional(readOnly = true)
    public Document getDocument(UUID docId) {
        return documentRepository.findById(docId).orElse(null);
    }
}