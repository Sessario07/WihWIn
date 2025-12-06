package com.wihwin.controller;

import com.wihwin.dto.*;
import com.wihwin.entity.Device;
import com.wihwin.entity.User;
import com.wihwin.repository.DeviceRepository;
import com.wihwin.repository.UserRepository;
import com.wihwin.security.UserPrincipal;
import com.wihwin.service.AuthService;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/devices")
public class DeviceController {

    private final AuthService authService;
    private final UserRepository userRepository;
    private final DeviceRepository deviceRepository;

    public DeviceController(AuthService authService, UserRepository userRepository, DeviceRepository deviceRepository) {
        this.authService = authService;
        this.userRepository = userRepository;
        this.deviceRepository = deviceRepository;
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

    @GetMapping("/me")
    public ResponseEntity<?> getMyDevice(@AuthenticationPrincipal UserPrincipal userPrincipal) {
        try {
            Device device = deviceRepository.findByUserId(userPrincipal.getId())
                    .orElse(null);
            
            if (device == null) {
                Map<String, Object> response = new HashMap<>();
                response.put("hasDevice", false);
                response.put("device", null);
                return ResponseEntity.ok(response);
            }
            
            Map<String, Object> deviceInfo = new HashMap<>();
            deviceInfo.put("id", device.getId());
            deviceInfo.put("deviceId", device.getDeviceId());
            deviceInfo.put("createdAt", device.getCreatedAt());
            
            Map<String, Object> response = new HashMap<>();
            response.put("hasDevice", true);
            response.put("device", deviceInfo);
            return ResponseEntity.ok(response);
        } catch (Exception e) {
            return ResponseEntity.badRequest().body(new ApiResponse(false, e.getMessage()));
        }
    }

    @DeleteMapping("/disconnect")
    public ResponseEntity<?> disconnectDevice(@AuthenticationPrincipal UserPrincipal userPrincipal) {
        try {
            Device device = deviceRepository.findByUserId(userPrincipal.getId())
                    .orElseThrow(() -> new RuntimeException("No device registered to this user"));
            
            device.setUser(null);
            deviceRepository.save(device);
            
            return ResponseEntity.ok(new ApiResponse(true, "Device disconnected successfully"));
        } catch (Exception e) {
            return ResponseEntity.badRequest().body(new ApiResponse(false, e.getMessage()));
        }
    }
}
