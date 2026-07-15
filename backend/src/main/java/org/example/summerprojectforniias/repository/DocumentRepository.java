package org.example.summerprojectforniias.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;
import org.example.summerprojectforniias.model.Document;

import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

@Repository
public interface DocumentRepository extends JpaRepository<Document, UUID> {

    List<Document> findAllByIncidentId(UUID incidentId);

    // Платформонезависимый JPA-запрос для извлечения документов целиком за 30 дней
    @Query("SELECT d FROM Document d WHERE d.createdAt >= :date AND d.pHash IS NOT NULL")
    List<Document> findDocumentsSince(@Param("date") LocalDateTime date);
}