package com.wihwin.controller;

import com.wihwin.dto.*;
import com.wihwin.security.UserPrincipal;
import com.wihwin.service.ProfileService;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/profile")
public class ProfileController {

    private final ProfileService profileService;

    public ProfileController(ProfileService profileService) {
        this.profileService = profileService;
    }

    @PostMapping("/customer")
    public ResponseEntity<?> createCustomerProfile(
            @Valid @RequestBody CustomerProfileRequest request,
            @AuthenticationPrincipal UserPrincipal userPrincipal) {
        try {
            ApiResponse response = profileService.createCustomerProfile(request, userPrincipal.getId());
            return ResponseEntity.ok(response);
        } catch (Exception e) {
            return ResponseEntity.badRequest().body(new ApiResponse(false, e.getMessage()));
        }
    }

    @PostMapping("/doctor")
    public ResponseEntity<?> createDoctorProfile(
            @Valid @RequestBody DoctorProfileRequest request,
            @AuthenticationPrincipal UserPrincipal userPrincipal) {
        try {
            ApiResponse response = profileService.createDoctorProfile(request, userPrincipal.getId());
            return ResponseEntity.ok(response);
        } catch (Exception e) {
            return ResponseEntity.badRequest().body(new ApiResponse(false, e.getMessage()));
        }
    }
}
