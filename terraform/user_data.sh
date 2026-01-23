#!/bin/bash
set -e

exec > >(tee /var/log/user-data.log) 2>&1

dnf update -y
dnf install -y docker git

systemctl start docker
systemctl enable docker

mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-aarch64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

usermod -aG docker ec2-user

mkdir -p /opt/${project_name}
cd /opt/${project_name}

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

cat > /opt/${project_name}/.env <<EOF
ECR_REGISTRY=${account_id}.dkr.ecr.${aws_region}.amazonaws.com
IMAGE_TAG=latest
AWS_REGION=${aws_region}
EOF

%{ if github_repo != "" }
git clone --branch ${github_branch} ${github_repo} /opt/${project_name}/app
cd /opt/${project_name}/app
cp /opt/${project_name}/.env /opt/${project_name}/app/.env
%{ endif }

cat > /opt/${project_name}/deploy.sh <<'DEPLOY_SCRIPT'
#!/bin/bash
set -e

cd /opt/${project_name}/app
source /opt/${project_name}/.env
export ECR_REGISTRY IMAGE_TAG AWS_REGION

aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REGISTRY
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d --remove-orphans
docker image prune -f
DEPLOY_SCRIPT

chmod +x /opt/${project_name}/deploy.sh

cat > /etc/systemd/system/${project_name}.service <<EOF
[Unit]
Description=WihWin Docker Compose Application
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/${project_name}/app
EnvironmentFile=/opt/${project_name}/.env
ExecStart=/usr/bin/docker compose -f docker-compose.prod.yml up -d
ExecStop=/usr/bin/docker compose -f docker-compose.prod.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable ${project_name}.service

echo "User data script completed at $(date)"
