package com.wihwin.service;

import com.wihwin.dto.*;
import com.wihwin.entity.*;
import com.wihwin.repository.*;
import com.wihwin.security.JwtTokenProvider;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.scheduling.annotation.Async;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.wihwin.security.UserPrincipal;
import java.time.LocalDateTime;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.concurrent.Executor;

@Service
public class AuthService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final AuthenticationManager authenticationManager;
    private final JwtTokenProvider tokenProvider;
    private final Executor bcryptExecutor;

    public AuthService(UserRepository userRepository,
                      PasswordEncoder passwordEncoder,
                      AuthenticationManager authenticationManager,
                      JwtTokenProvider tokenProvider, 
                      @Qualifier("bcryptExecutor") Executor bcryptExecutor) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.authenticationManager = authenticationManager;
        this.tokenProvider = tokenProvider;
        this.bcryptExecutor = bcryptExecutor;
    }

    @Transactional
    public AuthResponse register(RegisterRequest request) {
        if (userRepository.existsByUsername(request.getUsername())) {
            throw new RuntimeException("Username already taken");
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

        String jwt = tokenProvider.generateTokenForUser(user.getId().toString());

        return new AuthResponse(jwt, user.getId(), user.getUsername(), user.getEmail(), user.getRole());
    }

    public AuthResponse login(LoginRequest request) {

        Authentication authentication;
        try {
            authentication =
                CompletableFuture.supplyAsync(
                    () -> authenticationManager.authenticate(
                        new UsernamePasswordAuthenticationToken(
                            request.getUsername(),
                            request.getPassword()
                        )
                    ),
                    bcryptExecutor
                ).join();
        } catch (CompletionException e) {
            
            throw (RuntimeException) e.getCause();
        }
        SecurityContextHolder.getContext().setAuthentication(authentication);
        String jwt = tokenProvider.generateToken(authentication);
        
        UserPrincipal principal = (UserPrincipal) authentication.getPrincipal();
    
        // Fire-and-forget: update last login asynchronously
        updateLastLoginAsync(principal.getUsername());

        return new AuthResponse(jwt, principal.getId(), principal.getUsername(), principal.getEmail(), principal.getRole());
    }

    @Async
    @Transactional
    public void updateLastLoginAsync(String username) {
        userRepository.updateLastLoginByUsername(username, LocalDateTime.now());
    }
}
