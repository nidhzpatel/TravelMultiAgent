locals {
  name = "voyagemind-${var.environment}"
  common_environment = [
    {
      name  = "ENVIRONMENT",
      value = var.environment,
    },
    {
      name  = "OIDC_ISSUER",
      value = var.oidc_issuer,
    },
    {
      name  = "OIDC_AUDIENCE",
      value = var.oidc_audience,
    },
    {
      name  = "OIDC_JWKS_URL",
      value = var.oidc_jwks_url,
    },
    {
      name  = "OTEL_SDK_DISABLED",
      value = "false",
    },
  ]
}


resource "aws_ecs_cluster" "this" {
  name = local.name

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}


resource "aws_cloudwatch_log_group" "api" {
  name              = "/voyagemind/${var.environment}/api"
  retention_in_days = var.environment == "production" ? 90 : 30
}


resource "aws_cloudwatch_log_group" "worker" {
  name              = "/voyagemind/${var.environment}/worker"
  retention_in_days = var.environment == "production" ? 90 : 30
}


resource "aws_cloudwatch_log_group" "frontend" {
  name              = "/voyagemind/${var.environment}/frontend"
  retention_in_days = var.environment == "production" ? 30 : 14
}


resource "aws_iam_role" "execution" {
  name = "${local.name}-execution"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        },
        Action = "sts:AssumeRole"
      }
    ]
  })
}


resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}


resource "aws_iam_role_policy" "secrets" {
  role = aws_iam_role.execution.id
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "secretsmanager:GetSecretValue"
        ],
        Resource = [
          var.database_url_secret_arn,
          var.session_secret_arn
        ]
      }
    ]
  })
}


resource "aws_iam_role" "workload" {
  name = "${local.name}-workload"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        },
        Action = "sts:AssumeRole"
      }
    ]
  })
}


resource "aws_s3_bucket" "exports" {
  bucket = "${local.name}-exports"
}


resource "aws_s3_bucket_versioning" "exports" {
  bucket = aws_s3_bucket.exports.id

  versioning_configuration {
    status = "Enabled"
  }
}


resource "aws_s3_bucket_server_side_encryption_configuration" "exports" {
  bucket = aws_s3_bucket.exports.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}


resource "aws_s3_bucket_public_access_block" "exports" {
  bucket                  = aws_s3_bucket.exports.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}


resource "aws_iam_role_policy" "exports" {
  role = aws_iam_role.workload.id
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ],
        Resource = "${aws_s3_bucket.exports.arn}/*"
      }
    ]
  })
}


resource "aws_iam_role" "rds_monitoring" {
  name = "${local.name}-rds-monitoring"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        },
        Action = "sts:AssumeRole"
      }
    ]
  })
}


resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}


resource "aws_db_subnet_group" "this" {
  name       = local.name
  subnet_ids = var.database_subnet_ids
}


resource "aws_db_instance" "this" {
  identifier                   = local.name
  engine                       = "postgres"
  engine_version               = "16.4"
  instance_class               = var.database_instance_class
  allocated_storage            = 50
  max_allocated_storage        = 500
  storage_type                 = "gp3"
  storage_encrypted            = true
  db_name                      = "voyagemind"
  username                     = "voyagemind"
  manage_master_user_password  = true
  db_subnet_group_name         = aws_db_subnet_group.this.name
  vpc_security_group_ids       = var.database_security_group_ids
  multi_az                     = var.environment == "production"
  publicly_accessible          = false
  backup_retention_period      = var.environment == "production" ? 14 : 3
  backup_window                = "18:00-19:00"
  maintenance_window           = "Sun:19:00-Sun:20:00"
  performance_insights_enabled = true
  monitoring_interval          = 60
  monitoring_role_arn          = aws_iam_role.rds_monitoring.arn
  deletion_protection          = var.environment == "production"
  skip_final_snapshot          = false
  final_snapshot_identifier    = "${local.name}-final"
  auto_minor_version_upgrade   = true
}


