package org.example.summerprojectforniias.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;
import org.example.summerprojectforniias.model.Document;

import java.util.UUID;

@Repository
public interface DocumentRepository extends JpaRepository<Document, UUID> {

    /**
     * Ищет визуальные дубликаты за последние 30 дней по расстоянию Хэмминга.
     * Сравнивает p_hash в формате hex, приводя его к побитовому bit(64).
     * Разница бит (расстояние Хэмминга) меньше 8 считается подозрением на дубликат.
     */
    @Query(value = """
        SELECT EXISTS (
            SELECT 1 FROM documents d 
            WHERE d.created_at >= NOW() - INTERVAL '30 days' 
              AND d.p_hash IS NOT NULL 
              AND bit_count(
                (('x' || lpad(d.p_hash, 16, '0'))::bit(64)) # 
                (('x' || lpad(:newPHash, 16, '0'))::bit(64))
              ) < 8
        )
    """, nativeQuery = true)
    boolean existsDuplicateInLast30Days(@Param("newPHash") String newPHash);
}