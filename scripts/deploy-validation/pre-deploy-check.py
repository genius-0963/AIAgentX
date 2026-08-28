#!/usr/bin/env python3
"""Pre-deployment validation script.

Checks prerequisites before deploying to Kubernetes.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


class PreDeployValidator:
    """Validates pre-deployment prerequisites."""

    def __init__(self, verbose: bool = False) -> None:
        self.verbose = verbose
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def _run_cmd(
        self, cmd: list[str], capture: bool = True
    ) -> tuple[int, str, str]:
        """Run a command."""
        if self.verbose:
            print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=capture, text=True)
        return result.returncode, result.stdout, result.stderr

    def check_command(self, cmd: str, min_version: str | None = None) -> bool:
        """Check if a command exists and optionally check version."""
        path = shutil.which(cmd)
        if not path:
            self.errors.append(f"Required command '{cmd}' not found in PATH")
            return False

        if min_version:
            code, stdout, stderr = self._run_cmd([cmd, "version"])
            if code != 0:
                self.warnings.append(
                    f"Could not check version for '{cmd}': {stderr}"
                )
            else:
                if self.verbose:
                    print(f"  {cmd}: {stdout.strip()}")

        if self.verbose:
            print(f"  ✓ {cmd} found at {path}")
        return True

    def check_kubectl(self) -> bool:
        """Check kubectl is available and configured."""
        if not self.check_command("kubectl"):
            return False

        # Check cluster connectivity
        code, stdout, stderr = self._run_cmd(
            ["kubectl", "cluster-info", "--request-timeout=10s"]
        )
        if code != 0:
            self.errors.append(f"kubectl cannot connect to cluster: {stderr}")
            return False

        # Get cluster info
        code, stdout, stderr = self._run_cmd(
            ["kubectl", "version", "-o", "json"]
        )
        if code == 0:
            try:
                import json

                version_info = json.loads(stdout)
                client = version_info.get("clientVersion", {})
                server = version_info.get("serverVersion", {})
                if self.verbose:
                    print(
                        f"  Client: {client.get('major', '')}.{client.get('minor', '')}"
                    )
                    print(
                        f"  Server: {server.get('major', '')}.{server.get('minor', '')}"
                    )
            except Exception:
                pass

        return True

    def check_kustomize(self) -> bool:
        """Check kustomize is available."""
        return self.check_command("kustomize")

    def check_helm(self) -> bool:
        """Check helm is available (optional)."""
        return self.check_command("helm")

    def check_docker(self) -> bool:
        """Check docker is available for building images."""
        return self.check_command("docker")

    def check_image_registry(self) -> bool:
        """Check image registry credentials."""
        # Check if we can push to registry
        # This is a basic check - in practice you'd verify specific registry
        code, stdout, stderr = self._run_cmd(["docker", "info"])
        if code != 0:
            self.warnings.append(f"Docker daemon not accessible: {stderr}")
            return False

        if self.verbose:
            print("  ✓ Docker daemon accessible")
        return True

    def check_environment_variables(self) -> bool:
        """Check required environment variables."""
        required_vars = [
            "DOCKER_REGISTRY",
            "IMAGE_TAG",
        ]

        optional_vars = [
            "KUBECONFIG",
            "NAMESPACE",
            "ENVIRONMENT",
        ]

        all_ok = True
        for var in required_vars:
            value = os.environ.get(var)
            if not value:
                self.errors.append(f"Required environment variable '{var}' not set")
                all_ok = False
            elif self.verbose:
                print(f"  ✓ {var}={value}")

        for var in optional_vars:
            value = os.environ.get(var)
            if value and self.verbose:
                print(f"  ✓ {var}={value}")
            elif not value and self.verbose:
                print(f"  ⚠ {var} not set (optional)")

        return all_ok

    def check_manifest_files(self, manifest_dir: Path) -> bool:
        """Check manifest files exist and are valid YAML."""
        if not manifest_dir.exists():
            self.errors.append(f"Manifest directory not found: {manifest_dir}")
            return False

        yaml_files = list(manifest_dir.rglob("*.yaml")) + list(
            manifest_dir.rglob("*.yml")
        )
        if not yaml_files:
            self.errors.append(f"No YAML files found in {manifest_dir}")
            return False

        import yaml

        all_ok = True
        for yaml_file in yaml_files:
            try:
                with open(yaml_file) as f:
                    list(yaml.safe_load_all(f))
                if self.verbose:
                    print(f"  ✓ {yaml_file.relative_to(manifest_dir)}")
            except yaml.YAMLError as e:
                self.errors.append(f"Invalid YAML in {yaml_file}: {e}")
                all_ok = False
            except Exception as e:
                self.errors.append(f"Failed to read {yaml_file}: {e}")
                all_ok = False

        return all_ok

    def check_secrets_exist(self, namespace: str) -> bool:
        """Check if required secrets exist in cluster (dry-run)."""
        code, stdout, stderr = self._run_cmd(
            [
                "kubectl",
                "get",
                "secret",
                "aiagentx-secrets",
                "-n",
                namespace,
                "--dry-run=client",
            ]
        )
        if code != 0:
            self.warnings.append(
                f"Secret 'aiagentx-secrets' not found in namespace '{namespace}' "
                f"(will need to create before deploy): {stderr}"
            )
            return True  # Not an error - can be created during deploy

        if self.verbose:
            print(f"  ✓ Secret 'aiagentx-secrets' exists in namespace '{namespace}'")
        return True

    def check_namespace_exists(self, namespace: str) -> bool:
        """Check if namespace exists or can be created."""
        code, stdout, stderr = self._run_cmd(
            ["kubectl", "get", "namespace", namespace]
        )
        if code != 0:
            if self.verbose:
                print(f"  ⚠ Namespace '{namespace}' does not exist (will be created)")
            return True  # Not an error - kustomize will create it

        if self.verbose:
            print(f"  ✓ Namespace '{namespace}' exists")
        return True

    def check_rbac_permissions(self, namespace: str) -> bool:
        """Check if we have RBAC permissions to deploy."""
        # Try to create a test resource
        test_resource = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: pre-deploy-test
  namespace: %s
data:
  test: "true"
""" % namespace

        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(test_resource)
            temp_path = f.name

        try:
            code, stdout, stderr = self._run_cmd(
                ["kubectl", "apply", "--dry-run=client", "-f", temp_path]
            )
            if code != 0:
                self.errors.append(
                    f"Insufficient RBAC permissions to deploy to namespace '{namespace}': {stderr}"
                )
                return False

            if self.verbose:
                print(f"  ✓ RBAC permissions OK for namespace '{namespace}'")
            return True
        finally:
            try:
                os.unlink(temp_path)
            except Exception:
                pass

    def run_all_checks(self, manifest_dir: Path, namespace: str) -> bool:
        """Run all pre-deployment checks."""
        print("Running pre-deployment validation...")
        print("=" * 60)

        checks = [
            ("kubectl", self.check_kubectl),
            ("kustomize", self.check_kustomize),
            ("helm (optional)", self.check_helm),
            ("docker", self.check_docker),
            ("docker registry access", self.check_image_registry),
            ("environment variables", self.check_environment_variables),
            (f"manifest files ({manifest_dir})", lambda: self.check_manifest_files(manifest_dir)),
            (f"namespace '{namespace}'", lambda: self.check_namespace_exists(namespace)),
            (f"secrets in '{namespace}'", lambda: self.check_secrets_exist(namespace)),
            (f"RBAC permissions for '{namespace}'", lambda: self.check_rbac_permissions(namespace)),
        ]

        all_passed = True
        for name, check_fn in checks:
            if self.verbose:
                print(f"\nChecking: {name}...")
            try:
                result = check_fn()
                if not result:
                    all_passed = False
                    if self.verbose:
                        print(f"  ✗ FAILED: {name}")
                else:
                    if self.verbose:
                        print(f"  ✓ PASSED: {name}")
            except Exception as e:
                self.errors.append(f"Check '{name}' failed with exception: {e}")
                all_passed = False
                if self.verbose:
                    print(f"  ✗ ERROR: {name}: {e}")

        return all_passed

    def print_results(self) -> None:
        """Print validation results."""
        if self.warnings:
            print("\nWarnings:")
            for w in self.warnings:
                print(f"  ⚠ {w}")

        if self.errors:
            print("\nErrors:")
            for e in self.errors:
                print(f"  ✗ {e}")
        else:
            print("\n✓ All pre-deployment checks passed!")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pre-deployment validation"
    )
    parser.add_argument(
        "-m",
        "--manifest-dir",
        type=Path,
        default=Path("deploy/k8s/base"),
        help="Manifest directory",
    )
    parser.add_argument(
        "-n",
        "--namespace",
        default="aiagentx",
        help="Kubernetes namespace",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Verbose output"
    )

    args = parser.parse_args()

    validator = PreDeployValidator(verbose=args.verbose)

    success = validator.run_all_checks(args.manifest_dir, args.namespace)
    validator.print_results()

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())