# SSL Setup Guide for WihWIN

## Prerequisites

1. **Domain name** pointing to your EC2 IP (`35.77.98.154`)
   - Example: `api.wihwin.com`
   - Configure A record in your DNS provider

2. **EC2 Security Group** must allow:
   - Port 80 (HTTP) - for Let's Encrypt validation
   - Port 443 (HTTPS) - for secure traffic
   - Port 1883 (MQTT) - for helmet devices

## Step-by-Step Setup

### 1. Configure Your Domain

On EC2, edit `setup-ssl.sh`:

```bash
nano setup-ssl.sh
```

Change these lines:
```bash
DOMAIN="api.wihwin.com"        # Your domain
EMAIL="your-email@gmail.com"   # Your email
```

### 2. Run the SSL Setup Script

```bash
chmod +x setup-ssl.sh
./setup-ssl.sh
```

This will:
- Create certificate directories
- Start nginx
- Request SSL certificate from Let's Encrypt

### 3. Update Nginx Configuration

Edit `nginx/nginx.conf` and replace:

```nginx
server_name _;  # Replace with: server_name api.wihwin.com;
ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;  
# Replace 'your-domain.com' with 'api.wihwin.com'
```

### 4. Restart Services

```bash
docker-compose restart nginx
```

### 5. Test HTTPS

```bash
curl https://api.wihwin.com/health
# Should return: OK

curl https://api.wihwin.com/api/fast/device/check?device_id=HELMET001
# Should return device JSON
```

## Certificate Auto-Renewal

Certificates automatically renew every 12 hours via the `certbot` container.

## Update Your Clients

### Helmet Simulator

```c
#define FASTAPI_BASE_URL "https://api.wihwin.com/api/fast"  // Use HTTPS
```

### Mobile App

```dart
const String apiUrl = "https://api.wihwin.com";
```

## URLs After SSL

| Service | Old URL | New URL (HTTPS) |
|---------|---------|-----------------|
| FastAPI | `http://35.77.98.154/api/fast/` | `https://api.wihwin.com/api/fast/` |
| Spring | `http://35.77.98.154/api/spring/` | `https://api.wihwin.com/api/spring/` |
| MQTT | `tcp://35.77.98.154:1883` | No change (MQTT doesn't use HTTPS) |

## Troubleshooting

### Certificate request fails

Check DNS:
```bash
nslookup api.wihwin.com
# Should return your EC2 IP: 35.77.98.154
```

### Nginx won't start

Check logs:
```bash
docker logs nginx_proxy
```

### Test without domain (temporary)

Comment out the HTTPS redirect in `nginx.conf` temporarily:
```nginx
# location / {
#     return 301 https://$host$request_uri;
# }
```
