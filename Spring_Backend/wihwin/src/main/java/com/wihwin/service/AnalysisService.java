package com.wihwin.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestTemplate;

import java.util.Map;
import java.util.UUID;

@Service
public class AnalysisService {

    @Value("${fastapi.url}")
    private String fastapiUrl;

    private final RestTemplate restTemplate;

    public AnalysisService() {
        this.restTemplate = new RestTemplate();
    }

    public Object getTrends(UUID userId, int days) {
        try {
            String url = fastapiUrl + "/users/" + userId + "/daily-hrv-trend?days=" + days;
            return restTemplate.getForObject(url, Object.class);
        } catch (HttpClientErrorException e) {
            return Map.of("user_id", userId.toString(), "baseline_rmssd", 42.0, "period_days", days, "data", java.util.List.of());
        } catch (Exception e) {
            return Map.of("user_id", userId.toString(), "baseline_rmssd", 42.0, "period_days", days, "data", java.util.List.of());
        }
    }

    public Object getWeeklyFatigue(UUID userId) {
        try {
            String url = fastapiUrl + "/users/" + userId + "/weekly-fatigue-score";
            return restTemplate.getForObject(url, Object.class);
        } catch (HttpClientErrorException e) {
            return Map.of("user_id", userId.toString(), "scores", java.util.List.of());
        } catch (Exception e) {
            return Map.of("user_id", userId.toString(), "scores", java.util.List.of());
        }
    }

    public Object getHeatmap(UUID userId, int days) {
        try {
            String url = fastapiUrl + "/users/" + userId + "/hrv-heatmap?days=" + days;
            return restTemplate.getForObject(url, Object.class);
        } catch (HttpClientErrorException e) {
            return Map.of("user_id", userId.toString(), "days", days, "heatmap", java.util.List.of());
        } catch (Exception e) {
            return Map.of("user_id", userId.toString(), "days", days, "heatmap", java.util.List.of());
        }
    }

    public Object getLfHfTrend(UUID userId, int days) {
        try {
            String url = fastapiUrl + "/users/" + userId + "/lf-hf-trend?days=" + days;
            return restTemplate.getForObject(url, Object.class);
        } catch (HttpClientErrorException e) {
            return Map.of("user_id", userId.toString(), "threshold", 2.5, "period_days", days, "data", java.util.List.of());
        } catch (Exception e) {
            return Map.of("user_id", userId.toString(), "threshold", 2.5, "period_days", days, "data", java.util.List.of());
        }
    }

    public Object getRides(UUID userId, int page, int size) {
        try {
            String url = fastapiUrl + "/users/" + userId + "/rides?page=" + page + "&size=" + size;
            return restTemplate.getForObject(url, Object.class);
        } catch (HttpClientErrorException e) {
            return Map.of("user_id", userId.toString(), "total_rides", 0, "page", page, "size", size, "rides", java.util.List.of());
        } catch (Exception e) {
            return Map.of("user_id", userId.toString(), "total_rides", 0, "page", page, "size", size, "rides", java.util.List.of());
        }
    }

    public Object getFatiguePatterns(UUID userId) {
        try {
            String url = fastapiUrl + "/users/" + userId + "/fatigue-patterns";
            return restTemplate.getForObject(url, Object.class);
        } catch (HttpClientErrorException e) {
            return Map.of("user_id", userId.toString(), "patterns", Map.of("by_hour", java.util.List.of(), "by_day", java.util.List.of()));
        } catch (Exception e) {
            return Map.of("user_id", userId.toString(), "patterns", Map.of("by_hour", java.util.List.of(), "by_day", java.util.List.of()));
        }
    }
}