resource "aws_ecs_task_definition" "api" {
  family = "${local.name}-api"
  requires_compatibilities = [
    "FARGATE",
  ]
  network_mode       = "awsvpc"
  cpu                = 1024
  memory             = 2048
  execution_role_arn = aws_iam_role.execution.arn
  task_role_arn      = aws_iam_role.workload.arn
  container_definitions = jsonencode([
    {
      name                   = "api",
      image                  = var.api_image,
      essential              = true,
      readonlyRootFilesystem = true,
      portMappings = [
        {
          containerPort = 8000
        }
      ],
      environment = local.common_environment,
      secrets = [
        {
          name      = "DATABASE_URL",
          valueFrom = var.database_url_secret_arn
        },
        {
          name      = "SESSION_SECRET",
          valueFrom = var.session_secret_arn
        }
      ],
      healthCheck = {
        command = [
          "CMD-SHELL",
          "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')\""
        ],
        interval    = 30,
        timeout     = 5,
        retries     = 3,
        startPeriod = 30
      },
      logConfiguration = {
        logDriver = "awslogs",
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.api.name,
          "awslogs-region"        = var.aws_region,
          "awslogs-stream-prefix" = "api"
        }
      }
    }
  ])
}


resource "aws_ecs_task_definition" "worker" {
  family = "${local.name}-worker"
  requires_compatibilities = [
    "FARGATE",
  ]
  network_mode       = "awsvpc"
  cpu                = 1024
  memory             = 2048
  execution_role_arn = aws_iam_role.execution.arn
  task_role_arn      = aws_iam_role.workload.arn
  container_definitions = jsonencode([
    {
      name                   = "worker",
      image                  = var.worker_image,
      essential              = true,
      readonlyRootFilesystem = true,
      command = [
        "python",
        "-m",
        "app.workers.run"
      ],
      environment = local.common_environment,
      secrets = [
        {
          name      = "DATABASE_URL",
          valueFrom = var.database_url_secret_arn
        },
        {
          name      = "SESSION_SECRET",
          valueFrom = var.session_secret_arn
        }
      ],
      logConfiguration = {
        logDriver = "awslogs",
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.worker.name,
          "awslogs-region"        = var.aws_region,
          "awslogs-stream-prefix" = "worker"
        }
      }
    }
  ])
}


resource "aws_ecs_task_definition" "frontend" {
  family = "${local.name}-frontend"
  requires_compatibilities = [
    "FARGATE",
  ]
  network_mode       = "awsvpc"
  cpu                = 256
  memory             = 512
  execution_role_arn = aws_iam_role.execution.arn
  task_role_arn      = aws_iam_role.workload.arn
  container_definitions = jsonencode([
    {
      name                   = "frontend",
      image                  = var.frontend_image,
      essential              = true,
      readonlyRootFilesystem = true,
      portMappings = [
        {
          containerPort = 8080
        }
      ],
      healthCheck = {
        command = [
          "CMD-SHELL",
          "wget -q -O - http://127.0.0.1:8080/healthz"
        ],
        interval    = 30,
        timeout     = 5,
        retries     = 3,
        startPeriod = 15
      },
      logConfiguration = {
        logDriver = "awslogs",
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.frontend.name,
          "awslogs-region"        = var.aws_region,
          "awslogs-stream-prefix" = "frontend"
        }
      }
    }
  ])
}


resource "aws_ecs_service" "api" {
  name                               = "api"
  cluster                            = aws_ecs_cluster.this.id
  task_definition                    = aws_ecs_task_definition.api.arn
  desired_count                      = var.api_desired_count
  launch_type                        = "FARGATE"
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }


  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = var.service_security_group_ids
    assign_public_ip = false
  }
}


resource "aws_ecs_service" "worker" {
  name                               = "worker"
  cluster                            = aws_ecs_cluster.this.id
  task_definition                    = aws_ecs_task_definition.worker.arn
  desired_count                      = var.worker_desired_count
  launch_type                        = "FARGATE"
  deployment_minimum_healthy_percent = 50
  deployment_maximum_percent         = 200

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }


  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = var.service_security_group_ids
    assign_public_ip = false
  }
}


