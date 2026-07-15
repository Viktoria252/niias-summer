package org.example.summerprojectforniias.service;

import jakarta.persistence.EntityNotFoundException;
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
import java.util.List;
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
    public List<Incident> getAllIncidents() {
        return incidentRepository.findAllByOrderByCreatedAtDesc();
    }

    @Transactional(readOnly = true)
    public Document getDocument(UUID docId) {
        return documentRepository.findById(docId).orElse(null);
    }

    @Transactional
    public void addDocumentsToIncident(UUID incidentId, MultipartFile[] files) throws IOException {
        Incident incident = incidentRepository.findById(incidentId)
                .orElseThrow(() -> new EntityNotFoundException("Инцидент не найден"));

        // 1. Сохраняем дозагруженные документы
        for (MultipartFile file : files) {
            Document doc = Document.builder()
                    .id(UUID.randomUUID())
                    .incident(incident) // Связываем с существующим инцидентом
                    .fileName(file.getOriginalFilename())
                    .fileData(file.getBytes())
                    .status(DocumentStatus.NEW)
                    .build();

            // Сохраняем документ через репозиторий и добавляем в коллекцию
            documentRepository.save(doc);
            incident.getDocuments().add(doc);
        }

        // 2. Переводим статус инцидента в PENDING (как при первой загрузке),
        // чтобы асинхронный процессор корректно взял задачу в обработку
        incident.setStatus(IncidentStatus.PENDING);
        incidentRepository.save(incident);

        // 3. ЗАПУСКАЕМ фоновую обработку для этого инцидента заново
        incidentProcessor.processIncidentAsync(incidentId);
    }
}