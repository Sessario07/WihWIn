package com.wihwin.controller;

import com.wihwin.dto.*;
import com.wihwin.entity.User;
import com.wihwin.repository.UserRepository;
import com.wihwin.security.UserPrincipal;
import com.wihwin.service.AuthService;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/profile")
public class ProfileController {

    private final AuthService authService;
    private final UserRepository userRepository;

    public ProfileController(AuthService authService, UserRepository userRepository) {
        this.authService = authService;
        this.userRepository = userRepository;
    }

    @PostMapping("/customer")
    public ResponseEntity<?> createCustomerProfile(
            @Valid @RequestBody CustomerProfileRequest request,
            @AuthenticationPrincipal UserPrincipal userPrincipal) {
        try {
            User user = userRepository.findById(userPrincipal.getId())
                    .orElseThrow(() -> new RuntimeException("User not found"));
            
            ApiResponse response = authService.createCustomerProfile(request, user);
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
            User user = userRepository.findById(userPrincipal.getId())
                    .orElseThrow(() -> new RuntimeException("User not found"));
            
            ApiResponse response = authService.createDoctorProfile(request, user);
            return ResponseEntity.ok(response);
        } catch (Exception e) {
            return ResponseEntity.badRequest().body(new ApiResponse(false, e.getMessage()));
        }
    }
}
