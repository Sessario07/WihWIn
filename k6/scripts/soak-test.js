import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';


const errorRate = new Rate('error_rate');
const springLoginLatency = new Trend('spring_login_latency');
const fastApiBatchLatency = new Trend('fastapi_batch_latency');
const springLoginSuccess = new Counter('spring_login_success');
const springLoginFailed = new Counter('spring_login_failed');
const fastApiBatchSuccess = new Counter('fastapi_batch_success');
const fastApiBatchFailed = new Counter('fastapi_batch_failed');

const BASE_URL = 'http://nginx:80';
const REGISTRATION_COUNT = 15;

export const options = {
    scenarios: {
        // Scenario 1: Spring Boot Login - Soak (25 RPS sustained)
        spring_login: {
            executor: 'constant-arrival-rate',
            exec: 'testSpringLogin',
            rate: 25,
            timeUnit: '1s',
            duration: '5m',
            preAllocatedVUs: 50,
            maxVUs: 150,
        },
        // Scenario 2: FastAPI Batch Telemetry - Soak (50 RPS sustained)
        fastapi_batch: {
            executor: 'constant-arrival-rate',
            exec: 'testFastApiBatch',
            rate: 50,
            timeUnit: '1s',
            duration: '5m',
            preAllocatedVUs: 100,
            maxVUs: 300,
        },
    },
    thresholds: {
        http_req_duration: ['p(95)<1000'],     // 95% under 1s
        error_rate: ['rate<0.02'],              // Error rate under 2%
        spring_login_latency: ['p(95)<800'],    // Spring login P95 under 800ms
        fastapi_batch_latency: ['p(95)<800'],   // FastAPI batch P95 under 800ms
    },
};

// Generate random user credentials
function generateUserCredentials(index) {
    const timestamp = Date.now();
    const random = Math.floor(Math.random() * 10000);
    return {
        username: `soak_user_${index}_${timestamp}_${random}`,
        email: `soak${index}_${timestamp}_${random}@example.com`,
        password: `SoakPass123!${index}`,
        role: 'customer',
    };
}

// Register a single user
function registerUser(credentials) {
    const headers = { 'Content-Type': 'application/json' };
    const payload = JSON.stringify(credentials);
    
    const response = http.post(
        `${BASE_URL}/api/spring/auth/register`,
        payload,
        { headers, tags: { endpoint: 'registration' } }
    );
    
    const success = check(response, {
        'Registration status is 200': (r) => r.status === 200,
        'Registration returns token': (r) => {
            try {
                const body = JSON.parse(r.body);
                return body.token && body.token.length > 0;
            } catch (e) {
                return false;
            }
        },
    });
    
    if (success && response.status === 200) {
        try {
            const body = JSON.parse(response.body);
            return {
                username: credentials.username,
                password: credentials.password,
                token: body.token,
                userId: body.userId,
            };
        } catch (e) {
            console.error(`Failed to parse registration response: ${e.message}`);
            return null;
        }
    }
    
    console.error(`Registration failed for ${credentials.username}: Status ${response.status}`);
    return null;
}

// Setup phase - Register users before soak test
export function setup() {
    console.log('\n' + '='.repeat(60));
    console.log('SETUP PHASE: Registering test users for SOAK test...');
    console.log('='.repeat(60));
    
    const users = [];
    let successCount = 0;
    
    for (let i = 0; i < REGISTRATION_COUNT; i++) {
        const credentials = generateUserCredentials(i);
        console.log(`Registering user ${i + 1}/${REGISTRATION_COUNT}: ${credentials.username}`);
        
        const registeredUser = registerUser(credentials);
        
        if (registeredUser) {
            users.push(registeredUser);
            successCount++;
            console.log(`✓ Successfully registered: ${registeredUser.username}`);
        }
        
        sleep(0.5);
    }
    
    console.log('-'.repeat(60));
    console.log(`Registration complete: ${successCount}/${REGISTRATION_COUNT} successful`);
    console.log('='.repeat(60) + '\n');
    
    if (users.length === 0) {
        throw new Error('No users registered successfully. Cannot proceed with soak test.');
    }
    
    return { users };
}

// Generate telemetry batch payload
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

// Test function for Spring Login
export function testSpringLogin(data) {
    if (!data.users || data.users.length === 0) {
        console.error('No registered users available for login test');
        return;
    }
    
    const headers = { 'Content-Type': 'application/json' };
    const user = data.users[Math.floor(Math.random() * data.users.length)];
    
    const loginPayload = JSON.stringify({
        username: user.username,
        password: user.password,
    });
    
    const loginRes = http.post(
        `${BASE_URL}/api/spring/auth/login`,
        loginPayload,
        { headers, tags: { endpoint: 'spring_login' } }
    );
    
    springLoginLatency.add(loginRes.timings.duration);
    
    const loginSuccess = check(loginRes, {
        'Spring login status is 200': (r) => r.status === 200,
    });
    
    if (loginSuccess) {
        springLoginSuccess.add(1);
    } else {
        springLoginFailed.add(1);
        errorRate.add(1);
    }
}

