# WihWin CD Infrastructure

Terraform configuration for deploying WihWin to AWS EC2 with ECR.

## Resources Created

| Resource | Description |
|----------|-------------|
| EC2 Instance | Amazon Linux 2023 (ARM64) with Docker |
| Security Group | Ports 22, 80, 1883, 9001, 15672 |
| IAM Role | ECR pull-only permissions |
| ECR Repositories | fastapi, spring, worker, ride-aggregator |
| AWS Budget | Monthly cost alerts at 80% and 100% |

## Quick Start

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars

terraform init
terraform plan
terraform apply
```

## Required GitHub Secrets

| Secret | Description |
|--------|-------------|
| `AWS_ACCESS_KEY_ID` | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key |
| `EC2_HOST` | `terraform output instance_public_ip` |
| `EC2_SSH_PRIVATE_KEY` | SSH private key contents |

## Pipeline Flow

- All branches: CI (tests only)
- Main branch: CI -> Build -> Push to ECR -> Deploy to EC2

## Manual Deployment

```bash
ssh -i key.pem ec2-user@<EC2_IP> 'sudo /opt/wihwin/deploy.sh'
```

## Cleanup

```bash
terraform destroy
```
