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
@RequestMapping("/devices")
public class DeviceController {

    private final AuthService authService;
    private final UserRepository userRepository;

    public DeviceController(AuthService authService, UserRepository userRepository) {
        this.authService = authService;
        this.userRepository = userRepository;
    }

    @PostMapping("/register")
    public ResponseEntity<?> registerDevice(
            @Valid @RequestBody DeviceRegisterRequest request,
            @AuthenticationPrincipal UserPrincipal userPrincipal) {
        try {
            User user = userRepository.findById(userPrincipal.getId())
                    .orElseThrow(() -> new RuntimeException("User not found"));
            
            ApiResponse response = authService.registerDevice(request, user);
            return ResponseEntity.ok(response);
        } catch (Exception e) {
            return ResponseEntity.badRequest().body(new ApiResponse(false, e.getMessage()));
        }
    }
}
