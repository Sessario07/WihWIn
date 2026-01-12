package com.wihwin.controller;

import com.wihwin.dto.ApiResponse;
import com.wihwin.security.UserPrincipal;
import com.wihwin.service.AnalysisService;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/analysis")
public class AnalysisController {

    private final AnalysisService analysisService;

    public AnalysisController(AnalysisService analysisService) {
        this.analysisService = analysisService;
    }

    @GetMapping("/trends")
    public ResponseEntity<?> getTrends(
            @RequestParam(defaultValue = "30") int days,
            @AuthenticationPrincipal UserPrincipal userPrincipal) {
        try {
            return ResponseEntity.ok(analysisService.getTrends(userPrincipal.getId(), days));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(new ApiResponse(false, "Error fetching trends: " + e.getMessage()));
        }
    }

    @GetMapping("/weekly-fatigue")
    public ResponseEntity<?> getWeeklyFatigue(@AuthenticationPrincipal UserPrincipal userPrincipal) {
        try {
            return ResponseEntity.ok(analysisService.getWeeklyFatigue(userPrincipal.getId()));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(new ApiResponse(false, "Error fetching weekly fatigue: " + e.getMessage()));
        }
    }

    @GetMapping("/heatmap")
    public ResponseEntity<?> getHeatmap(
            @RequestParam(defaultValue = "7") int days,
            @AuthenticationPrincipal UserPrincipal userPrincipal) {
        try {
            return ResponseEntity.ok(analysisService.getHeatmap(userPrincipal.getId(), days));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(new ApiResponse(false, "Error fetching heatmap: " + e.getMessage()));
        }
    }

    @GetMapping("/lf-hf-trend")
    public ResponseEntity<?> getLfHfTrend(
            @RequestParam(defaultValue = "30") int days,
            @AuthenticationPrincipal UserPrincipal userPrincipal) {
        try {
            return ResponseEntity.ok(analysisService.getLfHfTrend(userPrincipal.getId(), days));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(new ApiResponse(false, "Error fetching LF/HF trend: " + e.getMessage()));
        }
    }

    @GetMapping("/rides")
    public ResponseEntity<?> getRides(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size,
            @AuthenticationPrincipal UserPrincipal userPrincipal) {
        try {
            return ResponseEntity.ok(analysisService.getRides(userPrincipal.getId(), page, size));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(new ApiResponse(false, "Error fetching rides: " + e.getMessage()));
        }
    }

    @GetMapping("/fatigue-patterns")
    public ResponseEntity<?> getFatiguePatterns(@AuthenticationPrincipal UserPrincipal userPrincipal) {
        try {
            return ResponseEntity.ok(analysisService.getFatiguePatterns(userPrincipal.getId()));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(new ApiResponse(false, "Error fetching fatigue patterns: " + e.getMessage()));
        }
    }
}
