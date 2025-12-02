package com.wihwin.controller;

import com.wihwin.security.UserPrincipal;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;

@RestController
@RequestMapping("/analysis")
public class AnalysisController {

    @Value("${fastapi.url}")
    private String fastapiUrl;

    private final RestTemplate restTemplate = new RestTemplate();

    @GetMapping("/trends")
    public ResponseEntity<?> getTrends(
            @RequestParam(defaultValue = "30") int days,
            @AuthenticationPrincipal UserPrincipal userPrincipal) {
        try {
            String url = fastapiUrl + "/users/" + userPrincipal.getId() + "/daily-hrv-trend?days=" + days;
            return ResponseEntity.ok(restTemplate.getForObject(url, Object.class));
        } catch (Exception e) {
            return ResponseEntity.status(500).body("Error fetching trends from FastAPI: " + e.getMessage());
        }
    }

    @GetMapping("/weekly-fatigue")
    public ResponseEntity<?> getWeeklyFatigue(@AuthenticationPrincipal UserPrincipal userPrincipal) {
        try {
            String url = fastapiUrl + "/users/" + userPrincipal.getId() + "/weekly-fatigue-score";
            return ResponseEntity.ok(restTemplate.getForObject(url, Object.class));
        } catch (Exception e) {
            return ResponseEntity.status(500).body("Error fetching weekly fatigue: " + e.getMessage());
        }
    }

    @GetMapping("/heatmap")
    public ResponseEntity<?> getHeatmap(
            @RequestParam(defaultValue = "7") int days,
            @AuthenticationPrincipal UserPrincipal userPrincipal) {
        try {
            String url = fastapiUrl + "/users/" + userPrincipal.getId() + "/hrv-heatmap?days=" + days;
            return ResponseEntity.ok(restTemplate.getForObject(url, Object.class));
        } catch (Exception e) {
            return ResponseEntity.status(500).body("Error fetching heatmap: " + e.getMessage());
        }
    }

    @GetMapping("/lf-hf-trend")
    public ResponseEntity<?> getLfHfTrend(
            @RequestParam(defaultValue = "30") int days,
            @AuthenticationPrincipal UserPrincipal userPrincipal) {
        try {
            String url = fastapiUrl + "/users/" + userPrincipal.getId() + "/lf-hf-trend?days=" + days;
            return ResponseEntity.ok(restTemplate.getForObject(url, Object.class));
        } catch (Exception e) {
            return ResponseEntity.status(500).body("Error fetching LF/HF trend: " + e.getMessage());
        }
    }

    @GetMapping("/rides")
    public ResponseEntity<?> getRides(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size,
            @AuthenticationPrincipal UserPrincipal userPrincipal) {
        try {
            String url = fastapiUrl + "/users/" + userPrincipal.getId() + "/rides?page=" + page + "&size=" + size;
            return ResponseEntity.ok(restTemplate.getForObject(url, Object.class));
        } catch (Exception e) {
            return ResponseEntity.status(500).body("Error fetching rides: " + e.getMessage());
        }
    }

    @GetMapping("/fatigue-patterns")
    public ResponseEntity<?> getFatiguePatterns(@AuthenticationPrincipal UserPrincipal userPrincipal) {
        try {
            String url = fastapiUrl + "/users/" + userPrincipal.getId() + "/fatigue-patterns";
            return ResponseEntity.ok(restTemplate.getForObject(url, Object.class));
        } catch (Exception e) {
            return ResponseEntity.status(500).body("Error fetching fatigue patterns: " + e.getMessage());
        }
    }
}
