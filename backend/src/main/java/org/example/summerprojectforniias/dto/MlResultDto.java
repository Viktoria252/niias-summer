package org.example.summerprojectforniias.dto;

public record MlResultDto(
        String extracted_text,      // Сырой текст Markdown от OCR
        ProtocolDataDto parsed_json, // СТРУКТУРИРОВАННЫЕ ДАННЫЕ ПРОТОКОЛА
        String p_hash               // Хэш изображения
) {}
