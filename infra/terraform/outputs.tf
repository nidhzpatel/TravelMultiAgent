output "cluster_name" {
  value = aws_ecs_cluster.this.name
}


output "api_service_name" {
  value = aws_ecs_service.api.name
}


output "worker_service_name" {
  value = aws_ecs_service.worker.name
}


output "frontend_service_name" {
  value = aws_ecs_service.frontend.name
}


output "exports_bucket" {
  value = aws_s3_bucket.exports.id
}


output "database_endpoint" {
  value = aws_db_instance.this.endpoint
}


output "database_master_secret_arn" {
  value     = try(aws_db_instance.this.master_user_secret[0].secret_arn, null)
  sensitive = true
}
