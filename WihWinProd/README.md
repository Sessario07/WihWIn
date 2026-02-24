# WihWinProd — Infrastructure Repository

This repository contains **infrastructure provisioning** and **production runtime orchestration** for the WihWin platform.

It does **NOT** contain application source code, Dockerfiles, or CI/CD pipelines.  
Those live in the [Application Repository](https://github.com/your-org/WihWIn).

---

## Repository Structure

```
WihWinProd/
├── terraform/                  # AWS infrastructure as code
│   ├── main.tf                 # Provider, data sources
│   ├── variables.tf            # Input variables
│   ├── ec2.tf                  # EC2 instance
│   ├── ecr.tf                  # ECR repositories (empty)
│   ├── iam.tf                  # IAM roles for ECR pull
│   ├── ssh_key.tf              # AWS key pair from ~/.ssh/wihwin-key.pub
│   ├── security_group.tf       # Firewall rules
│   ├── budget.tf               # AWS budget alerts
│   ├── outputs.tf              # Terraform outputs
│   ├── user_data.sh            # EC2 bootstrap script
│   └── terraform.tfvars.example
├── docker-compose.prod.yml     # Production orchestration (image: only)
├── init.sql                    # Postgres schema
├── nginx/nginx.conf            # Reverse proxy config
├── prometheus/prometheus.yml   # Metrics scraping
├── grafana/provisioning/       # Grafana datasource provisioning
├── mqtt/
│   ├── mosquitto.conf          # MQTT broker config
│   └── mqtt-entrypoint.sh      # MQTT password bootstrap
├── .env.template               # Environment variable template (no secrets)
└── .gitignore
```

---

## Deployment Model

### Overview

```
┌──────────────────┐     ┌──────────────────────┐
│  WihWinProd       │     │  WihWIn (App Repo)    │
│  (This Repo)      │     │                      │
│                  │     │  Source code          │
│  Terraform       │     │  Dockerfiles          │
│  docker-compose  │     │  CI: tests → build    │
│  Runtime configs │     │  CD: SSH → pull → up  │
└────────┬─────────┘     └──────────┬───────────┘
         │                          │
         │ 1. terraform apply       │ 4. CI builds + pushes to ECR
         │ 2. Cloned onto EC2       │ 5. CD SSHs into EC2
         ▼                          │ 6. docker compose pull + up
    ┌────────────┐                  │
    │   AWS EC2   │◄────────────────┘
    │             │
    │  /opt/wihwin/app/
    │    ├── docker-compose.prod.yml
    │    ├── .env
    │    ├── nginx/
    │    ├── prometheus/
    │    ├── grafana/
    │    ├── mqtt/
    │    └── init.sql
    └────────────┘
```

---

## Initial Setup (Step-by-Step)

### Prerequisites

- AWS CLI configured (`aws configure`)
- Terraform >= 1.0 installed
- An SSH key pair at `~/.ssh/wihwin-key` and `~/.ssh/wihwin-key.pub`

If you don't have the key pair yet:
```bash
ssh-keygen -t ed25519 -f ~/.ssh/wihwin-key -C "wihwin-prod"
```

### Step 1: Provision Infrastructure

```bash
cd WihWinProd/terraform

# Create your tfvars file from the example
cp terraform.tfvars.example terraform.tfvars

# Edit terraform.tfvars — fill in:
#   budget_alert_email  = "your-email@example.com"
#   infra_repo_url      = "https://github.com/your-org/WihWinProd.git"
nano terraform.tfvars

# Initialize and apply
terraform init
terraform plan
terraform apply
```

After `terraform apply` completes, note the outputs:
- `instance_public_ip` — your EC2 IP address
- `ecr_registry` — your ECR registry URL (e.g., `698302425909.dkr.ecr.ap-northeast-1.amazonaws.com`)
- `ssh_command` — ready-to-use SSH command

### Step 2: SSH into EC2 and Inject Secrets

Wait ~2 minutes for user_data.sh to finish, then:

```bash
# SSH in (use the output from terraform)
ssh -i ~/.ssh/wihwin-key ec2-user@<EC2_PUBLIC_IP>

# Check user-data completed
cat /var/log/user-data.log | tail -5

# Edit the .env file to replace all CHANGE_ME placeholders
sudo nano /opt/wihwin/app/.env
```

Replace every `CHANGE_ME` with real values. Example secure password generation:
```bash
# Generate random passwords
openssl rand -base64 32    # for POSTGRES_PASSWORD
openssl rand -base64 24    # for MQTT_PASSWORD, RABBITMQ_PASSWORD
openssl rand -base64 64    # for JWT_SECRET
openssl rand -base64 16    # for GRAFANA_PASSWORD
```

**IMPORTANT**: Make sure `DB_URL` and `RABBITMQ_URL` contain the same passwords you set for `POSTGRES_PASSWORD` and `RABBITMQ_PASSWORD`.

### Step 3: Configure GitHub Secrets (Application Repo)

In your **WihWIn application repository** on GitHub, go to:  
**Settings → Secrets and variables → Actions → New repository secret**

Add these secrets:

| Secret Name | Value | Description |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | Your AWS access key | IAM user with ECR push permissions |
| `AWS_SECRET_ACCESS_KEY` | Your AWS secret key | IAM user with ECR push permissions |
| `EC2_HOST` | `<EC2_PUBLIC_IP>` | From `terraform output instance_public_ip` |
| `EC2_SSH_PRIVATE_KEY` | Contents of `~/.ssh/wihwin-key` | The **private** key (paste full content) |

Also create a **GitHub Environment**:
1. Go to **Settings → Environments → New environment**
2. Name it: `production`
3. (Optional) Add required reviewers for deploy approval

### Step 4: Push to Main and Deploy

Once secrets are set, any push to `main` in the app repo will:
1. Run unit tests (FastAPI, Worker, Spring Boot)
2. Build Docker images for all 4 services
3. Push images to ECR
4. SSH into EC2
5. `docker compose pull` + `docker compose up -d`

```bash
# From the application repo
git push origin main
```

---

## Terraform Commands

```bash
cd WihWinProd/terraform

# See what will be created
terraform plan

# Create all infrastructure
terraform apply

# Show outputs (IP, ECR URLs, SSH command)
terraform output

# Destroy everything
terraform destroy
```

---

## Services

| Service | Container Name | Image Source | Port |
|---|---|---|---|
| nginx | nginx_proxy | nginx:alpine | 80 (public) |
| fastapi | fastapi_app | ECR: wihwin-fastapi | 8000 (internal) |
| spring | spring_backend | ECR: wihwin-spring-backend | 8080 (internal) |
| worker | helmet_worker | ECR: wihwin-worker | — |
| ride-aggregator | ride_aggregator | ECR: wihwin-ride-aggregator | — |
| db | postgres_db | postgres:15-alpine | 5432 (internal) |
| mqtt | mqtt_broker | eclipse-mosquitto:2 | 1883 (public) |
| rabbitmq | rabbitmq | rabbitmq:3-alpine | 5672 (internal) |
| prometheus | prometheus | prom/prometheus | 9090 (internal) |
| grafana | grafana | grafana/grafana | 3000 (internal) |
| node-exporter | node_exporter | prom/node-exporter | 9100 (internal) |

---

## This Repo Must NOT

- Build Docker images
- Push images to ECR
- Run CI pipelines
- Deploy automatically
- Contain application source code
