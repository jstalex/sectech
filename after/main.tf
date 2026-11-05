# Исправлено: ключи удалены из кода; для автономного plan используются переменные окружения.
terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "5.100.0" }
  }
}
provider "aws" {
  region                      = "us-east-1"
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true
  skip_region_validation      = true
}
resource "aws_s3_bucket" "data" {
  # checkov:skip=CKV_AWS_144: Учебные данные dev; межрегиональная репликация не требуется.
  bucket = "student-iac-lab3-data"
  # Исправлено: обязательный тег окружения.
  tags = { Environment = "dev" }
}
resource "aws_s3_bucket_acl" "data" {
  bucket = aws_s3_bucket.data.id
  # Исправлено: публичный ACL заменен приватным.
  acl = "private"
}
resource "aws_s3_bucket_public_access_block" "data" {
  bucket = aws_s3_bucket.data.id
  # Исправлено: четыре уровня блокировки публичного доступа.
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id
  # Исправлено: версии объектов сохраняются.
  versioning_configuration { status = "Enabled" }
}
resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    # Исправлено: используется ключ KMS, а не AES256 по умолчанию.
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = "arn:aws:kms:us-east-1:123456789012:key/00000000-0000-4000-8000-000000000001"
    }
  }
}
resource "aws_security_group" "web" {
  # checkov:skip=CKV2_AWS_5: Изолированный учебный SG; EC2 не разворачивается.
  name        = "student-iac-lab3-web"
  description = "Lab security group"
  vpc_id      = "vpc-0123456789abcdef0"
  tags        = { Environment = "dev" }
  ingress {
    description = "SSH from trusted network"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    # Исправлено: SSH только из доверенной сети.
    cidr_blocks = ["10.0.0.0/16"]
  }
  egress {
    description = "HTTPS only"
    # Исправлено: исходящий трафик ограничен HTTPS.
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
resource "aws_iam_policy" "app" {
  name = "student-iac-lab3-app"
  tags = { Environment = "dev" }
  # Исправлено: конкретное действие и область объектов вместо звездочек.
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:GetObject"]
      Resource = "${aws_s3_bucket.data.arn}/*"
    }]
  })
}

# Исправлено: аудит в отдельный заранее подготовленный бакет журналов.
resource "aws_s3_bucket_logging" "data" {
  bucket        = aws_s3_bucket.data.id
  target_bucket = "student-iac-lab3-audit-existing"
  target_prefix = "data/"
}
# Исправлено: незавершенные загрузки удаляются через 7 дней.
resource "aws_s3_bucket_lifecycle_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    id     = "abort-incomplete-uploads"
    status = "Enabled"
    filter { prefix = "" }
    abort_incomplete_multipart_upload { days_after_initiation = 7 }
  }
}
# Исправлено: уведомления о создании объектов в подготовленную SNS-тему.
resource "aws_s3_bucket_notification" "data" {
  bucket = aws_s3_bucket.data.id
  topic {
    topic_arn = "arn:aws:sns:us-east-1:123456789012:student-iac-events-existing"
    events    = ["s3:ObjectCreated:*"]
  }
}
