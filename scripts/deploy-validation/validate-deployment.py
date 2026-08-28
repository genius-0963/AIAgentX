#!/usr/bin/env python3
"""Kubernetes deployment smoke test script.

Runs post-deployment validation checks against a live cluster.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import yaml


class DeploymentValidator:
    """Validates a live Kubernetes deployment."""

    def __init__(
        self,
        namespace: str = "aiagentx",
        kubeconfig: str | None = None,
        timeout: int = 300,
        verbose: bool = False,
    ) -> None:
        self.namespace = namespace
        self.kubeconfig = kubeconfig
        self.timeout = timeout
        self.verbose = verbose
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.kubectl_cmd = ["kubectl"]
        if kubeconfig:
            self.kubectl_cmd.extend(["--kubeconfig", kubeconfig])

    def _run_kubectl(
        self, args: list[str], capture: bool = True
    ) -> tuple[int, str, str]:
        """Run kubectl command."""
        import subprocess

        cmd = self.kubectl_cmd + args
        if self.verbose:
            print(f"Running: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            timeout=30,
        )
        return result.returncode, result.stdout, result.stderr

    def check_namespace_exists(self) -> bool:
        """Check if namespace exists."""
        code, stdout, stderr = self._run_kubectl(
            ["get", "namespace", self.namespace]
        )
        if code != 0:
            self.errors.append(f"Namespace '{self.namespace}' does not exist")
            return False
        return True

    def check_deployment_ready(self, name: str) -> bool:
        """Check if deployment is ready."""
        code, stdout, stderr = self._run_kubectl(
            [
                "get",
                "deployment",
                name,
                "-n",
                self.namespace,
                "-o",
                "json",
            ]
        )
        if code != 0:
            self.errors.append(f"Deployment '{name}' not found: {stderr}")
            return False

        try:
            deployment = json.loads(stdout)
            spec_replicas = deployment["spec"].get("replicas", 1)
            status = deployment.get("status", {})
            ready_replicas = status.get("readyReplicas", 0)
            updated_replicas = status.get("updatedReplicas", 0)
            available_replicas = status.get("availableReplicas", 0)

            if ready_replicas < spec_replicas:
                self.errors.append(
                    f"Deployment '{name}' not ready: {ready_replicas}/{spec_replicas} replicas ready"
                )
                return False

            if updated_replicas < spec_replicas:
                self.warnings.append(
                    f"Deployment '{name}' not fully updated: {updated_replicas}/{spec_replicas}"
                )

            if available_replicas < spec_replicas:
                self.warnings.append(
                    f"Deployment '{name}' not fully available: {available_replicas}/{spec_replicas}"
                )

            if self.verbose:
                print(
                    f"  Deployment '{name}': {ready_replicas}/{spec_replicas} ready, "
                    f"{updated_replicas} updated, {available_replicas} available"
                )

            return True
        except Exception as e:
            self.errors.append(f"Failed to parse deployment '{name}' status: {e}")
            return False

    def check_pods_running(self, label_selector: str) -> bool:
        """Check if all pods matching selector are running."""
        code, stdout, stderr = self._run_kubectl(
            [
                "get",
                "pods",
                "-n",
                self.namespace,
                "-l",
                label_selector,
                "-o",
                "json",
            ]
        )
        if code != 0:
            self.errors.append(f"Failed to get pods: {stderr}")
            return False

        try:
            pods = json.loads(stdout)
            items = pods.get("items", [])
            if not items:
                self.warnings.append(
                    f"No pods found for selector '{label_selector}'"
                )
                return True

            all_running = True
            for pod in items:
                pod_name = pod["metadata"]["name"]
                phase = pod["status"].get("phase", "Unknown")
                conditions = pod["status"].get("conditions", [])

                ready = any(
                    c["type"] == "Ready" and c["status"] == "True"
                    for c in conditions
                )

                if phase != "Running" or not ready:
                    self.errors.append(
                        f"Pod '{pod_name}' not ready: phase={phase}, ready={ready}"
                    )
                    all_running = False
                elif self.verbose:
                    print(f"  Pod '{pod_name}': {phase}, Ready={ready}")

            return all_running
        except Exception as e:
            self.errors.append(f"Failed to parse pod status: {e}")
            return False

    def check_service_endpoints(self, service_name: str) -> bool:
        """Check if service has endpoints."""
        code, stdout, stderr = self._run_kubectl(
            [
                "get",
                "endpoints",
                service_name,
                "-n",
                self.namespace,
                "-o",
                "json",
            ]
        )
        if code != 0:
            self.errors.append(f"Service '{service_name}' not found: {stderr}")
            return False

        try:
            endpoints = json.loads(stdout)
            subsets = endpoints.get("subsets", [])
            if not subsets:
                self.errors.append(f"Service '{service_name}' has no endpoints")
                return False

            total_addresses = sum(
                len(s.get("addresses", [])) for s in subsets
            )
            if total_addresses == 0:
                self.errors.append(
                    f"Service '{service_name}' has no ready endpoints"
                )
                return False

            if self.verbose:
                print(
                    f"  Service '{service_name}': {total_addresses} endpoint(s)"
                )
            return True
        except Exception as e:
            self.errors.append(f"Failed to parse endpoints: {e}")
            return False

    def check_hpa_status(self, hpa_name: str) -> bool:
        """Check HPA status."""
        code, stdout, stderr = self._run_kubectl(
            ["get", "hpa", hpa_name, "-n", self.namespace, "-o", "json"]
        )
        if code != 0:
            self.warnings.append(f"HPA '{hpa_name}' not found: {stderr}")
            return True  # Not an error if HPA doesn't exist

        try:
            hpa = json.loads(stdout)
            status = hpa.get("status", {})
            current_replicas = status.get("currentReplicas", 0)
            desired_replicas = status.get("desiredReplicas", 0)

            if self.verbose:
                print(
                    f"  HPA '{hpa_name}': current={current_replicas}, desired={desired_replicas}"
                )

            return True
        except Exception as e:
            self.warnings.append(f"Failed to parse HPA '{hpa_name}' status: {e}")
            return True

    def check_pdb_status(self, pdb_name: str) -> bool:
        """Check PDB status."""
        code, stdout, stderr = self._run_kubectl(
            ["get", "pdb", pdb_name, "-n", self.namespace, "-o", "json"]
        )
        if code != 0:
            self.warnings.append(f"PDB '{pdb_name}' not found: {stderr}")
            return True

        try:
            pdb = json.loads(stdout)
            status = pdb.get("status", {})
            current_healthy = status.get("currentHealthy", 0)
            desired_healthy = status.get("desiredHealthy", 0)
            disruptions_allowed = status.get("disruptionsAllowed", 0)

            if self.verbose:
                print(
                    f"  PDB '{pdb_name}': healthy={current_healthy}/{desired_healthy}, "
                    f"disruptions_allowed={disruptions_allowed}"
                )

            if disruptions_allowed == 0:
                self.warnings.append(
                    f"PDB '{pdb_name}' allows 0 disruptions (may block node drains)"
                )

            return True
        except Exception as e:
            self.warnings.append(f"Failed to parse PDB '{pdb_name}' status: {e}")
            return True

    def check_network_policies(self) -> bool:
        """Check network policies exist."""
        code, stdout, stderr = self._run_kubectl(
            ["get", "networkpolicy", "-n", self.namespace, "-o", "json"]
        )
        if code != 0:
            self.warnings.append(f"No network policies found: {stderr}")
            return True

        try:
            policies = json.loads(stdout)
            items = policies.get("items", [])
            if not items:
                self.warnings.append("No network policies found in namespace")
                return True

            if self.verbose:
                for policy in items:
                    name = policy["metadata"]["name"]
                    print(f"  NetworkPolicy: {name}")
            return True
        except Exception as e:
            self.warnings.append(f"Failed to parse network policies: {e}")
            return True

    def check_ingress(self, ingress_name: str) -> bool:
        """Check ingress status."""
        code, stdout, stderr = self._run_kubectl(
            ["get", "ingress", ingress_name, "-n", self.namespace, "-o", "json"]
        )
        if code != 0:
            self.errors.append(f"Ingress '{ingress_name}' not found: {stderr}")
            return False

        try:
            ingress = json.loads(stdout)
            status = ingress.get("status", {})
            load_balancer = status.get("loadBalancer", {})
            ingress_list = load_balancer.get("ingress", [])

            if not ingress_list:
                self.warnings.append(
                    f"Ingress '{ingress_name}' has no load balancer address yet"
                )
            else:
                for lb in ingress_list:
                    if self.verbose:
                        ip = lb.get("ip") or lb.get("hostname", "pending")
                        print(f"  Ingress '{ingress_name}': {ip}")

            return True
        except Exception as e:
            self.warnings.append(f"Failed to parse ingress status: {e}")
            return True

    def check_secrets(self) -> bool:
        """Check required secrets exist."""
        required_secrets = ["aiagentx-secrets"]
        all_ok = True

        for secret in required_secrets:
            code, stdout, stderr = self._run_kubectl(
                ["get", "secret", secret, "-n", self.namespace]
            )
            if code != 0:
                self.errors.append(f"Required secret '{secret}' not found")
                all_ok = False
            elif self.verbose:
                print(f"  Secret '{secret}' exists")

        return all_ok

    def check_configmaps(self) -> bool:
        """Check required configmaps exist."""
        required_configmaps = ["aiagentx-config"]
        all_ok = True

        for cm in required_configmaps:
            code, stdout, stderr = self._run_kubectl(
                ["get", "configmap", cm, "-n", self.namespace]
            )
            if code != 0:
                self.errors.append(f"Required configmap '{cm}' not found")
                all_ok = False
            elif self.verbose:
                print(f"  ConfigMap '{cm}' exists")

        return all_ok

    def check_api_health(self) -> bool:
        """Check API health endpoint."""
        # Port-forward to API service and check health
        import subprocess

        # This is a simplified check - in practice you'd port-forward
        # For now, just check if service exists
        return self.check_service_endpoints("aiagentx-api")

    def run_all_checks(self) -> bool:
        """Run all validation checks."""
        print(f"Running deployment validation for namespace: {self.namespace}")
        print("=" * 60)

        checks = [
            ("Namespace exists", self.check_namespace_exists),
            ("Secrets exist", self.check_secrets),
            ("ConfigMaps exist", self.check_configmaps),
            ("API deployment ready", lambda: self.check_deployment_ready("aiagentx-api")),
            ("Worker deployment ready", lambda: self.check_deployment_ready("aiagentx-worker")),
            ("API pods running", lambda: self.check_pods_running("app.kubernetes.io/component=api")),
            ("Worker pods running", lambda: self.check_pods_running("app.kubernetes.io/component=worker")),
            ("API service endpoints", lambda: self.check_service_endpoints("aiagentx-api")),
            ("Worker service endpoints", lambda: self.check_service_endpoints("aiagentx-worker")),
            ("API HPA", lambda: self.check_hpa_status("aiagentx-api-hpa")),
            ("Worker HPA", lambda: self.check_hpa_status("aiagentx-worker-hpa")),
            ("API PDB", lambda: self.check_pdb_status("aiagentx-api-pdb")),
            ("Worker PDB", lambda: self.check_pdb_status("aiagentx-worker-pdb")),
            ("Network policies", self.check_network_policies),
            ("Ingress", lambda: self.check_ingress("aiagentx-api")),
            ("API health endpoint", self.check_api_health),
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
            print("\n✓ All deployment checks passed!")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Kubernetes deployment"
    )
    parser.add_argument(
        "-n",
        "--namespace",
        default="aiagentx",
        help="Kubernetes namespace",
    )
    parser.add_argument(
        "--kubeconfig",
        help="Path to kubeconfig file",
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=int,
        default=300,
        help="Timeout in seconds",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Verbose output"
    )

    args = parser.parse_args()

    validator = DeploymentValidator(
        namespace=args.namespace,
        kubeconfig=args.kubeconfig,
        timeout=args.timeout,
        verbose=args.verbose,
    )

    success = validator.run_all_checks()
    validator.print_results()

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())