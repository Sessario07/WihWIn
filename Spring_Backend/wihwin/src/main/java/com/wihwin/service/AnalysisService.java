package com.wihwin.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

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
        String url = fastapiUrl + "/users/" + userId + "/daily-hrv-trend?days=" + days;
        return restTemplate.getForObject(url, Object.class);
    }

    public Object getWeeklyFatigue(UUID userId) {
        String url = fastapiUrl + "/users/" + userId + "/weekly-fatigue-score";
        return restTemplate.getForObject(url, Object.class);
    }

    public Object getHeatmap(UUID userId, int days) {
        String url = fastapiUrl + "/users/" + userId + "/hrv-heatmap?days=" + days;
        return restTemplate.getForObject(url, Object.class);
    }

    public Object getLfHfTrend(UUID userId, int days) {
        String url = fastapiUrl + "/users/" + userId + "/lf-hf-trend?days=" + days;
        return restTemplate.getForObject(url, Object.class);
    }

    public Object getRides(UUID userId, int page, int size) {
        String url = fastapiUrl + "/users/" + userId + "/rides?page=" + page + "&size=" + size;
        return restTemplate.getForObject(url, Object.class);
    }

    public Object getFatiguePatterns(UUID userId) {
        String url = fastapiUrl + "/users/" + userId + "/fatigue-patterns";
        return restTemplate.getForObject(url, Object.class);
    }
}
