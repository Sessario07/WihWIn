package com.wihwin.service;

import com.wihwin.dto.ApiResponse;
import com.wihwin.dto.DeviceRegisterRequest;
import com.wihwin.dto.DeviceResponse;
import com.wihwin.entity.Device;
import com.wihwin.entity.User;
import com.wihwin.repository.DeviceRepository;
import com.wihwin.repository.UserRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.UUID;

@Service
public class DeviceService {

    private final DeviceRepository deviceRepository;
    private final UserRepository userRepository;

    public DeviceService(DeviceRepository deviceRepository, UserRepository userRepository) {
        this.deviceRepository = deviceRepository;
        this.userRepository = userRepository;
    }

    @Transactional
    public ApiResponse registerDevice(DeviceRegisterRequest request, UUID userId) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new RuntimeException("User not found"));

        if (!user.getRole().equals("customer")) {
            throw new RuntimeException("Only customers can register devices");
        }

        Device device = deviceRepository.findByDeviceId(request.getDeviceId())
                .orElse(null);

        if (device == null) {
            throw new RuntimeException("Device not found. Please ensure the device is initialized.");
        }

        if (device.getUser() != null) {
            throw new RuntimeException("Device is already registered to another user");
        }

        deviceRepository.findByUserId(userId).ifPresent(existingDevice -> {
            throw new RuntimeException("User already has a registered device");
        });

        device.setUser(user);
        deviceRepository.save(device);

        return new ApiResponse(true, "Device registered successfully");
    }

    public DeviceResponse getMyDevice(UUID userId) {
        Device device = deviceRepository.findByUserId(userId).orElse(null);

        if (device == null) {
            return new DeviceResponse(false, null, null, null);
        }

        return new DeviceResponse(
                true,
                device.getId(),
                device.getDeviceId(),
                device.getCreatedAt()
        );
    }

    @Transactional
    public ApiResponse disconnectDevice(UUID userId) {
        Device device = deviceRepository.findByUserId(userId)
                .orElseThrow(() -> new RuntimeException("No device registered to this user"));

        device.setUser(null);
        deviceRepository.save(device);

        return new ApiResponse(true, "Device disconnected successfully");
    }
}
