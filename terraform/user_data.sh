#!/bin/bash
set -e

exec > >(tee /var/log/user-data.log) 2>&1

dnf update -y
dnf install -y docker git
dnf install -y awscli

systemctl start docker
systemctl enable docker

mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-aarch64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

usermod -aG docker ec2-user

mkdir -p /opt/${project_name}

dnf install -y amazon-ecr-credential-helper

mkdir -p /root/.docker
cat > /root/.docker/config.json <<EOF
{
  "credHelpers": {
    "${account_id}.dkr.ecr.${aws_region}.amazonaws.com": "ecr-login"
  }
}
EOF

mkdir -p /home/ec2-user/.docker
cp /root/.docker/config.json /home/ec2-user/.docker/config.json
chown -R ec2-user:ec2-user /home/ec2-user/.docker

%{ if github_repo != "" }
git clone --branch ${github_branch} ${github_repo} /opt/${project_name}/app
%{ endif }

cat > /opt/${project_name}/app/WihWinProd/.env <<EOF
ECR_REGISTRY=${account_id}.dkr.ecr.${aws_region}.amazonaws.com
IMAGE_TAG=latest
AWS_REGION=${aws_region}

POSTGRES_USER=wihwin_admin
POSTGRES_PASSWORD=CHANGE_ME
POSTGRES_DB=Wihwin
DB_URL=postgresql://wihwin_admin:CHANGE_ME@db:5432/Wihwin
SPRING_DATASOURCE_URL=jdbc:postgresql://db:5432/Wihwin

MQTT_BROKER=mqtt
MQTT_USER=helmet
MQTT_PASSWORD=CHANGE_ME

RABBITMQ_USER=wihwin_mq
RABBITMQ_PASSWORD=CHANGE_ME
RABBITMQ_URL=amqp://wihwin_mq:CHANGE_ME@rabbitmq:5672/

JWT_SECRET=CHANGE_ME_TO_A_SECURE_512_BIT_SECRET
JWT_EXPIRATION=86400000
BCRYPT_STRENGTH=12

FASTAPI_URL=http://fastapi:8000
PYTHONUNBUFFERED=1

GRAFANA_USER=admin
GRAFANA_PASSWORD=CHANGE_ME
GRAFANA_ROOT_URL=http://localhost:3000
EOF

cat > /opt/${project_name}/deploy.sh <<'DEPLOY_SCRIPT'
#!/bin/bash
set -e

cd /opt/${project_name}/app/WihWinProd
source .env
export ECR_REGISTRY IMAGE_TAG AWS_REGION

aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REGISTRY
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d --remove-orphans
docker image prune -f
DEPLOY_SCRIPT

chmod +x /opt/${project_name}/deploy.sh

chown -R ec2-user:ec2-user /opt/${project_name}

echo "User data script completed at $(date)"