resource "aws_ecs_service" "frontend" {
  name                               = "frontend"
  cluster                            = aws_ecs_cluster.this.id
  task_definition                    = aws_ecs_task_definition.frontend.arn
  desired_count                      = var.frontend_desired_count
  launch_type                        = "FARGATE"
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }


  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = var.service_security_group_ids
    assign_public_ip = false
  }
}


resource "aws_cloudwatch_metric_alarm" "api_cpu" {
  alarm_name  = "${local.name}-api-cpu"
  namespace   = "AWS/ECS"
  metric_name = "CPUUtilization"
  dimensions = {
    ClusterName = aws_ecs_cluster.this.name,
    ServiceName = aws_ecs_service.api.name,
  }
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 2
  comparison_operator = "GreaterThanThreshold"
  threshold           = 80
  alarm_actions = [
    var.alarm_topic_arn,
  ]
}


resource "aws_cloudwatch_metric_alarm" "worker_cpu" {
  alarm_name  = "${local.name}-worker-cpu"
  namespace   = "AWS/ECS"
  metric_name = "CPUUtilization"
  dimensions = {
    ClusterName = aws_ecs_cluster.this.name,
    ServiceName = aws_ecs_service.worker.name,
  }
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 2
  comparison_operator = "GreaterThanThreshold"
  threshold           = 80
  alarm_actions = [
    var.alarm_topic_arn,
  ]
}


resource "aws_cloudwatch_metric_alarm" "database_connections" {
  alarm_name  = "${local.name}-database-connections"
  namespace   = "AWS/RDS"
  metric_name = "DatabaseConnections"
  dimensions = {
    DBInstanceIdentifier = aws_db_instance.this.identifier,
  }
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 2
  comparison_operator = "GreaterThanThreshold"
  threshold           = 80
  alarm_actions = [
    var.alarm_topic_arn,
  ]
}


resource "aws_cloudwatch_metric_alarm" "api_errors" {
  alarm_name          = "${local.name}-api-errors"
  namespace           = "VoyageMind"
  metric_name         = "ApiServerErrorCount"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 2
  comparison_operator = "GreaterThanThreshold"
  threshold           = 5
  treat_missing_data  = "notBreaching"
  alarm_actions = [
    var.alarm_topic_arn,
  ]
}


resource "aws_cloudwatch_dashboard" "this" {
  dashboard_name = local.name
  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric",
        x      = 0,
        y      = 0,
        width  = 12,
        height = 6,
        properties = {
          title  = "API latency and errors",
          region = var.aws_region,
          metrics = [
            [
              "VoyageMind",
              "ApiLatencyMs",
              {
                stat = "p95"
              }
            ],
            [
              ".",
              "ApiServerErrorCount",
              {
                stat = "Sum"
              }
            ]
          ]
        }
      },
      {
        type   = "metric",
        x      = 12,
        y      = 0,
        width  = 12,
        height = 6,
        properties = {
          title  = "Planning jobs, tokens and cost",
          region = var.aws_region,
          metrics = [
            [
              "VoyageMind",
              "PlanningJobCount",
              {
                stat = "Sum"
              }
            ],
            [
              ".",
              "PlanningTokensUsed",
              {
                stat = "Sum"
              }
            ],
            [
              ".",
              "PlanningCostUsd",
              {
                stat = "Sum"
              }
            ]
          ]
        }
      },
      {
        type   = "metric",
        x      = 0,
        y      = 6,
        width  = 12,
        height = 6,
        properties = {
          title  = "Provider outcomes",
          region = var.aws_region,
          metrics = [
            [
              "VoyageMind",
              "ProviderRunCount",
              {
                stat = "Sum"
              }
            ]
          ]
        }
      },
      {
        type   = "metric",
        x      = 12,
        y      = 6,
        width  = 12,
        height = 6,
        properties = {
          title  = "Authorization denials",
          region = var.aws_region,
          metrics = [
            [
              "VoyageMind",
              "AuthorizationDenialCount",
              {
                stat = "Sum"
              }
            ]
          ]
        }
      }
    ]
  })
}
