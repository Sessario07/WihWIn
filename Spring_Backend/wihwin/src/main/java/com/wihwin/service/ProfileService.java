package com.wihwin.service;

import com.wihwin.dto.ApiResponse;
import com.wihwin.dto.CustomerProfileRequest;
import com.wihwin.dto.DoctorProfileRequest;
import com.wihwin.entity.CustomerProfile;
import com.wihwin.entity.DoctorProfile;
import com.wihwin.entity.User;
import com.wihwin.repository.CustomerProfileRepository;
import com.wihwin.repository.DoctorProfileRepository;
import com.wihwin.repository.UserRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.UUID;

@Service
public class ProfileService {

    private final UserRepository userRepository;
    private final CustomerProfileRepository customerProfileRepository;
    private final DoctorProfileRepository doctorProfileRepository;

    public ProfileService(UserRepository userRepository,
                         CustomerProfileRepository customerProfileRepository,
                         DoctorProfileRepository doctorProfileRepository) {
        this.userRepository = userRepository;
        this.customerProfileRepository = customerProfileRepository;
        this.doctorProfileRepository = doctorProfileRepository;
    }

    @Transactional
    public ApiResponse createCustomerProfile(CustomerProfileRequest request, UUID userId) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new RuntimeException("User not found"));

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
    public ApiResponse createDoctorProfile(DoctorProfileRequest request, UUID userId) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new RuntimeException("User not found"));

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
}