// Test function for FastAPI Batch
export function testFastApiBatch() {
    const headers = { 'Content-Type': 'application/json' };
    const batchPayload = JSON.stringify(generateTelemetryBatch());
    
    const batchRes = http.post(
        `${BASE_URL}/api/fast/telemetry/batch`,
        batchPayload,
        { headers, tags: { endpoint: 'fastapi_batch' } }
    );
    
    fastApiBatchLatency.add(batchRes.timings.duration);
    
    const batchSuccess = check(batchRes, {
        'FastAPI batch status is 200': (r) => r.status === 200,
    });
    
    if (batchSuccess) {
        fastApiBatchSuccess.add(1);
    } else {
        fastApiBatchFailed.add(1);
        errorRate.add(1);
    }
}

// Summary handler
export function handleSummary(data) {
    const metrics = data.metrics;
    
    const totalReqs = metrics.http_reqs ? metrics.http_reqs.values.count : 0;
    const avgLatency = metrics.http_req_duration ? metrics.http_req_duration.values.avg.toFixed(2) : 0;
    const p95Latency = metrics.http_req_duration ? metrics.http_req_duration.values['p(95)'].toFixed(2) : 0;
    const errRate = metrics.error_rate ? (metrics.error_rate.values.rate * 100).toFixed(2) : 0;
    
    const springAvg = metrics.spring_login_latency ? metrics.spring_login_latency.values.avg.toFixed(2) : 0;
    const springP95 = metrics.spring_login_latency ? metrics.spring_login_latency.values['p(95)'].toFixed(2) : 0;
    const springSuccess = metrics.spring_login_success ? metrics.spring_login_success.values.count : 0;
    const springFailed = metrics.spring_login_failed ? metrics.spring_login_failed.values.count : 0;
    const springTotal = springSuccess + springFailed;
    const springRps = springTotal > 0 ? (springTotal / 300).toFixed(2) : 0;
    
    const fastApiAvg = metrics.fastapi_batch_latency ? metrics.fastapi_batch_latency.values.avg.toFixed(2) : 0;
    const fastApiP95 = metrics.fastapi_batch_latency ? metrics.fastapi_batch_latency.values['p(95)'].toFixed(2) : 0;
    const fastApiSuccess = metrics.fastapi_batch_success ? metrics.fastapi_batch_success.values.count : 0;
    const fastApiFailed = metrics.fastapi_batch_failed ? metrics.fastapi_batch_failed.values.count : 0;
    const fastApiTotal = fastApiSuccess + fastApiFailed;
    const fastApiRps = fastApiTotal > 0 ? (fastApiTotal / 300).toFixed(2) : 0;
    
    console.log('\n' + '='.repeat(70));
    console.log('                    SOAK TEST RESULTS');
    console.log('='.repeat(70));
    console.log(`Test Type:              Soak Test (Sustained Load)`);
    console.log(`Test Duration:          300s (5m 0s)`);
    console.log(`Total Requests:         ${totalReqs}`);
    console.log(`Overall Avg Latency:    ${avgLatency}ms`);
    console.log(`Overall P95 Latency:    ${p95Latency}ms`);
    console.log(`Overall Error Rate:     ${errRate}%`);
    console.log('='.repeat(70));
    
    console.log('\nSPRING BOOT LOGIN ENDPOINT (SOAK):');
    console.log('-'.repeat(70));
    console.log(`  Target RPS:           25 (sustained)`);
    console.log(`  Actual Avg RPS:       ${springRps}`);
    console.log(`  Total Requests:       ${springTotal}`);
    console.log(`  Successful:           ${springSuccess} (${springTotal > 0 ? ((springSuccess/springTotal)*100).toFixed(2) : 0}%)`);
    console.log(`  Failed:               ${springFailed} (${springTotal > 0 ? ((springFailed/springTotal)*100).toFixed(2) : 0}%)`);
    console.log(`  Avg Latency:          ${springAvg}ms`);
    console.log(`  P95 Latency:          ${springP95}ms`);
    
    console.log('\nFASTAPI BATCH TELEMETRY ENDPOINT (SOAK):');
    console.log('-'.repeat(70));
    console.log(`  Target RPS:           50 (sustained)`);
    console.log(`  Actual Avg RPS:       ${fastApiRps}`);
    console.log(`  Total Requests:       ${fastApiTotal}`);
    console.log(`  Successful:           ${fastApiSuccess} (${fastApiTotal > 0 ? ((fastApiSuccess/fastApiTotal)*100).toFixed(2) : 0}%)`);
    console.log(`  Failed:               ${fastApiFailed} (${fastApiTotal > 0 ? ((fastApiFailed/fastApiTotal)*100).toFixed(2) : 0}%)`);
    console.log(`  Avg Latency:          ${fastApiAvg}ms`);
    console.log(`  P95 Latency:          ${fastApiP95}ms`);
    
    console.log('\nBATCH PROCESSING METRICS (FastAPI):');
    console.log('-'.repeat(70));
    console.log(`  Flush interval:       120s`);
    console.log(`  Requests per batch:   ${(parseFloat(fastApiRps) * 120).toFixed(0)}`);
    console.log(`  Flush cycles:         ${(300 / 120).toFixed(2)}`);
    console.log('='.repeat(70) + '\n');
    
    return {
        stdout: JSON.stringify(data, null, 2),
    };
}