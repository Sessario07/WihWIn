package com.wihwin.service;

import com.wihwin.dto.*;
import com.wihwin.entity.User;
import com.wihwin.repository.UserRepository;
import com.wihwin.security.JwtTokenProvider;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.crypto.password.PasswordEncoder;

import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class AuthServiceTest {

    @Mock
    private UserRepository userRepository;

    @Mock
    private PasswordEncoder passwordEncoder;

    @Mock
    private AuthenticationManager authenticationManager;

    @Mock
    private JwtTokenProvider tokenProvider;

    @InjectMocks
    private AuthService authService;

    private RegisterRequest registerRequest;
    private LoginRequest loginRequest;
    private User testUser;

    @BeforeEach
    void setUp() {
        registerRequest = new RegisterRequest();
        registerRequest.setUsername("testuser");
        registerRequest.setEmail("test@example.com");
        registerRequest.setPassword("password123");
        registerRequest.setRole("customer");

        loginRequest = new LoginRequest();
        loginRequest.setUsername("testuser");
        loginRequest.setPassword("password123");

        testUser = new User();
        testUser.setId(UUID.randomUUID());
        testUser.setUsername("testuser");
        testUser.setEmail("test@example.com");
        testUser.setPasswordHash("hashedPassword");
        testUser.setRole("customer");
    }

    @Test
    void register_Success_ReturnsAuthResponse() {
        
        when(userRepository.existsByUsername("testuser")).thenReturn(false);
        when(userRepository.existsByEmail("test@example.com")).thenReturn(false);
        when(passwordEncoder.encode("password123")).thenReturn("hashedPassword");
        when(userRepository.save(any(User.class))).thenReturn(testUser);
        
        Authentication mockAuth = mock(Authentication.class);
        when(authenticationManager.authenticate(any(UsernamePasswordAuthenticationToken.class)))
                .thenReturn(mockAuth);
        when(tokenProvider.generateToken(mockAuth)).thenReturn("test-jwt-token");
        
        AuthResponse response = authService.register(registerRequest);

        assertNotNull(response);
        assertEquals("test-jwt-token", response.getToken());
        assertEquals("testuser", response.getUsername());
        assertEquals("test@example.com", response.getEmail());
        assertEquals("customer", response.getRole());
        
        verify(userRepository).save(any(User.class));
    }

    @Test
    void register_UsernameAlreadyExists_ThrowsException() {
        
        when(userRepository.existsByUsername("testuser")).thenReturn(true);

        RuntimeException exception = assertThrows(RuntimeException.class, 
                () -> authService.register(registerRequest));
        
        assertEquals("Username already taken", exception.getMessage());
        verify(userRepository, never()).save(any(User.class));
    }

    @Test
    void register_EmailAlreadyExists_ThrowsException() {
        
        when(userRepository.existsByUsername("testuser")).thenReturn(false);
        when(userRepository.existsByEmail("test@example.com")).thenReturn(true);

        RuntimeException exception = assertThrows(RuntimeException.class, 
                () -> authService.register(registerRequest));
        
        assertEquals("Email is already in use", exception.getMessage());
        verify(userRepository, never()).save(any(User.class));
    }

    @Test
    void login_Success_ReturnsAuthResponse() {
        
        Authentication mockAuth = mock(Authentication.class);
        when(authenticationManager.authenticate(any(UsernamePasswordAuthenticationToken.class)))
                .thenReturn(mockAuth);
        when(tokenProvider.generateToken(mockAuth)).thenReturn("test-jwt-token");
        when(userRepository.findByUsername("testuser")).thenReturn(Optional.of(testUser));
        when(userRepository.save(any(User.class))).thenReturn(testUser);

        AuthResponse response = authService.login(loginRequest);

        assertNotNull(response);
        assertEquals("test-jwt-token", response.getToken());
        assertEquals("testuser", response.getUsername());
        assertEquals("test@example.com", response.getEmail());
        
        verify(userRepository).save(any(User.class)); 
    }

    @Test
    void login_InvalidCredentials_ThrowsException() {
        
        when(authenticationManager.authenticate(any(UsernamePasswordAuthenticationToken.class)))
                .thenThrow(new BadCredentialsException("Invalid credentials"));

        assertThrows(BadCredentialsException.class, 
                () -> authService.login(loginRequest));
    }

    @Test
    void login_UserNotFound_ThrowsException() {
        
        Authentication mockAuth = mock(Authentication.class);
        when(authenticationManager.authenticate(any(UsernamePasswordAuthenticationToken.class)))
                .thenReturn(mockAuth);
        when(tokenProvider.generateToken(mockAuth)).thenReturn("test-jwt-token");
        when(userRepository.findByUsername("testuser")).thenReturn(Optional.empty());

        
        RuntimeException exception = assertThrows(RuntimeException.class, 
                () -> authService.login(loginRequest));
        
        assertEquals("User not found", exception.getMessage());
    }
}
