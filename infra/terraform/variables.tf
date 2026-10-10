variable "environment" {
  type = string

  validation {
    condition = contains([
      "staging",
      "production"
    ], var.environment)
    error_message = "environment must be staging or production"
  }
}


variable "aws_region" {
  type = string
}


variable "private_subnet_ids" {
  type = list(string)
}


variable "service_security_group_ids" {
  type = list(string)
}


variable "database_subnet_ids" {
  type = list(string)
}


variable "database_security_group_ids" {
  type = list(string)
}


variable "api_image" {
  type = string
}


variable "worker_image" {
  type = string
}


variable "frontend_image" {
  type = string
}


variable "database_url_secret_arn" {
  type      = string
  sensitive = true
}


variable "session_secret_arn" {
  type      = string
  sensitive = true
}


variable "oidc_issuer" {
  type = string
}


variable "oidc_audience" {
  type = string
}


variable "oidc_jwks_url" {
  type = string
}


variable "api_desired_count" {
  type    = number
  default = 2
}


variable "worker_desired_count" {
  type    = number
  default = 2
}


variable "frontend_desired_count" {
  type    = number
  default = 2
}


variable "alarm_topic_arn" {
  type = string
}


variable "database_instance_class" {
  type    = string
  default = "db.t4g.medium"
}
