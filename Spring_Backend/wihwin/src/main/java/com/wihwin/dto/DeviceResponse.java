package com.wihwin.dto;

import lombok.AllArgsConstructor;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.UUID;

@Data
@AllArgsConstructor
public class DeviceResponse {
    private Boolean hasDevice;
    private UUID id;
    private String deviceId;
    private LocalDateTime createdAt;
}
