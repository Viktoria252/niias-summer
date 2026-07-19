package org.example.summerprojectforniias.service;

import jakarta.persistence.EntityNotFoundException;
import lombok.RequiredArgsConstructor;
import org.example.summerprojectforniias.dto.IncidentUploadResponse;
import org.example.summerprojectforniias.dto.ProtocolDataDto;
import org.example.summerprojectforniias.model.Document;
import org.example.summerprojectforniias.model.DocumentStatus;
import org.example.summerprojectforniias.model.Incident;
import org.example.summerprojectforniias.model.IncidentStatus;
import org.example.summerprojectforniias.repository.DocumentRepository;
import org.example.summerprojectforniias.repository.IncidentRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class IncidentService {

    private final IncidentRepository incidentRepository;
    private final DocumentRepository documentRepository;
    private final ObjectMapper objectMapper = new ObjectMapper();

    @Transactional
    public IncidentUploadResponse uploadIncidents(UUID incidentId, MultipartFile[] files) throws IOException {

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
                    .incident(incident)
                    .fileName(file.getOriginalFilename())
                    .fileData(file.getBytes())
                    .status(DocumentStatus.NEW)
                    .build();

            documentRepository.save(doc);
            incident.getDocuments().add(doc);
        }

        // 2. Переводим статус инцидента в PENDING
        incident.setStatus(IncidentStatus.PENDING);
        incidentRepository.save(incident);

    }
    @Transactional
    public void deleteIncident(UUID id) {
        List<Document> docs = documentRepository.findAll().stream()
                .filter(doc -> doc.getIncident().getId().equals(id))
                .toList();

        documentRepository.deleteAll(docs);
        incidentRepository.deleteById(id);
    }

    @Transactional
    public void deleteDocument(UUID docId) {
        Document doc = documentRepository.findById(docId).orElse(null);
        if (doc != null) {
            Incident incident = doc.getIncident();
            documentRepository.delete(doc);

            // Пересчитываем объединенные данные по оставшимся обработанным документам
            List<Document> remainingDocs = documentRepository.findAllByIncidentId(incident.getId());
            ProtocolDataDto merged = null;
            for (Document d : remainingDocs) {
                if (d.getStatus() == DocumentStatus.PARSED && d.getParsedJson() != null) {
                    try {
                        ProtocolDataDto parsed = objectMapper.readValue(d.getParsedJson(), ProtocolDataDto.class);
                        merged = mergeProtocolData(merged, parsed);
                    } catch (Exception e) {
                        // Игнорируем ошибки парсинга для поврежденных строк
                    }
                }
            }
            try {
                String mergedStr = merged != null ? objectMapper.writeValueAsString(merged) : null;
                incident.setMergedData(mergedStr);
                incidentRepository.save(incident);
            } catch (Exception e) {
                // Игнорируем
            }
        }
    }

    private ProtocolDataDto mergeProtocolData(ProtocolDataDto target, ProtocolDataDto source) {
        if (source == null) return target;
        if (target == null) return source;

        return new ProtocolDataDto(
                source.failureLocation() != null ? source.failureLocation() : target.failureLocation(),
                source.failureDate() != null ? source.failureDate() : target.failureDate(),
                source.failureTime() != null ? source.failureTime() : target.failureTime(),
                source.locomotiveSeries() != null ? source.locomotiveSeries() : target.locomotiveSeries(),
                source.locomotiveSectionNumber() != null ? source.locomotiveSectionNumber() : target.locomotiveSectionNumber(),
                source.contract() != null ? source.contract() : target.contract(),
                source.failureReason() != null ? source.failureReason() : target.failureReason(),
                source.failureType() != null ? source.failureType() : target.failureType(),
                source.locomotiveEquipment() != null ? source.locomotiveEquipment() : target.locomotiveEquipment(),
                source.responsibleOrganization() != null ? source.responsibleOrganization() : target.responsibleOrganization()
        );
    }
}