package com.wihwin.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.CreationTimestamp;

import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Table(name = "devices")
@Data
@NoArgsConstructor
@AllArgsConstructor
public class Device {
    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @ManyToOne
    @JoinColumn(name = "user_id")
    private User user;

    @Column(name = "device_id", unique = true, nullable = false, length = 64)
    private String deviceId;

    @Column(nullable = false)
    private Boolean onboarded = false;

    @Column(name = "last_seen")
    private LocalDateTime lastSeen;

    @Column(name = "battery_pct")
    private Integer batteryPct;

    @CreationTimestamp
    @Column(name = "created_at")
    private LocalDateTime createdAt;
}
