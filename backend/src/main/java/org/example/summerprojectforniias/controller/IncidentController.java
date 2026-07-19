package org.example.summerprojectforniias.controller;

import lombok.RequiredArgsConstructor;
import org.example.summerprojectforniias.dto.IncidentUploadResponse;
import org.example.summerprojectforniias.model.Document;
import org.example.summerprojectforniias.model.Incident;
import org.example.summerprojectforniias.service.IncidentProcessor;
import org.example.summerprojectforniias.service.IncidentService;
import org.example.summerprojectforniias.service.SseService;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/incidents")
@RequiredArgsConstructor
@CrossOrigin(origins = "*")
public class IncidentController {

    private final IncidentService incidentService;
    private final SseService sseService;
    private final IncidentProcessor incidentProcessor;

    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<IncidentUploadResponse> uploadIncidents(
            @RequestParam("files") MultipartFile[] files) throws IOException {

        // Генерируем UUID прямо здесь, чтобы он был доступен обоим бинам
        UUID incidentId = UUID.randomUUID();

        // Передаем сгенерированный ID в метод сервиса
        IncidentUploadResponse response = incidentService.uploadIncidents(incidentId, files);

        // Запускаем фоновую обработку
        incidentProcessor.processIncidentAsync(incidentId);

        return ResponseEntity.ok(response);
    }

    // 2. Подписка на SSE поток обновлений статусов
    @GetMapping(value = "/{id}/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter streamIncident(@PathVariable UUID id) {
        return sseService.createEmitter(id);
    }

    // 3. Сохранение ручных корректировок оператора
    @PutMapping(value = "/{id}/correct", consumes = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Void> correctIncident(
            @PathVariable UUID id,
            @RequestBody String correctedData) {

        incidentService.saveCorrection(id, correctedData);
        return ResponseEntity.ok().build();
    }

    // 4. Получение истории инцидента по ID
    @GetMapping("/{id}")
    public ResponseEntity<Incident> getIncident(@PathVariable UUID id) {
        Incident incident = incidentService.getIncident(id);
        if (incident == null) {
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.ok(incident);
    }

    // 5. Просмотр оригинального файла документа
    @GetMapping(value = "/documents/{docId}/file", produces = MediaType.APPLICATION_OCTET_STREAM_VALUE)
    public ResponseEntity<byte[]> getDocumentFile(@PathVariable UUID docId) {
        Document doc = incidentService.getDocument(docId);
        if (doc == null) {
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.ok()
                .header("Content-Disposition", "attachment; filename=\"" + doc.getFileName() + "\"")
                .body(doc.getFileData());
    }

    // 6. Получение списка всех инцидентов для реестра
    @GetMapping
    public ResponseEntity<List<Incident>> getAllIncidents() {
        List<Incident> incidents = incidentService.getAllIncidents();
        return ResponseEntity.ok(incidents);
    }

    // 7. Дозагрузка дополнительных файлов в уже существующий инцидент
    @PostMapping(value = "/{id}/documents", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<Void> uploadAdditionalDocuments(
            @PathVariable UUID id,
            @RequestParam("files") MultipartFile[] files) throws IOException {

        // Фиксируем транзакцию добавления файлов в сервисном слое
        incidentService.addDocumentsToIncident(id, files);

        // Запускаем асинхронный процессор повторно
        incidentProcessor.processIncidentAsync(id);

        return ResponseEntity.ok().build();
    }

    // 8. Удаление инцидента и всех связанных документов
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deleteIncident(@PathVariable UUID id) {
        incidentService.deleteIncident(id);
        return ResponseEntity.ok().build();
    }

    // 9. Удаление конкретного документа из инцидента с пересчетом данных
    @DeleteMapping("/documents/{docId}")
    public ResponseEntity<Void> deleteDocument(@PathVariable UUID docId) {
        incidentService.deleteDocument(docId);
        return ResponseEntity.ok().build();
    }
}