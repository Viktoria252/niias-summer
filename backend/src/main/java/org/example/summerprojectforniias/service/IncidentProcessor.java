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

import java.time.LocalDateTime;
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

    @Value("${app.ml-mock-enabled:true}")
    private boolean mlMockEnabled;

    @Async
    public void processIncidentAsync(UUID incidentId) {
        log.info("Начата фоновая обработка инцидента {}", incidentId);
        try {
            // 1. Переводим инцидент в статус PROCESSING
            updateIncidentStatus(incidentId, IncidentStatus.PROCESSING);
            sseService.sendStatusUpdate(incidentId, new IncidentStatusUpdate(
                    incidentId, IncidentStatus.PROCESSING, null, false, null
            ));

            // 2. Быстро достаем список документов инцидента напрямую из БД 
            Incident incident = incidentRepository.findById(incidentId)
                    .orElseThrow(() -> new IllegalArgumentException("Инцидент не найден: " + incidentId));
            List<Document> documents = documentRepository.findAllByIncidentId(incidentId);

            boolean anyDocumentIsDuplicate = false;
            
            // Инициализируем finalMergedData уже существующими сводными данными инцидента,
            // чтобы новые дозагруженные файлы дополняли отчет, а не затирали старые поля!
            ProtocolDataDto finalMergedData = null;
            if (incident.getMergedData() != null) {
                try {
                    finalMergedData = objectMapper.readValue(incident.getMergedData(), ProtocolDataDto.class);
                    log.info("Инициализированы существующие данные для слияния: {}", incident.getMergedData());
                } catch (Exception e) {
                    log.warn("Не удалось распарсить существующий mergedData: {}", e.getMessage());
                }
            }

            for (Document doc : documents) {
                // КРИТИЧЕСКИ ВАЖНО: Пропускаем документы, которые уже были успешно обработаны ранее!
                if (doc.getStatus() == DocumentStatus.PARSED) {
                    log.info("Документ {} уже обработан ранее, пропускаем его повторный анализ.", doc.getFileName());
                    
                    // Если старый файл был помечен как дубликат, сохраняем этот флаг для общего отчета
                    if (Boolean.TRUE.equals(doc.getIsSuspectedDuplicate())) {
                        anyDocumentIsDuplicate = true;
                    }
                    continue; 
                }

                updateDocumentStatus(doc.getId(), DocumentStatus.PROCESSING);

                MlResultDto mlResult;

                if (mlMockEnabled) {
                    Thread.sleep(3000); // Имитируем работу ML на CPU

                    ProtocolDataDto mockProtocol = new ProtocolDataDto(
                            "1",
                            "2026-01-01",
                            "null",
                            "1",
                            "№1111",
                            "1",
                            "1",
                            "1",
                            "л111",
                            "1"
                    );
                    mlResult = new MlResultDto("# Локальный OCR текст...", mockProtocol, "8f3c3c3c1c1c1c1c");
                } else {
                    mlResult = mlIntegrationService.extractData(doc.getFileData(), doc.getFileName());
                }

                // 3. Надежный побитовый расчет Хэмминга на стороне Java с выявлением оригинала
                boolean isDuplicate = false;
                String newHash = mlResult.p_hash();
                String dupDetails = null;
                
                if (newHash != null) {
                    LocalDateTime thirtyDaysAgo = LocalDateTime.now().minusDays(30);
                    List<Document> existingDocs = documentRepository.findDocumentsSince(thirtyDaysAgo);
                    
                    for (Document oldDoc : existingDocs) {
                        // Исключаем сравнение со своим же прошлым хэшем, если документ перерабатывается заново
                        if (oldDoc.getId().equals(doc.getId())) {
                            continue;
                        }
                        
                        String oldHash = oldDoc.getPHash();
                        int distance = calculateHammingDistance(newHash, oldHash);
                        if (distance < 8) {
                            isDuplicate = true;
                            // Генерируем детальное описание дубликата
                            dupDetails = String.format(
                                "Текущий файл совпадает с ранее загруженным файлом '%s' в рамках Инцидента (ID: %s), который был добавлен %s.",
                                oldDoc.getFileName(),
                                oldDoc.getIncident().getId(),
                                oldDoc.getCreatedAt().toString().replace("T", " в ").substring(0, 21)
                            );
                            log.warn("Документ {} заподозрен в дублировании! {}", doc.getId(), dupDetails);
                            break;
                        }
                    }
                }

                if (isDuplicate) {
                    anyDocumentIsDuplicate = true;
                }

                // Сливаем данные текущего документа в общий отчет инцидента
                finalMergedData = mergeProtocolData(finalMergedData, mlResult.parsed_json());

                // Записываем результаты обработки конкретного документа в БД
                String parsedJsonStr = objectMapper.writeValueAsString(mlResult.parsed_json());
                
                // Если найден дубликат, записываем его детали в extracted_text вместо OCR (прикольное решение)
                String finalExtractedText = isDuplicate ? dupDetails : mlResult.extracted_text();
                
                updateDocumentResults(doc.getId(), DocumentStatus.PARSED,
                        finalExtractedText, parsedJsonStr,
                        mlResult.p_hash(), isDuplicate);

                // Отправляем промежуточные результаты на фронтенд "на лету" для автозаполнения полей формы
                String currentMergedDataStr = objectMapper.writeValueAsString(finalMergedData);
                updateIncidentDataAndStatus(incidentId, IncidentStatus.PROCESSING, currentMergedDataStr);
                
                sseService.sendStatusUpdate(incidentId, new IncidentStatusUpdate(
                        incidentId, IncidentStatus.PROCESSING, currentMergedDataStr, anyDocumentIsDuplicate, null
                ));
            }

            // 3. Сохраняем итоговые объединенные данные и закрываем инцидент (COMPLETED)
            String finalMergedDataStr = objectMapper.writeValueAsString(finalMergedData);
            updateIncidentDataAndStatus(incidentId, IncidentStatus.COMPLETED, finalMergedDataStr);

            // Отправляем финальный JSON-отчет клиенту через SSE
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

    private int calculateHammingDistance(String hash1, String hash2) {
        try {
            long h1 = Long.parseUnsignedLong(hash1, 16);
            long h2 = Long.parseUnsignedLong(hash2, 16);
            return Long.bitCount(h1 ^ h2);
        } catch (NumberFormatException e) {
            return 64;
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