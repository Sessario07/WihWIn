package com.wihwin.controller;

import com.wihwin.dto.*;
import com.wihwin.security.UserPrincipal;
import com.wihwin.service.DeviceService;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/devices")
public class DeviceController {

    private final DeviceService deviceService;

    public DeviceController(DeviceService deviceService) {
        this.deviceService = deviceService;
    }

    @PostMapping("/register")
    public ResponseEntity<?> registerDevice(
            @Valid @RequestBody DeviceRegisterRequest request,
            @AuthenticationPrincipal UserPrincipal userPrincipal) {
        try {
            ApiResponse response = deviceService.registerDevice(request, userPrincipal.getId());
            return ResponseEntity.ok(response);
        } catch (Exception e) {
            return ResponseEntity.badRequest().body(new ApiResponse(false, e.getMessage()));
        }
    }

    @GetMapping("/me")
    public ResponseEntity<?> getMyDevice(@AuthenticationPrincipal UserPrincipal userPrincipal) {
        try {
            DeviceResponse response = deviceService.getMyDevice(userPrincipal.getId());
            return ResponseEntity.ok(response);
        } catch (Exception e) {
            return ResponseEntity.badRequest().body(new ApiResponse(false, e.getMessage()));
        }
    }

    @DeleteMapping("/disconnect")
    public ResponseEntity<?> disconnectDevice(@AuthenticationPrincipal UserPrincipal userPrincipal) {
        try {
            ApiResponse response = deviceService.disconnectDevice(userPrincipal.getId());
            return ResponseEntity.ok(response);
        } catch (Exception e) {
            return ResponseEntity.badRequest().body(new ApiResponse(false, e.getMessage()));
        }
    }
}
