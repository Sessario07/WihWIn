#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <math.h>
#include "MQTTClient.h"
#include <curl/curl.h>
#include <stdbool.h>

#define ADDRESS     "tcp://localhost:1883"
#define CLIENTID    "SmartHelmetSim"
#define DEVICE_ID   "HELMET001"
#define QOS         1
#define TIMEOUT     10000L
#define ONBOARD_SAMPLES 12  // 1 minute (12 samples at 5-second intervals) for faster testing
#define NORMAL_OPERATION_CYCLES 100

// PPG Configuration
#define PPG_SAMPLE_RATE 50      // 50 Hz sampling rate
#define PPG_BUFFER_SECONDS 5    // Send every 5 seconds
#define PPG_BUFFER_SIZE (PPG_SAMPLE_RATE * PPG_BUFFER_SECONDS)  // 250 samples per transmission

// MQTT Authentication (must match mosquitto password file)
#define MQTT_USERNAME "helmet"
#define MQTT_PASSWORD "wihwin123"

// FastAPI URL (through Nginx reverse proxy)
#define FASTAPI_BASE_URL "http://localhost/api/fast"

// Dynamic topic generation
char TOPIC_TELE[128];
char TOPIC_CMD[128];
char TOPIC_BASELINE[128];
char TOPIC_ACCEL[128];

// PPG simulation parameters
#define PI 3.14159265358979323846

struct baseline_metrics {
    double mean_hr;
    double sdnn;
    double rmssd;
    double pnn50;
    double lf_hf_ratio;
    double sd1_sd2_ratio;
};

struct baseline_metrics computed_baseline;
bool isOnboarding = false;
bool has_baseline = false;
int onboard_count = 0;
int alert_flag = 0;

// Callback to capture response from curl
size_t write_callback(void *contents, size_t size, size_t nmemb, void *userp) {
    size_t realsize = size * nmemb;
    strncat((char *)userp, (char *)contents, realsize);
    return realsize;
}

// Generate realistic PPG waveform
void generate_ppg_signal(int *ppg_buffer, int size, double heart_rate, bool add_noise) {
    double samples_per_beat = (60.0 / heart_rate) * PPG_SAMPLE_RATE;
    
    for (int i = 0; i < size; i++) {
        double t = (double)i / PPG_SAMPLE_RATE;
        double phase = fmod(i, samples_per_beat) / samples_per_beat;
        
        // Simulate PPG waveform with systolic peak and dicrotic notch
        double systolic = exp(-pow((phase - 0.2) * 10, 2)) * 0.8;
        double dicrotic = exp(-pow((phase - 0.4) * 15, 2)) * 0.3;
        double baseline_wave = 0.1 * sin(2 * PI * 0.1 * t);  // Respiratory variation
        
        double signal = systolic + dicrotic + baseline_wave;
        
        // Add some HRV (slight variations in beat timing)
        double hrv_noise = 0.02 * sin(2 * PI * 0.15 * t);
        signal += hrv_noise;
        
        // Add sensor noise if requested
        if (add_noise) {
            signal += ((rand() % 100) - 50) / 1000.0;
        }
        
        // Scale to 12-bit ADC range (0-4095) with baseline offset
        ppg_buffer[i] = (int)(2048 + signal * 1500);
        
        // Clamp to valid range
        if (ppg_buffer[i] < 0) ppg_buffer[i] = 0;
        if (ppg_buffer[i] > 4095) ppg_buffer[i] = 4095;
    }
}

// Generate accelerometer data (normal riding vs crash)
void generate_accel_data(double *accel_x, double *accel_y, double *accel_z, bool simulate_crash) {
    if (simulate_crash) {
        // Crash: sudden high G-force impact
        *accel_x = ((rand() % 1000) - 500) / 50.0;  // -10 to +10 G
        *accel_y = ((rand() % 1000) - 500) / 50.0;
        *accel_z = ((rand() % 500) / 50.0);  // Impact usually upward
    } else {
        // Normal riding: small vibrations around gravity
        *accel_x = ((rand() % 200) - 100) / 100.0;  // -1 to +1 G
        *accel_y = ((rand() % 200) - 100) / 100.0;
        *accel_z = 9.8 + ((rand() % 100) - 50) / 100.0;  // ~9.8 G (gravity)
    }
}

