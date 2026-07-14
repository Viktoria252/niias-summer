-- V1__init_db.sql

CREATE TABLE incidents (
                           id UUID PRIMARY KEY,
                           status VARCHAR(50) NOT NULL,          -- PENDING, PROCESSING, COMPLETED, FAILED
                           merged_data JSONB,                    -- Итоговый собранный JSON (для автозаполнения)
                           corrected_data JSONB,                 -- Данные после ручной правки оператора (датасет обучения)
                           error_message TEXT,
                           created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                           updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE documents (
                           id UUID PRIMARY KEY,
                           incident_id UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
                           file_name VARCHAR(255) NOT NULL,
                           file_data BYTEA NOT NULL,             -- Бинарный контент файла (PDF, JPG, PNG)
                           status VARCHAR(50) NOT NULL,          -- NEW, PROCESSING, PARSED, ERROR
                           extracted_text TEXT,                  -- Сырой текст/Markdown от Qianfan-OCR (датасет обучения)
                           parsed_json JSONB,                    -- Распознанные сущности из файла от Qwen
                           p_hash VARCHAR(16),                   -- Перцептивный 64-битный хэш изображения (hex)
                           is_suspected_duplicate BOOLEAN DEFAULT FALSE,
                           created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_documents_phash ON documents(p_hash) WHERE p_hash IS NOT NULL;