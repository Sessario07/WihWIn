package com.wihwin.service;

import com.wihwin.dto.*;
import com.wihwin.entity.*;
import com.wihwin.repository.*;
import com.wihwin.security.JwtTokenProvider;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

@Service
public class AuthService {

    private final UserRepository userRepository;
    private final CustomerProfileRepository customerProfileRepository;
    private final DoctorProfileRepository doctorProfileRepository;
    private final DeviceRepository deviceRepository;
    private final PasswordEncoder passwordEncoder;
    private final AuthenticationManager authenticationManager;
    private final JwtTokenProvider tokenProvider;

    public AuthService(UserRepository userRepository,
                      CustomerProfileRepository customerProfileRepository,
                      DoctorProfileRepository doctorProfileRepository,
                      DeviceRepository deviceRepository,
                      PasswordEncoder passwordEncoder,
                      AuthenticationManager authenticationManager,
                      JwtTokenProvider tokenProvider) {
        this.userRepository = userRepository;
        this.customerProfileRepository = customerProfileRepository;
        this.doctorProfileRepository = doctorProfileRepository;
        this.deviceRepository = deviceRepository;
        this.passwordEncoder = passwordEncoder;
        this.authenticationManager = authenticationManager;
        this.tokenProvider = tokenProvider;
    }

    @Transactional
    public AuthResponse register(RegisterRequest request) {
        if (userRepository.existsByUsername(request.getUsername())) {
            throw new RuntimeException("Username is already taken");
        }

        if (userRepository.existsByEmail(request.getEmail())) {
            throw new RuntimeException("Email is already in use");
        }

        User user = new User();
        user.setUsername(request.getUsername());
        user.setEmail(request.getEmail());
        user.setPasswordHash(passwordEncoder.encode(request.getPassword()));
        user.setRole(request.getRole());

        user = userRepository.save(user);

        Authentication authentication = authenticationManager.authenticate(
            new UsernamePasswordAuthenticationToken(request.getUsername(), request.getPassword())
        );

        SecurityContextHolder.getContext().setAuthentication(authentication);
        String jwt = tokenProvider.generateToken(authentication);

        return new AuthResponse(jwt, user.getId(), user.getUsername(), user.getEmail(), user.getRole());
    }

    public AuthResponse login(LoginRequest request) {
        Authentication authentication = authenticationManager.authenticate(
            new UsernamePasswordAuthenticationToken(request.getUsername(), request.getPassword())
        );

        SecurityContextHolder.getContext().setAuthentication(authentication);
        String jwt = tokenProvider.generateToken(authentication);

        User user = userRepository.findByUsername(request.getUsername())
                .orElseThrow(() -> new RuntimeException("User not found"));

        user.setLastLogin(LocalDateTime.now());
        userRepository.save(user);

        return new AuthResponse(jwt, user.getId(), user.getUsername(), user.getEmail(), user.getRole());
    }

    @Transactional
    public ApiResponse createCustomerProfile(CustomerProfileRequest request, User user) {
        if (!user.getRole().equals("customer")) {
            throw new RuntimeException("Only customers can create customer profiles");
        }

        CustomerProfile profile = new CustomerProfile();
        profile.setUser(user);
        profile.setBloodType(request.getBloodType());
        profile.setAllergies(request.getAllergies());
        profile.setPreExistingConditions(request.getPreExistingConditions());
        profile.setCurrentMedications(request.getCurrentMedications());
        profile.setRecentMedicalHistory(request.getRecentMedicalHistory());
        profile.setAdvanceDirectives(request.getAdvanceDirectives());
        profile.setEmergencyContactName(request.getEmergencyContactName());
        profile.setEmergencyContactPhone(request.getEmergencyContactPhone());

        customerProfileRepository.save(profile);

        return new ApiResponse(true, "Customer profile created successfully");
    }

    @Transactional
    public ApiResponse createDoctorProfile(DoctorProfileRequest request, User user) {
        if (!user.getRole().equals("doctor")) {
            throw new RuntimeException("Only doctors can create doctor profiles");
        }

        DoctorProfile profile = new DoctorProfile();
        profile.setUser(user);
        profile.setHospitalName(request.getHospitalName());
        profile.setLat(request.getLat());
        profile.setLon(request.getLon());
        profile.setSpecialization(request.getSpecialization());
        profile.setLicenseNumber(request.getLicenseNumber());

        doctorProfileRepository.save(profile);

        return new ApiResponse(true, "Doctor profile created successfully");
    }

    @Transactional
    public ApiResponse registerDevice(DeviceRegisterRequest request, User user) {
        if (!user.getRole().equals("customer")) {
            throw new RuntimeException("Only customers can register devices");
        }

        // Check if device exists
        Device device = deviceRepository.findByDeviceId(request.getDeviceId())
                .orElse(null);

        if (device == null) {
            throw new RuntimeException("Device not found. Please ensure the device is initialized.");
        }

        if (device.getUser() != null) {
            throw new RuntimeException("Device is already registered to another user");
        }

        // Check if user already has a device
        deviceRepository.findByUserId(user.getId()).ifPresent(existingDevice -> {
            throw new RuntimeException("User already has a registered device");
        });

        device.setUser(user);
        deviceRepository.save(device);

        return new ApiResponse(true, "Device registered successfully");
    }
}
