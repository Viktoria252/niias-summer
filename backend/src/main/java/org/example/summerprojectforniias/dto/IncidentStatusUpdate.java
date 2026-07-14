package org.example.summerprojectforniias.dto;

import org.example.summerprojectforniias.model.IncidentStatus;
import java.util.UUID;

public record IncidentStatusUpdate(
        UUID incidentId,
        IncidentStatus status,
        String mergedData,            // Наполняется при COMPLETED
        boolean isSuspectedDuplicate, // Наполняется при COMPLETED
        String errorMessage           // Наполняется при FAILED
) {}
