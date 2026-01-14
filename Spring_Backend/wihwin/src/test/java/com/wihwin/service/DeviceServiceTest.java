package com.wihwin.service;
import com.wihwin.dto.ApiResponse;
import com.wihwin.dto.DeviceRegisterRequest;
import com.wihwin.dto.DeviceResponse;
import com.wihwin.entity.Device;
import com.wihwin.entity.User;
import com.wihwin.repository.DeviceRepository;
import com.wihwin.repository.UserRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.LocalDateTime;
import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class DeviceServiceTest {

    @Mock
    private DeviceRepository deviceRepository;

    @Mock
    private UserRepository userRepository;

    @InjectMocks
    private DeviceService deviceService;

    private User testUser;
    private Device testDevice;
    private UUID userId;
    private UUID deviceId;

    @BeforeEach
    void setUp() {
        userId = UUID.randomUUID();
        deviceId = UUID.randomUUID();

        testUser = new User();
        testUser.setId(userId);
        testUser.setUsername("testuser");
        testUser.setEmail("test@example.com");
        testUser.setRole("customer");

        testDevice = new Device();
        testDevice.setId(deviceId);
        testDevice.setDeviceId("HELMET-001");
        testDevice.setUser(null);
        testDevice.setOnboarded(false);
        testDevice.setCreatedAt(LocalDateTime.now());
    }

    @Test
    void registerDevice_Success_ReturnsSuccessResponse() {
        
        DeviceRegisterRequest request = new DeviceRegisterRequest();
        request.setDeviceId("HELMET-001");

        when(userRepository.findById(userId)).thenReturn(Optional.of(testUser));
        when(deviceRepository.findByDeviceId("HELMET-001")).thenReturn(Optional.of(testDevice));
        when(deviceRepository.findByUserId(userId)).thenReturn(Optional.empty());
        when(deviceRepository.save(any(Device.class))).thenReturn(testDevice);

        ApiResponse response = deviceService.registerDevice(request, userId);

        assertTrue(response.getSuccess());
        assertEquals("Device registered successfully", response.getMessage());
        verify(deviceRepository).save(any(Device.class));
    }

    @Test
    void registerDevice_UserNotFound_ThrowsException() {
        
        DeviceRegisterRequest request = new DeviceRegisterRequest();
        request.setDeviceId("HELMET-001");

        when(userRepository.findById(userId)).thenReturn(Optional.empty());

        RuntimeException exception = assertThrows(RuntimeException.class,
                () -> deviceService.registerDevice(request, userId));

        assertEquals("User not found", exception.getMessage());
    }

    @Test
    void registerDevice_UserNotCustomer_ThrowsException() {
        
        DeviceRegisterRequest request = new DeviceRegisterRequest();
        request.setDeviceId("HELMET-001");
        
        testUser.setRole("doctor");
        when(userRepository.findById(userId)).thenReturn(Optional.of(testUser));

        RuntimeException exception = assertThrows(RuntimeException.class,
                () -> deviceService.registerDevice(request, userId));

        assertEquals("Only customers can register devices", exception.getMessage());
    }

    @Test
    void registerDevice_DeviceNotFound_ThrowsException() {
        
        DeviceRegisterRequest request = new DeviceRegisterRequest();
        request.setDeviceId("INVALID-DEVICE");

        when(userRepository.findById(userId)).thenReturn(Optional.of(testUser));
        when(deviceRepository.findByDeviceId("INVALID-DEVICE")).thenReturn(Optional.empty());

        RuntimeException exception = assertThrows(RuntimeException.class,
                () -> deviceService.registerDevice(request, userId));

        assertEquals("Device not found. Please ensure the device is initialized.", exception.getMessage());
    }

    @Test
    void registerDevice_DeviceAlreadyRegistered_ThrowsException() {
        
        DeviceRegisterRequest request = new DeviceRegisterRequest();
        request.setDeviceId("HELMET-001");
        
        User otherUser = new User();
        otherUser.setId(UUID.randomUUID());
        testDevice.setUser(otherUser);

        when(userRepository.findById(userId)).thenReturn(Optional.of(testUser));
        when(deviceRepository.findByDeviceId("HELMET-001")).thenReturn(Optional.of(testDevice));

        RuntimeException exception = assertThrows(RuntimeException.class,
                () -> deviceService.registerDevice(request, userId));

        assertEquals("Device is already registered to another user", exception.getMessage());
    }

    @Test
    void registerDevice_UserAlreadyHasDevice_ThrowsException() {
        
        DeviceRegisterRequest request = new DeviceRegisterRequest();
        request.setDeviceId("HELMET-001");
        
        Device existingDevice = new Device();
        existingDevice.setId(UUID.randomUUID());

        when(userRepository.findById(userId)).thenReturn(Optional.of(testUser));
        when(deviceRepository.findByDeviceId("HELMET-001")).thenReturn(Optional.of(testDevice));
        when(deviceRepository.findByUserId(userId)).thenReturn(Optional.of(existingDevice));

        
        RuntimeException exception = assertThrows(RuntimeException.class,
                () -> deviceService.registerDevice(request, userId));

        assertEquals("User already has a registered device", exception.getMessage());
    }

    @Test
    void getMyDevice_HasDevice_ReturnsDeviceResponse() {
        
        testDevice.setUser(testUser);
        when(deviceRepository.findByUserId(userId)).thenReturn(Optional.of(testDevice));

        DeviceResponse response = deviceService.getMyDevice(userId);

        assertTrue(response.getHasDevice());
        assertEquals(deviceId, response.getId());
        assertEquals("HELMET-001", response.getDeviceId());
    }

    @Test
    void getMyDevice_NoDevice_ReturnsEmptyResponse() {
        
        when(deviceRepository.findByUserId(userId)).thenReturn(Optional.empty());

        DeviceResponse response = deviceService.getMyDevice(userId);

        assertFalse(response.getHasDevice());
        assertNull(response.getId());
        assertNull(response.getDeviceId());
    }

    @Test
    void disconnectDevice_Success_ReturnsSuccessResponse() {
        
        testDevice.setUser(testUser);
        when(deviceRepository.findByUserId(userId)).thenReturn(Optional.of(testDevice));
        when(deviceRepository.save(any(Device.class))).thenReturn(testDevice);

        ApiResponse response = deviceService.disconnectDevice(userId);

        assertTrue(response.getSuccess());
        assertEquals("Device disconnected successfully", response.getMessage());
        verify(deviceRepository).save(any(Device.class));
    }

    @Test
    void disconnectDevice_NoDeviceRegistered_ThrowsException() {
        
        when(deviceRepository.findByUserId(userId)).thenReturn(Optional.empty());
 
        RuntimeException exception = assertThrows(RuntimeException.class,
                () -> deviceService.disconnectDevice(userId));

        assertEquals("No device registered to this user", exception.getMessage());
    }
}
