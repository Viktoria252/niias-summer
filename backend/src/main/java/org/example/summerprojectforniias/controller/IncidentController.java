package org.example.summerprojectforniias.controller;

import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import org.example.summerprojectforniias.dto.IncidentUploadResponse;
import org.example.summerprojectforniias.service.IncidentService;
import org.example.summerprojectforniias.service.SseService;
import org.example.summerprojectforniias.model.Incident;
import org.example.summerprojectforniias.model.Document;

import java.io.IOException;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/incidents")
@RequiredArgsConstructor
@CrossOrigin(origins = "*") // Разрешаем запросы с любого порта
public class IncidentController {

    private final IncidentService incidentService;
    private final SseService sseService;

    // 1. Загрузка файлов
    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<IncidentUploadResponse> uploadIncidents(
            @RequestParam("files") MultipartFile[] files) throws IOException {

        IncidentUploadResponse response = incidentService.uploadIncidents(files);
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

    // 4. Получение истории инцидента по ID (если пользователь обновил страницу)
    @GetMapping("/{id}")
    public ResponseEntity<Incident> getIncident(@PathVariable UUID id) {
        Incident incident = incidentService.getIncident(id);
        if (incident == null) {
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.ok(incident);
    }

    // 5. Просмотр оригинального файла документа из базы данных (для рендеринга картинок на фронте)
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
}