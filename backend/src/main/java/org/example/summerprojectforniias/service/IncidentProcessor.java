package org.example.summerprojectforniias.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.example.summerprojectforniias.dto.IncidentStatusUpdate;
import org.example.summerprojectforniias.dto.MlResultDto;
import org.example.summerprojectforniias.dto.ProtocolDataDto;
import org.example.summerprojectforniias.model.*;
import org.example.summerprojectforniias.repository.DocumentRepository;
import org.example.summerprojectforniias.repository.IncidentRepository;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
@Slf4j
public class IncidentProcessor {

    private final IncidentRepository incidentRepository;
    private final DocumentRepository documentRepository;
    private final SseService sseService;
    private final MlIntegrationService mlIntegrationService;
    private final ObjectMapper objectMapper = new ObjectMapper();


    //ЗНАЧЕНИЕ true - режим симуляции
    //ЗНАЧЕНИЕ false - боевой режим для прода
    @Value("${app.ml-mock-enabled:false}")
    private boolean mlMockEnabled;

    @Async
    public void processIncidentAsync(UUID incidentId) {
        log.info("Начата фоновая обработка инцидента {}", incidentId);
        try {
            updateIncidentStatus(incidentId, IncidentStatus.PROCESSING);
            sseService.sendStatusUpdate(incidentId, new IncidentStatusUpdate(
                    incidentId, IncidentStatus.PROCESSING, null, false, null
            ));

            List<Document> documents = documentRepository.findAll().stream()
                    .filter(doc -> doc.getIncident().getId().equals(incidentId))
                    .toList();

            boolean anyDocumentIsDuplicate = false;
            ProtocolDataDto finalMergedData = null;

            for (Document doc : documents) {
                updateDocumentStatus(doc.getId(), DocumentStatus.PROCESSING);

                MlResultDto mlResult;

                if (mlMockEnabled) {
                    Thread.sleep(3000);

                    // Обновленный Mock под новый точный формат Виктории
                    ProtocolDataDto mockProtocol = new ProtocolDataDto(
                            "перегон Хижина-Магазин",
                            "2026-01-01",
                            "null",
                            "ТЭМ18Д",
                            "№1111",
                            "№999 от 01.01.2014",
                            "неисправность турбины ТК-30 (посторонний шум при работе)",
                            "производственный",
                            "локомотив ТЭМ18Д №1111",
                            "«ЛокоТех Сервис»"
                    );
                    mlResult = new MlResultDto("# Локальный OCR текст...", mockProtocol, "8f3c3c3c1c1c1c1c");
                } else {
                    // РЕАЛЬНЫЙ вызов FastAPI через HTTP-клиент
                    mlResult = mlIntegrationService.extractData(doc.getFileData(), doc.getFileName());
                }

                // Проверяем p_hash на дубликаты за последние 30 дней
                boolean isDuplicate = documentRepository.existsDuplicateInLast30Days(mlResult.p_hash());
                if (isDuplicate) {
                    anyDocumentIsDuplicate = true;
                    log.warn("Документ {} заподозрен в дублировании! pHash: {}", doc.getId(), mlResult.p_hash());
                }

                // Сливаем данные текущего документа в общий отчет
                finalMergedData = mergeProtocolData(finalMergedData, mlResult.parsed_json());

                // Записываем результаты в БД
                String parsedJsonStr = objectMapper.writeValueAsString(mlResult.parsed_json());
                updateDocumentResults(doc.getId(), DocumentStatus.PARSED,
                        mlResult.extracted_text(), parsedJsonStr,
                        mlResult.p_hash(), isDuplicate);
            }

            // Записываем финальные слитые данные и закрываем инцидент
            String finalMergedDataStr = objectMapper.writeValueAsString(finalMergedData);
            updateIncidentDataAndStatus(incidentId, IncidentStatus.COMPLETED, finalMergedDataStr);

            // Отправляем финальное уведомление через SSE
            sseService.sendStatusUpdate(incidentId, new IncidentStatusUpdate(
                    incidentId, IncidentStatus.COMPLETED, finalMergedDataStr, anyDocumentIsDuplicate, null
            ));
            sseService.completeEmitter(incidentId);

            log.info("Фоновая обработка инцидента {} успешно завершена", incidentId);

        } catch (Exception e) {
            log.error("Ошибка при обработке инцидента {}", incidentId, e);
            updateIncidentError(incidentId, e.getMessage());
            sseService.sendStatusUpdate(incidentId, new IncidentStatusUpdate(
                    incidentId, IncidentStatus.FAILED, null, false, e.getMessage()
            ));
            sseService.completeEmitter(incidentId);
        }
    }

    @Transactional
    public void updateDocumentStatus(UUID docId, DocumentStatus status) {
        documentRepository.findById(docId).ifPresent(doc -> {
            doc.setStatus(status);
            documentRepository.save(doc);
        });
    }

    @Transactional
    public void updateDocumentResults(UUID docId, DocumentStatus status, String text, String json, String pHash, boolean isDuplicate) {
        documentRepository.findById(docId).ifPresent(doc -> {
            doc.setStatus(status);
            doc.setExtractedText(text);
            doc.setParsedJson(json);
            doc.setPHash(pHash);
            doc.setIsSuspectedDuplicate(isDuplicate);
            documentRepository.save(doc);
        });
    }

    @Transactional
    public void updateIncidentStatus(UUID incidentId, IncidentStatus status) {
        incidentRepository.findById(incidentId).ifPresent(incident -> {
            incident.setStatus(status);
            incidentRepository.save(incident);
        });
    }

    @Transactional
    public void updateIncidentDataAndStatus(UUID incidentId, IncidentStatus status, String mergedData) {
        incidentRepository.findById(incidentId).ifPresent(incident -> {
            incident.setStatus(status);
            incident.setMergedData(mergedData);
            incidentRepository.save(incident);
        });
    }

    @Transactional
    public void updateIncidentError(UUID incidentId, String errorMessage) {
        incidentRepository.findById(incidentId).ifPresent(incident -> {
            incident.setStatus(IncidentStatus.FAILED);
            incident.setErrorMessage(errorMessage);
            incidentRepository.save(incident);
        });
    }

    private ProtocolDataDto mergeProtocolData(ProtocolDataDto target, ProtocolDataDto source) {
        if (source == null) return target;
        if (target == null) return source;

        // Логика слияния
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