int messageArrivedCB(void *context, char *topicName, int topicLen, MQTTClient_message *message) {
    char *payload = (char *)message->payload;
    
    char payload_str[512];
    int len = message->payloadlen < 511 ? message->payloadlen : 511;
    memcpy(payload_str, payload, len);
    payload_str[len] = '\0';
    
    if (strstr(payload_str, "\"vibrate\": true") || strstr(payload_str, "\"vibrate\":true")) {
        printf("    🚨 HELMET VIBRATING - DROWSINESS DETECTED!\n");
        alert_flag = 1;
    } else if (strstr(payload_str, "\"crash_detected\": true") || strstr(payload_str, "\"crash_detected\":true")) {
        printf("    💥 CRASH DETECTED - EMERGENCY SERVICES NOTIFIED!\n");
    } else {
        alert_flag = 0;
    }
    
    fflush(stdout);
    MQTTClient_freeMessage(&message);
    MQTTClient_free(topicName);
    return 1;
}

void parse_baseline_from_response(const char *response) {
    char *ptr;
    
    if ((ptr = strstr(response, "\"mean_hr\":")) != NULL) {
        sscanf(ptr, "\"mean_hr\": %lf", &computed_baseline.mean_hr);
    }
    if ((ptr = strstr(response, "\"sdnn\":")) != NULL) {
        sscanf(ptr, "\"sdnn\": %lf", &computed_baseline.sdnn);
    }
    if ((ptr = strstr(response, "\"rmssd\":")) != NULL) {
        sscanf(ptr, "\"rmssd\": %lf", &computed_baseline.rmssd);
    }
    if ((ptr = strstr(response, "\"pnn50\":")) != NULL) {
        sscanf(ptr, "\"pnn50\": %lf", &computed_baseline.pnn50);
    }
    if ((ptr = strstr(response, "\"lf_hf_ratio\":")) != NULL) {
        sscanf(ptr, "\"lf_hf_ratio\": %lf", &computed_baseline.lf_hf_ratio);
    }
    if ((ptr = strstr(response, "\"sd1_sd2_ratio\":")) != NULL) {
        sscanf(ptr, "\"sd1_sd2_ratio\": %lf", &computed_baseline.sd1_sd2_ratio);
    }
}

void publish_baseline_to_mqtt(MQTTClient client) {
    if (!has_baseline) {
        printf("⚠️  No baseline to publish\n");
        return;
    }
    
    char payload[512];
    sprintf(payload,
            "{\"mean_hr\":%.2f,\"sdnn\":%.2f,\"rmssd\":%.2f,\"pnn50\":%.2f,"
            "\"lf_hf_ratio\":%.2f,\"sd1_sd2_ratio\":%.2f}",
            computed_baseline.mean_hr,
            computed_baseline.sdnn,
            computed_baseline.rmssd,
            computed_baseline.pnn50,
            computed_baseline.lf_hf_ratio,
            computed_baseline.sd1_sd2_ratio);
    
    MQTTClient_message pubmsg = MQTTClient_message_initializer;
    MQTTClient_deliveryToken token;
    pubmsg.payload = payload;
    pubmsg.payloadlen = strlen(payload);
    pubmsg.qos = QOS;
    pubmsg.retained = 0;
    
    MQTTClient_publishMessage(client, TOPIC_BASELINE, &pubmsg, &token);
    MQTTClient_waitForCompletion(client, token, TIMEOUT);
    
    printf("✓ Published baseline to MQTT topic: %s\n", TOPIC_BASELINE);
    printf("  SDNN: %.2f, RMSSD: %.2f, pNN50: %.2f\n", 
           computed_baseline.sdnn, computed_baseline.rmssd, computed_baseline.pnn50);
}

