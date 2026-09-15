# src/setup_doctor/checkers/services.py
from __future__ import annotations
import os
import socket
import yaml  # PyYAML is a runtime dependency for this checker
from .base import Checker
from ..models import CheckResult, RemediationStep, CheckStatus, Severity
from ..utils.commands import run_command, which


def _port_open(host: str, port: int, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


class ServicesChecker(Checker):
    id, label, ecosystem = "services", "Local services", "services"

    def _compose_services(self, repo):
        for name in ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"):
            path = os.path.join(repo, name)
            if os.path.isfile(path):
                try:
                    with open(path, encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                    if not isinstance(data, dict):
                        return []
                    services = data.get("services")
                    return services.keys() if isinstance(services, dict) else []
                except yaml.YAMLError:
                    return []
        return []

    def run(self, ctx):
        results = []
        has_compose = bool(self._compose_services(ctx.repo_path))
        docker = which("docker")
        if docker is not None:
            docker_ok = run_command([docker, "info"], timeout=10).ok
        else:
            docker_ok = False
        # Docker thiếu khi repo yêu cầu compose -> FAIL (prerequisite thiếu), không SKIP (#5)
        results.append(CheckResult(
            check_id="services.container.present", name="Docker daemon reachable",
            ecosystem=self.ecosystem,
            status=CheckStatus.PASS if docker_ok
                   else (CheckStatus.FAIL if has_compose else CheckStatus.SKIP),
            evidence="docker daemon reachable" if docker_ok
                     else ("docker missing/unavailable (required by compose)" if has_compose else "no compose; docker not needed"),
            remediation=[] if docker_ok else [
                RemediationStep("Start Docker Desktop", "start \"\" \"C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe\"",
                                safe_fix=False, operation="start-docker",
                                argv=["start", "", "C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe"]),
            ],
        ))

        expected = set(self._compose_services(ctx.repo_path))
        if docker_ok and expected:
            res = run_command([docker, "compose", "ps", "--format", "{{.Name}}"], cwd=ctx.repo_path, timeout=30)
            running = set(res.stdout.splitlines())
            # Container name = <project>-<service>-1; so theo PREFIX (không đòi khớp chính xác) (#5)
            def _running(key):
                return any(rn == key or rn.startswith(key + "-") or rn.endswith("-" + key + "-1")
                           for rn in running)
            missing = {k for k in expected if not _running(k)} if res.ok else set(expected)
            results.append(CheckResult(
                check_id="services.compose.up", name="Compose services running",
                ecosystem=self.ecosystem,
                status=CheckStatus.PASS if not missing else CheckStatus.FAIL,
                evidence=f"not running: {', '.join(sorted(missing))}" if missing else "all compose services running",
                remediation=[] if not missing else [
                    RemediationStep("Start compose services", "docker compose up -d",
                                    safe_fix=True, operation="start-service",
                                    argv=["docker", "compose", "up", "-d"]),
                ],
                depends_on=["services.container.present"],
            ))
        elif has_compose and not docker_ok:
            results.append(CheckResult(
                check_id="services.compose.up", name="Compose services running",
                ecosystem=self.ecosystem, status=CheckStatus.FAIL,
                evidence="cannot check: docker unavailable",
                remediation=[RemediationStep("Start Docker first", "", safe_fix=False)],
                depends_on=["services.container.present"],
            ))
        else:
            results.append(CheckResult(
                check_id="services.compose.up", name="Compose services running",
                ecosystem=self.ecosystem, status=CheckStatus.SKIP,
                evidence="no compose file",
                depends_on=["services.container.present"],
            ))

        # DB/Redis port checks (read-only TCP probe)
        port_checks = [
            ("services.db.port", 5432, "PostgreSQL", "db"),
            ("services.redis", 6379, "Redis", "redis"),
        ]
        for check_id, port, label, key in port_checks:
            if key in expected:
                ok = _port_open("127.0.0.1", port)
                results.append(CheckResult(
                    check_id=check_id, name=f"{label} reachable",
                    ecosystem=self.ecosystem,
                    status=CheckStatus.PASS if ok else CheckStatus.FAIL,
                    evidence=f"port {port} {'open' if ok else 'closed'}",
                    remediation=[] if ok else [
                        RemediationStep(f"Start {label}", f"docker compose up -d {key}",
                                        safe_fix=True, operation="start-service",
                                        argv=["docker", "compose", "up", "-d", key]),
                    ],
                    depends_on=["services.compose.up"],
                ))
            else:
                results.append(CheckResult(
                    check_id=check_id, name=f"{label} reachable",
                    ecosystem=self.ecosystem, status=CheckStatus.SKIP,
                    evidence="service not declared in compose",
                    depends_on=["services.compose.up"],
                ))

        env_path = os.path.join(ctx.repo_path, ".env")
        env_example = os.path.join(ctx.repo_path, ".env.example")
        if os.path.isfile(env_path):
            results.append(CheckResult(
                check_id="services.envfile", name=".env file present",
                ecosystem=self.ecosystem, status=CheckStatus.PASS,
                evidence=".env exists",
            ))
        elif os.path.isfile(env_example):
            results.append(CheckResult(
                check_id="services.envfile", name=".env file present",
                ecosystem=self.ecosystem, status=CheckStatus.FAIL,
                evidence=".env missing but .env.example exists",
                remediation=[RemediationStep("Create .env from template", "create-env",
                                             safe_fix=True, operation="create-env",
                                             argv=None, files=[".env.example", ".env"])],
            ))
        else:
            results.append(CheckResult(
                check_id="services.envfile", name=".env file present",
                ecosystem=self.ecosystem, status=CheckStatus.SKIP,
                evidence="no .env template present",
            ))
        return results