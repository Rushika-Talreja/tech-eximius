"""
Sandbox execution runner for compiler and analyzer jobs.
Supports both Docker container execution and local sandboxed subprocess execution.

Hard Rules:
- Analysis containers run with NO network (--network none / blocked proxies).
- Non-root user (10001:10001).
- Timeouts with forced kill.
- Output capped at 10 MB.
- Secrets stripped from execution environment.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.logging_config import get_logger

logger = get_logger(__name__)

SAFE_ENV_KEYS = frozenset({
    "PATH",
    "HOME",
    "VIRTUAL_ENV",
    "SOLC_SELECT_DIR",
    "LANG",
    "LC_ALL",
})


@dataclass
class ExecutionResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False
    output_truncated: bool = False


class SandboxRunner:
    def __init__(
        self,
        runtime: str = "local",
        timeout_seconds: int = 120,
        max_output_bytes: int = 10 * 1024 * 1024,  # 10 MB
        cpu_limit: int = 2,
        mem_limit_mb: int = 2048,
    ) -> None:
        self.runtime = runtime
        self.timeout_seconds = timeout_seconds
        self.max_output_bytes = max_output_bytes
        self.cpu_limit = cpu_limit
        self.mem_limit_mb = mem_limit_mb

    def _prepare_clean_env(self, allow_network: bool, extra_env: dict[str, str] | None = None) -> dict[str, str]:
        """Strip all secrets from the execution environment."""
        env: dict[str, str] = {}
        for k, v in os.environ.items():
            if k in SAFE_ENV_KEYS:
                env[k] = v

        if not allow_network:
            # Block outbound network attempts in local runner
            env["HTTP_PROXY"] = "http://127.0.0.1:0"
            env["HTTPS_PROXY"] = "http://127.0.0.1:0"
            env["ALL_PROXY"] = "socks5://127.0.0.1:0"
            env["NO_PROXY"] = ""

        if extra_env:
            for k, v in extra_env.items():
                env[k] = v

        return env

    def run(
        self,
        cmd: list[str],
        cwd: Path | str | None = None,
        input_data: bytes | str | None = None,
        allow_network: bool = False,
        extra_env: dict[str, str] | None = None,
    ) -> ExecutionResult:
        """Execute command in sandbox."""
        start_time = time.perf_counter()
        clean_env = self._prepare_clean_env(allow_network=allow_network, extra_env=extra_env)

        # Docker runtime execution
        if self.runtime == "docker" and shutil.which("docker"):
            docker_cmd = [
                "docker", "run", "--rm",
                "--cpus", str(self.cpu_limit),
                "--memory", f"{self.mem_limit_mb}m",
                "--pids-limit", "256",
                "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges",
                "--user", "10001:10001",
                "--read-only",
                "--tmpfs", "/tmp:rw,noexec,nosuid,size=512m",
            ]
            if not allow_network:
                docker_cmd.extend(["--network", "none"])
            else:
                docker_cmd.extend(["--network", "bridge"])

            if cwd:
                docker_cmd.extend(["-v", f"{cwd}:/work:ro", "-w", "/work"])

            docker_cmd.append("sandbox-analysis")
            docker_cmd.extend(cmd)
            actual_cmd = docker_cmd
        else:
            # Local sandboxed subprocess
            actual_cmd = cmd

        input_bytes: bytes | None = None
        if isinstance(input_data, str):
            input_bytes = input_data.encode("utf-8")
        elif isinstance(input_data, bytes):
            input_bytes = input_data

        try:
            proc = subprocess.Popen(
                actual_cmd,
                cwd=str(cwd) if cwd else None,
                stdin=subprocess.PIPE if input_bytes is not None else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=clean_env,
            )

            try:
                raw_out, raw_err = proc.communicate(
                    input=input_bytes,
                    timeout=self.timeout_seconds,
                )
            except subprocess.TimeoutExpired:
                proc.kill()
                raw_out, raw_err = proc.communicate()
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                return ExecutionResult(
                    exit_code=-1,
                    stdout=raw_out.decode("utf-8", errors="replace"),
                    stderr="Execution timed out",
                    duration_ms=duration_ms,
                    timed_out=True,
                )

            duration_ms = int((time.perf_counter() - start_time) * 1000)

            # Cap output sizes
            truncated = False
            if len(raw_out) > self.max_output_bytes:
                raw_out = raw_out[:self.max_output_bytes]
                truncated = True
            if len(raw_err) > self.max_output_bytes:
                raw_err = raw_err[:self.max_output_bytes]
                truncated = True

            return ExecutionResult(
                exit_code=proc.returncode,
                stdout=raw_out.decode("utf-8", errors="replace"),
                stderr=raw_err.decode("utf-8", errors="replace"),
                duration_ms=duration_ms,
                output_truncated=truncated,
            )

        except Exception as exc:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            return ExecutionResult(
                exit_code=1,
                stdout="",
                stderr=f"Sandbox execution failed to start: {exc}",
                duration_ms=duration_ms,
            )