// Build JSON payload with PPG array (without accel - now separate)
char* build_telemetry_payload(const char *device_id, int *ppg_buffer, int ppg_size,
                               double lat, double lon) {
    // Allocate enough space for the JSON payload
    // PPG array: ~7 chars per value (e.g., "4095,") * 250 samples = ~1750 chars
    char *payload = malloc(8192);
    
    sprintf(payload,
            "{\"device_id\":\"%s\",\"ppg\":[",
            device_id);
    
    // Add PPG values
    char value_str[16];
    for (int i = 0; i < ppg_size; i++) {
        if (i > 0) strcat(payload, ",");
        sprintf(value_str, "%d", ppg_buffer[i]);
        strcat(payload, value_str);
    }
    
    // Add remaining fields (no accel - sent separately)
    char suffix[256];
    sprintf(suffix,
            "],\"sample_rate\":%d,\"lat\":%.6f,\"lon\":%.6f}",
            PPG_SAMPLE_RATE, lat, lon);
    strcat(payload, suffix);
    
    return payload;
}

// Build accelerometer payload (sent frequently for crash detection)
char* build_accel_payload(const char *device_id, double accel_x, double accel_y, double accel_z,
                          double lat, double lon) {
    char *payload = malloc(256);
    sprintf(payload,
            "{\"device_id\":\"%s\",\"accel_x\":%.4f,\"accel_y\":%.4f,\"accel_z\":%.4f,"
            "\"lat\":%.6f,\"lon\":%.6f}",
            device_id, accel_x, accel_y, accel_z, lat, lon);
    return payload;
}

