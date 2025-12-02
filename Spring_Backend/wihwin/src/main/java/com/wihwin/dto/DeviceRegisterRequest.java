package com.wihwin.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
public class DeviceRegisterRequest {
    @NotBlank(message = "Device ID is required")
    private String deviceId;
}
