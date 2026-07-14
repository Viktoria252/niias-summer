package org.example.summerprojectforniias.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record ProtocolDataDto(
        @JsonProperty("Место отказа") String failureLocation,
        @JsonProperty("Дата") String failureDate,
        @JsonProperty("Время начала отказа") String failureTime,
        @JsonProperty("Серия локомотива") String locomotiveSeries,
        @JsonProperty("Номер секции локомотива") String locomotiveSectionNumber,
        @JsonProperty("Договор") String contract,
        @JsonProperty("Причина отказа") String failureReason,
        @JsonProperty("Вид отказа") String failureType,
        @JsonProperty("Оборудование локомотива") String locomotiveEquipment,
        @JsonProperty("Наименование виновной организации") String responsibleOrganization
) {}