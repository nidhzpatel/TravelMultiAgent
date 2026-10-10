"""Deploy one ECS task definition and automatically roll back if stability fails."""

import argparse
import json
import subprocess


def aws(*arguments: str) -> dict:
    result = subprocess.run(["aws", *arguments, "--output", "json"], check=True, capture_output=True, text=True)
    return json.loads(result.stdout or "{}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cluster", required=True)
    parser.add_argument("--service", required=True)
    parser.add_argument("--task-definition", required=True)
    args = parser.parse_args()
    current = aws("ecs", "describe-services", "--cluster", args.cluster, "--services", args.service)
    previous = current["services"][0]["taskDefinition"]
    try:
        aws("ecs", "update-service", "--cluster", args.cluster, "--service", args.service, "--task-definition", args.task_definition, "--deployment-configuration", "minimumHealthyPercent=100,maximumPercent=200,deploymentCircuitBreaker={enable=true,rollback=true}")
        subprocess.run(["aws", "ecs", "wait", "services-stable", "--cluster", args.cluster, "--services", args.service], check=True)
    except subprocess.CalledProcessError:
        aws("ecs", "update-service", "--cluster", args.cluster, "--service", args.service, "--task-definition", previous, "--force-new-deployment")
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
