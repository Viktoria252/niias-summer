package org.example.summerprojectforniias.model;

import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Table(name = "documents")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Document {

    @Id
    @Column(name = "id", updatable = false, nullable = false)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "incident_id", nullable = false)
    private Incident incident;

    @Column(name = "file_name", nullable = false)
    private String fileName;

    @Column(name = "file_data", nullable = false)
    private byte[] fileData;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 50)
    private DocumentStatus status;

    @Column(name = "extracted_text", columnDefinition = "TEXT")
    private String extractedText; // Текст от OCR

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "parsed_json")
    private String parsedJson; // Извлеченные сущности от LLM

    @Column(name = "p_hash", length = 16)
    private String pHash; // 16-символьный хэш в hex формате

    @Column(name = "is_suspected_duplicate")
    private Boolean isSuspectedDuplicate;

    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @PrePersist
    protected void onCreate() {
        this.createdAt = LocalDateTime.now();
        if (this.isSuspectedDuplicate == null) {
            this.isSuspectedDuplicate = false;
        }
    }
}
