package org.example.summerprojectforniias.service;

import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import org.example.summerprojectforniias.dto.IncidentStatusUpdate;

import java.io.IOException;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

@Service
public class SseService {

    // Карта для хранения активных SSE-подключений клиентов
    private final Map<UUID, SseEmitter> emitters = new ConcurrentHashMap<>();

    public SseEmitter createEmitter(UUID incidentId) {
        // Устанавливаем таймаут соединения (например, 10 минут)
        SseEmitter emitter = new SseEmitter(600_000L);

        emitters.put(incidentId, emitter);

        // Обрабатываем завершение или обрыв связи
        emitter.onCompletion(() -> emitters.remove(incidentId));
        emitter.onTimeout(() -> emitters.remove(incidentId));
        emitter.onError((e) -> emitters.remove(incidentId));

        return emitter;
    }

    public void sendStatusUpdate(UUID incidentId, IncidentStatusUpdate update) {
        SseEmitter emitter = emitters.get(incidentId);
        if (emitter != null) {
            try {
                emitter.send(SseEmitter.event()
                        .name("status-update")
                        // Передаем MediaType.APPLICATION_JSON вторым аргументом в метод .data()
                        .data(update, MediaType.APPLICATION_JSON));
            } catch (IOException e) {
                emitters.remove(incidentId);
            }
        }
    }

    public void completeEmitter(UUID incidentId) {
        SseEmitter emitter = emitters.remove(incidentId);
        if (emitter != null) {
            emitter.complete();
        }
    }
}
