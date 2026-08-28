#!/usr/bin/env python3
"""Kubernetes manifest validation script.

Validates K8s manifests for syntax, best practices, and required fields.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml


class ManifestValidator:
    """Validates Kubernetes manifests."""

    def __init__(self, verbose: bool = False) -> None:
        self.verbose = verbose
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def validate_file(self, filepath: Path) -> bool:
        """Validate a single YAML file."""
        try:
            with open(filepath) as f:
                docs = list(yaml.safe_load_all(f))
        except yaml.YAMLError as e:
            self.errors.append(f"{filepath}: YAML syntax error: {e}")
            return False
        except Exception as e:
            self.errors.append(f"{filepath}: Failed to read: {e}")
            return False

        valid = True
        for i, doc in enumerate(docs):
            if doc is None:
                continue
            if not self._validate_document(doc, filepath, i):
                valid = False

        return valid

    def _validate_document(
        self, doc: dict[str, Any], filepath: Path, doc_index: int
    ) -> bool:
        """Validate a single Kubernetes resource document."""
        valid = True

        # Check required fields
        if "apiVersion" not in doc:
            self.errors.append(
                f"{filepath}:doc[{doc_index}]: Missing required field 'apiVersion'"
            )
            valid = False

        if "kind" not in doc:
            self.errors.append(
                f"{filepath}:doc[{doc_index}]: Missing required field 'kind'"
            )
            valid = False

        if "metadata" not in doc:
            self.errors.append(
                f"{filepath}:doc[{doc_index}]: Missing required field 'metadata'"
            )
            valid = False
        else:
            metadata = doc["metadata"]
            if "name" not in metadata:
                self.errors.append(
                    f"{filepath}:doc[{doc_index}]: Missing metadata.name"
                )
                valid = False

            # Check for labels
            if "labels" not in metadata:
                self.warnings.append(
                    f"{filepath}:doc[{doc_index}]: Missing metadata.labels (recommended)"
                )

        # Kind-specific validations
        kind = doc.get("kind", "")
        if kind == "Deployment":
            valid &= self._validate_deployment(doc, filepath, doc_index)
        elif kind == "Service":
            valid &= self._validate_service(doc, filepath, doc_index)
        elif kind == "HorizontalPodAutoscaler":
            valid &= self._validate_hpa(doc, filepath, doc_index)
        elif kind == "PodDisruptionBudget":
            valid &= self._validate_pdb(doc, filepath, doc_index)
        elif kind == "NetworkPolicy":
            valid &= self._validate_network_policy(doc, filepath, doc_index)
        elif kind == "Ingress":
            valid &= self._validate_ingress(doc, filepath, doc_index)

        return valid

    def _validate_deployment(
        self, doc: dict[str, Any], filepath: Path, doc_index: int
    ) -> bool:
        """Validate Deployment resource."""
        valid = True
        spec = doc.get("spec", {})

        # Check replicas
        if "replicas" not in spec:
            self.warnings.append(
                f"{filepath}:doc[{doc_index}]: Deployment missing replicas (default: 1)"
            )

        # Check selector
        if "selector" not in spec:
            self.errors.append(
                f"{filepath}:doc[{doc_index}]: Deployment missing spec.selector"
            )
            valid = False
        elif "matchLabels" not in spec["selector"]:
            self.errors.append(
                f"{filepath}:doc[{doc_index}]: Deployment selector missing matchLabels"
            )
            valid = False

        # Check template
        if "template" not in spec:
            self.errors.append(
                f"{filepath}:doc[{doc_index}]: Deployment missing spec.template"
            )
            valid = False
        else:
            template = spec["template"]
            if "metadata" not in template or "labels" not in template["metadata"]:
                self.errors.append(
                    f"{filepath}:doc[{doc_index}]: Deployment template missing metadata.labels"
                )
                valid = False
            else:
                # Verify selector matches template labels
                selector_labels = spec.get("selector", {}).get("matchLabels", {})
                template_labels = template["metadata"].get("labels", {})
                for key, value in selector_labels.items():
                    if template_labels.get(key) != value:
                        self.errors.append(
                            f"{filepath}:doc[{doc_index}]: Selector label '{key}={value}' "
                            f"does not match template label '{template_labels.get(key)}'"
                        )
                        valid = False

            # Check containers
            if "spec" in template:
                pod_spec = template["spec"]
                if "containers" not in pod_spec or not pod_spec["containers"]:
                    self.errors.append(
                        f"{filepath}:doc[{doc_index}]: Deployment has no containers"
                    )
                    valid = False
                else:
                    for j, container in enumerate(pod_spec["containers"]):
                        valid &= self._validate_container(
                            container, filepath, doc_index, j
                        )

        # Check strategy
        if "strategy" not in spec:
            self.warnings.append(
                f"{filepath}:doc[{doc_index}]: Deployment missing strategy (recommend RollingUpdate)"
            )

        return valid

    def _validate_container(
        self,
        container: dict[str, Any],
        filepath: Path,
        doc_index: int,
        container_index: int,
    ) -> bool:
        """Validate container specification."""
        valid = True
        prefix = f"{filepath}:doc[{doc_index}]:container[{container_index}]"

        # Required fields
        if "name" not in container:
            self.errors.append(f"{prefix}: Missing container name")
            valid = False

        if "image" not in container:
            self.errors.append(f"{prefix}: Missing container image")
            valid = False
        elif ":latest" in container["image"] or container["image"].endswith(":"):
            self.warnings.append(
                f"{prefix}: Using 'latest' tag or no tag (not recommended for production)"
            )

        # Check resources
        if "resources" not in container:
            self.warnings.append(
                f"{prefix}: Missing resource requests/limits (recommended for production)"
            )
        else:
            resources = container["resources"]
            if "requests" not in resources:
                self.warnings.append(f"{prefix}: Missing resource requests")
            if "limits" not in resources:
                self.warnings.append(f"{prefix}: Missing resource limits")

        # Check probes
        for probe_type in ["livenessProbe", "readinessProbe"]:
            if probe_type not in container:
                self.warnings.append(
                    f"{prefix}: Missing {probe_type} (recommended for production)"
                )

        # Check security context
        if "securityContext" not in container:
            self.warnings.append(
                f"{prefix}: Missing securityContext (recommended: runAsNonRoot, readOnlyRootFilesystem)"
            )

        return valid

    def _validate_service(
        self, doc: dict[str, Any], filepath: Path, doc_index: int
    ) -> bool:
        """Validate Service resource."""
        valid = True
        spec = doc.get("spec", {})

        if "selector" not in spec:
            self.warnings.append(
                f"{filepath}:doc[{doc_index}]: Service missing selector (headless service?)"
            )

        if "ports" not in spec or not spec["ports"]:
            self.errors.append(
                f"{filepath}:doc[{doc_index}]: Service missing ports"
            )
            valid = False

        return valid

    def _validate_hpa(
        self, doc: dict[str, Any], filepath: Path, doc_index: int
    ) -> bool:
        """Validate HorizontalPodAutoscaler resource."""
        valid = True
        spec = doc.get("spec", {})

        if "scaleTargetRef" not in spec:
            self.errors.append(
                f"{filepath}:doc[{doc_index}]: HPA missing scaleTargetRef"
            )
            valid = False

        if "minReplicas" not in spec:
            self.warnings.append(
                f"{filepath}:doc[{doc_index}]: HPA missing minReplicas"
            )

        if "maxReplicas" not in spec:
            self.errors.append(
                f"{filepath}:doc[{doc_index}]: HPA missing maxReplicas"
            )
            valid = False

        if "metrics" not in spec or not spec["metrics"]:
            self.warnings.append(
                f"{filepath}:doc[{doc_index}]: HPA missing metrics (will use CPU only)"
            )

        if "behavior" not in spec:
            self.warnings.append(
                f"{filepath}:doc[{doc_index}]: HPA missing scaling behavior config"
            )

        return valid

    def _validate_pdb(
        self, doc: dict[str, Any], filepath: Path, doc_index: int
    ) -> bool:
        """Validate PodDisruptionBudget resource."""
        valid = True
        spec = doc.get("spec", {})

        if "minAvailable" not in spec and "maxUnavailable" not in spec:
            self.errors.append(
                f"{filepath}:doc[{doc_index}]: PDB missing minAvailable or maxUnavailable"
            )
            valid = False

        if "selector" not in spec:
            self.errors.append(
                f"{filepath}:doc[{doc_index}]: PDB missing selector"
            )
            valid = False

        return valid

    def _validate_network_policy(
        self, doc: dict[str, Any], filepath: Path, doc_index: int
    ) -> bool:
        """Validate NetworkPolicy resource."""
        valid = True
        spec = doc.get("spec", {})

        if "podSelector" not in spec:
            self.errors.append(
                f"{filepath}:doc[{doc_index}]: NetworkPolicy missing podSelector"
            )
            valid = False

        if "policyTypes" not in spec:
            self.warnings.append(
                f"{filepath}:doc[{doc_index}]: NetworkPolicy missing policyTypes"
            )

        if "ingress" not in spec and "egress" not in spec:
            self.warnings.append(
                f"{filepath}:doc[{doc_index}]: NetworkPolicy has no ingress or egress rules"
            )

        return valid

    def _validate_ingress(
        self, doc: dict[str, Any], filepath: Path, doc_index: int
    ) -> bool:
        """Validate Ingress resource."""
        valid = True
        spec = doc.get("spec", {})

        if "rules" not in spec or not spec["rules"]:
            self.errors.append(
                f"{filepath}:doc[{doc_index}]: Ingress missing rules"
            )
            valid = False

        if "ingressClassName" not in spec:
            self.warnings.append(
                f"{filepath}:doc[{doc_index}]: Ingress missing ingressClassName"
            )

        if "tls" not in spec:
            self.warnings.append(
                f"{filepath}:doc[{doc_index}]: Ingress missing TLS config"
            )

        return valid

    def validate_directory(self, directory: Path) -> bool:
        """Validate all YAML files in a directory."""
        valid = True
        for filepath in directory.rglob("*.yaml"):
            # Skip kustomization.yaml files (they're not K8s resources)
            if filepath.name == "kustomization.yaml":
                continue
            if self.verbose:
                print(f"Validating {filepath}...")
            if not self.validate_file(filepath):
                valid = False
        return valid

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
            print("\n✓ All validations passed!")

    def has_errors(self) -> bool:
        return len(self.errors) > 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Kubernetes manifests"
    )
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="Paths to manifest files or directories",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Verbose output"
    )
    parser.add_argument(
        "--fail-on-warning", action="store_true", help="Treat warnings as errors"
    )

    args = parser.parse_args()

    validator = ManifestValidator(verbose=args.verbose)

    for path in args.paths:
        if path.is_dir():
            validator.validate_directory(path)
        else:
            validator.validate_file(path)

    validator.print_results()

    if validator.has_errors() or (args.fail_on_warning and validator.warnings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())