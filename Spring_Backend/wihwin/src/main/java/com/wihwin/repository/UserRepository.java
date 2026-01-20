package com.wihwin.repository;

import com.wihwin.entity.User;

import jakarta.transaction.Transactional;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface UserRepository extends JpaRepository<User, UUID> {
    Optional<User> findByUsername(String username);
    Optional<User> findByEmail(String email);
    Boolean existsByUsername(String username);
    Boolean existsByEmail(String email);

    @Modifying
    @Transactional
    @Query("""
        update User u
        set u.lastLogin = :lastLogin
        where u.username = :username
    """)
    int updateLastLoginByUsername(
        @Param("username") String username,
        @Param("lastLogin") LocalDateTime lastLogin
    );
}
