package com.wihwin.dto;

import lombok.Data;

@Data
public class CustomerProfileRequest {
    private String bloodType;
    private String allergies;
    private String preExistingConditions;
    private String currentMedications;
    private String recentMedicalHistory;
    private String advanceDirectives;
    private String emergencyContactName;
    private String emergencyContactPhone;
}
