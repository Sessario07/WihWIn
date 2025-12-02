package com.wihwin.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

@Data
public class DoctorProfileRequest {
    @NotBlank(message = "Hospital name is required")
    private String hospitalName;

    @NotNull(message = "Latitude is required")
    private Double lat;

    @NotNull(message = "Longitude is required")
    private Double lon;

    private String specialization;
    private String licenseNumber;
}