int main() {
    CURL *curl;
    CURLcode res;
    char response[8192] = {0};
    int ppg_buffer[PPG_BUFFER_SIZE];
    
    srand(time(NULL));

    // Build MQTT topics dynamically
    sprintf(TOPIC_TELE, "helmet/%s/telemetry", DEVICE_ID);
    sprintf(TOPIC_CMD, "helmet/%s/command", DEVICE_ID);
    sprintf(TOPIC_BASELINE, "helmet/%s/baseline", DEVICE_ID);
    sprintf(TOPIC_ACCEL, "helmet/%s/accel", DEVICE_ID);

    printf("=================================================\n");
    printf("   Smart Helmet Simulator - Starting Up\n");
    printf("   Device ID: %s\n", DEVICE_ID);
    printf("   PPG Config: %d Hz, %d samples/transmission\n", PPG_SAMPLE_RATE, PPG_BUFFER_SIZE);
    printf("   Accel: 10 Hz (every 100ms)\n");
    printf("=================================================\n\n");

    // 1️⃣ Check device status via FastAPI
    printf("Step 1: Checking device status...\n");
    curl = curl_easy_init();
    if (curl) {
        char url[256];
        sprintf(url, "%s/device/check?device_id=%s", FASTAPI_BASE_URL, DEVICE_ID);
        curl_easy_setopt(curl, CURLOPT_URL, url);
        curl_easy_setopt(curl, CURLOPT_HTTPGET, 1L);
        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
        curl_easy_setopt(curl, CURLOPT_WRITEDATA, response);
        res = curl_easy_perform(curl);
        curl_easy_cleanup(curl);
        
        printf("✓ Device check response: %s\n\n", response);
        
        if (strstr(response, "\"onboarded\": false") || strstr(response, "\"onboarded\":false")) {
            isOnboarding = true;
            printf("🔵 DEVICE NOT ONBOARDED - Will collect baseline\n");
            printf("   Samples needed: %d (approx %.1f minutes)\n", 
                   ONBOARD_SAMPLES, (ONBOARD_SAMPLES * 5.0) / 60.0);
        } else if (strstr(response, "\"onboarded\": true") || strstr(response, "\"onboarded\":true")) {
            isOnboarding = false;
            has_baseline = true;
            printf("✅ DEVICE ALREADY ONBOARDED\n");
            parse_baseline_from_response(response);
            printf("   Loaded baseline: SDNN=%.2f, RMSSD=%.2f\n", 
                   computed_baseline.sdnn, computed_baseline.rmssd);
        }
    }

    // 2️⃣ Connect MQTT
    printf("\nStep 2: Connecting to MQTT broker...\n");
    MQTTClient client;
    MQTTClient_connectOptions conn_opts = MQTTClient_connectOptions_initializer;
    MQTTClient_create(&client, ADDRESS, CLIENTID, MQTTCLIENT_PERSISTENCE_NONE, NULL);
    conn_opts.keepAliveInterval = 60;
    conn_opts.cleansession = 1;
    conn_opts.username = MQTT_USERNAME;
    conn_opts.password = MQTT_PASSWORD;

    if (MQTTClient_connect(client, &conn_opts) != MQTTCLIENT_SUCCESS) {
        printf("❌ Failed to connect MQTT broker.\n");
        exit(EXIT_FAILURE);
    }
    printf("✓ Connected to MQTT broker (authenticated as '%s')\n", MQTT_USERNAME);

    MQTTClient_setCallbacks(client, NULL, NULL, messageArrivedCB, NULL);
    MQTTClient_subscribe(client, TOPIC_CMD, QOS);
    printf("✓ Subscribed to: %s\n", TOPIC_CMD);
    printf("✓ Publishing PPG to: %s (every 5s)\n", TOPIC_TELE);
    printf("✓ Publishing Accel to: %s (every 100ms)\n", TOPIC_ACCEL);
    
    sleep(1);

    // 3️⃣ If already onboarded, publish baseline immediately
    if (has_baseline && !isOnboarding) {
        printf("\nStep 3: Publishing existing baseline to worker...\n");
        publish_baseline_to_mqtt(client);
        printf("\n");
    }

    // 4️⃣ Onboarding phase (if needed)
    if (isOnboarding) {
        printf("\n=================================================\n");
        printf("   ONBOARDING PHASE - Collecting Baseline Data\n");
        printf("=================================================\n\n");
        
        printf("📡 Starting telemetry stream (worker will use general baseline)...\n\n");
        
        while (onboard_count < ONBOARD_SAMPLES) {
            double hr = 65 + rand() % 15;  // Normal resting HR: 65-80 bpm
            double lat = -6.2000 + ((rand() % 100) / 10000.0);
            double lon = 106.8167 + ((rand() % 100) / 10000.0);
            
            // Generate PPG signal
            generate_ppg_signal(ppg_buffer, PPG_BUFFER_SIZE, hr, true);
            
            // Build and publish PPG telemetry
            char *payload = build_telemetry_payload(DEVICE_ID, ppg_buffer, PPG_BUFFER_SIZE, lat, lon);
            
            MQTTClient_message pubmsg = MQTTClient_message_initializer;
            MQTTClient_deliveryToken token;
            pubmsg.payload = payload;
            pubmsg.payloadlen = strlen(payload);
            pubmsg.qos = QOS;
            pubmsg.retained = 0;
            MQTTClient_publishMessage(client, TOPIC_TELE, &pubmsg, &token);
            MQTTClient_waitForCompletion(client, token, TIMEOUT);
            
            free(payload);
            
            // Send accel data 50 times during the 5 second window (every 100ms)
            for (int j = 0; j < 50; j++) {
                double accel_x, accel_y, accel_z;
                generate_accel_data(&accel_x, &accel_y, &accel_z, false);
                
                char *accel_payload = build_accel_payload(DEVICE_ID, accel_x, accel_y, accel_z, lat, lon);
                
                MQTTClient_message accel_msg = MQTTClient_message_initializer;
                MQTTClient_deliveryToken accel_token;
                accel_msg.payload = accel_payload;
                accel_msg.payloadlen = strlen(accel_payload);
                accel_msg.qos = 0;  // QoS 0 for high-frequency data
                accel_msg.retained = 0;
                MQTTClient_publishMessage(client, TOPIC_ACCEL, &accel_msg, &accel_token);
                
                free(accel_payload);
                usleep(100000);  // 100ms
            }
            
            onboard_count++;
            int progress = (onboard_count * 100) / ONBOARD_SAMPLES;
            printf("📊 [%d/%d] %3d%% | Target HR=%.0f bpm | PPG samples=%d\n", 
                   onboard_count, ONBOARD_SAMPLES, progress, hr, PPG_BUFFER_SIZE);
        }
        
        // Note: Baseline is now computed by worker from PPG data
        printf("\n✅ ONBOARDING DATA SENT! Worker will compute baseline...\n\n");
        isOnboarding = false;
        sleep(2);
    }

    // 5️⃣ Normal operation
    printf("=================================================\n");
    printf("   NORMAL OPERATION - Real-time Monitoring\n");
    printf("   PPG: every 5s | Accel: every 100ms\n");
    printf("=================================================\n\n");
    
    for (int i = 0; i < NORMAL_OPERATION_CYCLES; i++) {
        // Simulate different states
        bool simulate_drowsy = (rand() % 10 == 0);  // 10% chance of drowsy state
        bool simulate_crash = (rand() % 50 == 0);   // 2% chance of crash
        
        double hr;
        if (simulate_drowsy) {
            hr = 55 + rand() % 10;  // Lower HR when drowsy
        } else {
            hr = 65 + rand() % 20;  // Normal HR: 65-85 bpm
        }
        
        double lat = -6.2000 + ((rand() % 100) / 10000.0);
        double lon = 106.8167 + ((rand() % 100) / 10000.0);
        
        // Generate and publish PPG signal
        generate_ppg_signal(ppg_buffer, PPG_BUFFER_SIZE, hr, true);
        
        char *payload = build_telemetry_payload(DEVICE_ID, ppg_buffer, PPG_BUFFER_SIZE, lat, lon);
        
        MQTTClient_message pubmsg = MQTTClient_message_initializer;
        MQTTClient_deliveryToken token;
        pubmsg.payload = payload;
        pubmsg.payloadlen = strlen(payload);
        pubmsg.qos = QOS;
        pubmsg.retained = 0;
        MQTTClient_publishMessage(client, TOPIC_TELE, &pubmsg, &token);
        MQTTClient_waitForCompletion(client, token, TIMEOUT);
        
        free(payload);
        
        printf("📡 [%3d/%d] PPG sent (HR~%.0f) | GPS=(%.4f, %.4f)\n", 
               i+1, NORMAL_OPERATION_CYCLES, hr, lat, lon);
        
        // Send accel data 50 times during the 5 second window (every 100ms)
        // Crash happens at a random point if simulating crash
        int crash_at = simulate_crash ? (rand() % 50) : -1;
        
        for (int j = 0; j < 50; j++) {
            double accel_x, accel_y, accel_z;
            bool is_crash_moment = (j == crash_at);
            generate_accel_data(&accel_x, &accel_y, &accel_z, is_crash_moment);
            
            char *accel_payload = build_accel_payload(DEVICE_ID, accel_x, accel_y, accel_z, lat, lon);
            
            MQTTClient_message accel_msg = MQTTClient_message_initializer;
            MQTTClient_deliveryToken accel_token;
            accel_msg.payload = accel_payload;
            accel_msg.payloadlen = strlen(accel_payload);
            accel_msg.qos = 0;  // QoS 0 for high-frequency data
            accel_msg.retained = 0;
            MQTTClient_publishMessage(client, TOPIC_ACCEL, &accel_msg, &accel_token);
            
            free(accel_payload);
            
            if (is_crash_moment) {
                printf("    💥 CRASH SIMULATED! Accel=(%.1f, %.1f, %.1f)\n", 
                       accel_x, accel_y, accel_z);
            }
            
            // Check for incoming commands
            char *topicName = NULL;
            int topicLen;
            MQTTClient_message *message = NULL;
            
            int rc = MQTTClient_receive(client, &topicName, &topicLen, &message, 10);
            if (rc == MQTTCLIENT_SUCCESS && message != NULL) {
                messageArrivedCB(NULL, topicName, topicLen, message);
            }
            
            usleep(100000);  // 100ms
        }
        
        const char* status = alert_flag ? "[🚨 DROWSY]" : "[✅ NORMAL]";
        printf("%s\n\n", status);
    }

    printf("\n=================================================\n");
    printf("   Simulation Complete - Shutting Down\n");
    printf("=================================================\n");
    
    MQTTClient_disconnect(client, 10000);
    MQTTClient_destroy(&client);
    
    printf("✓ Shutdown complete\n\n");
    return 0;
}