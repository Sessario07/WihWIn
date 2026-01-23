variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "ap-northeast-1"
}

variable "project_name" {
  description = "Project name for resource tagging"
  type        = string
  default     = "wihwin"
}

variable "environment" {
  description = "Environment name (e.g., dev, staging, prod)"
  type        = string
  default     = "prod"
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "c6g.xlarge"
}

variable "ssh_allowed_cidr" {
  description = "CIDR block allowed for SSH access"
  type        = string
  default     = "0.0.0.0/0"
}

variable "key_pair_name" {
  description = "Name of existing EC2 key pair for SSH access"
  type        = string
}

variable "ecr_repository_urls" {
  description = "Map of service names to ECR repository URLs"
  type        = map(string)
  default     = {}
}

variable "budget_limit_amount" {
  description = "Monthly budget limit in USD"
  type        = string
  default     = "30"
}

variable "budget_alert_email" {
  description = "Email address for budget alerts"
  type        = string
}

variable "docker_compose_s3_bucket" {
  description = "S3 bucket containing docker-compose.yml"
  type        = string
  default     = ""
}

variable "github_repo_url" {
  description = "GitHub repository URL for cloning docker-compose.yml"
  type        = string
  default     = ""
}

variable "github_branch" {
  description = "GitHub branch to clone"
  type        = string
  default     = "main"
}
