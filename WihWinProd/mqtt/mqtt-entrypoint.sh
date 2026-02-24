#!/bin/sh
set -e

# Create password file from env vars
touch /mosquitto/config/password.txt
mosquitto_passwd -b /mosquitto/config/password.txt "$MQTT_USER" "$MQTT_PASSWORD"

# Start mosquitto
exec mosquitto -c /mosquitto/config/mosquitto.conf
