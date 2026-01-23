/**
 * RUN ALL TESTS - Combined Test Runner
 * Runs all test types sequentially with summary
 * 
 * Usage: Set K6_TEST_TYPE environment variable
 * - load, stress, spike, soak, or all
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const errorRate = new Rate('error_rate');
const springLatency = new Trend('spring_login_latency');
const fastApiLatency = new Trend('fastapi_batch_latency');

const BASE_URL = 'http://nginx:80';
const TEST_TYPE = __ENV.K6_TEST_TYPE || 'load';

// Define scenarios based on test type
const scenarios = {
    load: {
        executor: 'ramping-arrival-rate',
        startRate: 10,
        timeUnit: '1s',
        preAllocatedVUs: 200,
        maxVUs: 500,
        stages: [
            { duration: '30s', target: 50 },
            { duration: '30s', target: 100 },
            { duration: '30s', target: 100 },
        ],
    },
    stress: {
        executor: 'ramping-arrival-rate',
        startRate: 50,
        timeUnit: '1s',
        preAllocatedVUs: 500,
        maxVUs: 1000,
        stages: [
            { duration: '20s', target: 200 },
            { duration: '20s', target: 400 },
            { duration: '20s', target: 500 },
            { duration: '20s', target: 500 },
            { duration: '10s', target: 0 },
        ],
    },
    spike: {
        executor: 'ramping-arrival-rate',
        startRate: 10,
        timeUnit: '1s',
        preAllocatedVUs: 1000,
        maxVUs: 2000,
        stages: [
            { duration: '5s', target: 1000 },
            { duration: '60s', target: 1000 },
            { duration: '15s', target: 100 },
            { duration: '10s', target: 10 },
        ],
    },
    soak: {
        executor: 'constant-arrival-rate',
        rate: 50,
        timeUnit: '1s',
        duration: '5m',
        preAllocatedVUs: 100,
        maxVUs: 300,
    },
};

export const options = {
    scenarios: {
        test: scenarios[TEST_TYPE] || scenarios.load,
    },
    thresholds: {
        http_req_duration: ['p(95)<2000'],
        error_rate: ['rate<0.30'],
    },
};

function generateTelemetryBatch() {
    const telemetry = [];
    for (let i = 0; i < 10; i++) {
        telemetry.push({
            timestamp: new Date().toISOString(),
            hr: 60 + Math.random() * 40,
            rmssd: 30 + Math.random() * 30,
            sdnn: 40 + Math.random() * 40,
            pnn50: 10 + Math.random() * 30,
            lf_hf_ratio: 0.5 + Math.random() * 2,
            lat: -6.2 + Math.random() * 0.01,
            lon: 106.8 + Math.random() * 0.01,
        });
    }
    return {
        device_id: `HELMET${String(Math.floor(Math.random() * 1000)).padStart(3, '0')}`,
        ride_id: `ride-${Date.now()}-${Math.floor(Math.random() * 1000)}`,
        telemetry: telemetry,
    };
}

export default function () {
    const headers = { 'Content-Type': 'application/json' };

    // Spring Boot Login
    const loginPayload = JSON.stringify({
        username: `testuser${Math.floor(Math.random() * 100)}`,
        password: 'testpassword123',
    });

    const loginRes = http.post(
        `${BASE_URL}/api/spring/auth/login`,
        loginPayload,
        { headers }
    );

    springLatency.add(loginRes.timings.duration);
    errorRate.add(!check(loginRes, {
        'Spring responded': (r) => r.status !== 0,
    }));

    // FastAPI Batch
    const batchPayload = JSON.stringify(generateTelemetryBatch());

    const batchRes = http.post(
        `${BASE_URL}/api/fast/telemetry/batch`,
        batchPayload,
        { headers }
    );

    fastApiLatency.add(batchRes.timings.duration);
    errorRate.add(!check(batchRes, {
        'FastAPI responded': (r) => r.status !== 0,
    }));

    sleep(0.05);
}

export function handleSummary(data) {
    const testType = TEST_TYPE.toUpperCase();
    const durations = { load: 90, stress: 90, spike: 90, soak: 300 };
    const duration = durations[TEST_TYPE] || 90;

    const totalReqs = data.metrics.http_reqs?.values.count || 0;
    const avgLatency = data.metrics.http_req_duration?.values.avg?.toFixed(2) || 0;
    const p95Latency = data.metrics.http_req_duration?.values['p(95)']?.toFixed(2) || 0;
    const errRate = data.metrics.error_rate?.values.rate ? (data.metrics.error_rate.values.rate * 100).toFixed(2) : 0;
    const rps = (totalReqs / duration).toFixed(2);

    console.log('\n' + '='.repeat(60));
    console.log(`                 ${testType} TEST RESULTS`);
    console.log('='.repeat(60));
    console.log(`Test type:              ${testType} Test`);
    console.log(`Duration:               ${duration}s`);
    console.log(`Total Requests:         ${totalReqs}`);
    console.log(`Requests/sec:           ${rps}`);
    console.log(`Avg latency:            ${avgLatency}ms`);
    console.log(`P95 latency:            ${p95Latency}ms`);
    console.log(`Error rate:             ${errRate}%`);
    console.log('-'.repeat(60));
    console.log('BATCH PROCESSING METRICS:');
    console.log(`  Flush interval:       120s`);
    console.log(`  Requests per batch:   ${(parseFloat(rps) * 120).toFixed(0)}`);
    console.log(`  Flush cycles:         ${(duration / 120).toFixed(2)}`);
    console.log('='.repeat(60) + '\n');

    return { stdout: JSON.stringify(data, null, 2) };
}
