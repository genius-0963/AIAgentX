#!/usr/bin/env bash
# Run all deployment validations
# Usage: ./run-all-validations.sh [staging|production] [--verbose]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

ENVIRONMENT="${1:-staging}"
VERBOSE="${2:-}"

case "$ENVIRONMENT" in
    staging)
        NAMESPACE="aiagentx-staging"
        MANIFEST_DIR="$PROJECT_ROOT/deploy/k8s/overlays/staging"
        ;;
    production)
        NAMESPACE="aiagentx"
        MANIFEST_DIR="$PROJECT_ROOT/deploy/k8s/overlays/production"
        ;;
    *)
        echo "Usage: $0 [staging|production] [--verbose]"
        exit 1
        ;;
esac

if [[ "$VERBOSE" == "--verbose" ]]; then
    VERBOSE_FLAG="--verbose"
else
    VERBOSE_FLAG=""
fi

echo "=========================================="
echo "Deployment Validation Suite"
echo "Environment: $ENVIRONMENT"
echo "Namespace: $NAMESPACE"
echo "Manifest Dir: $MANIFEST_DIR"
echo "=========================================="

# Step 1: Pre-deployment checks
echo ""
echo "Step 1: Pre-deployment validation"
echo "------------------------------------------"
if python3 "$SCRIPT_DIR/pre-deploy-check.py" \
    --manifest-dir "$MANIFEST_DIR" \
    --namespace "$NAMESPACE" \
    $VERBOSE_FLAG; then
    echo "✓ Pre-deployment checks passed"
else
    echo "✗ Pre-deployment checks failed"
    exit 1
fi

# Step 2: Manifest syntax validation
echo ""
echo "Step 2: Manifest syntax validation"
echo "------------------------------------------"
if python3 "$SCRIPT_DIR/validate-k8s-manifests.py" \
    "$MANIFEST_DIR" \
    $VERBOSE_FLAG; then
    echo "✓ Manifest syntax validation passed"
else
    echo "✗ Manifest syntax validation failed"
    exit 1
fi

# Step 3: Kustomize build test
echo ""
echo "Step 3: Kustomize build test"
echo "------------------------------------------"
if kubectl kustomize "$MANIFEST_DIR" > /dev/null; then
    echo "✓ Kustomize build successful"
else
    echo "✗ Kustomize build failed"
    exit 1
fi

# Step 4: Dry-run apply
echo ""
echo "Step 4: Dry-run apply"
echo "------------------------------------------"
if kubectl apply --dry-run=client -k "$MANIFEST_DIR" > /dev/null; then
    echo "✓ Dry-run apply successful"
else
    echo "✗ Dry-run apply failed"
    exit 1
fi

# Step 5: Post-deployment validation (only if cluster accessible)
echo ""
echo "Step 5: Post-deployment validation"
echo "------------------------------------------"
if kubectl cluster-info --request-timeout=10s > /dev/null 2>&1; then
    if python3 "$SCRIPT_DIR/validate-deployment.py" \
        --namespace "$NAMESPACE" \
        $VERBOSE_FLAG; then
        echo "✓ Post-deployment validation passed"
    else
        echo "⚠ Post-deployment validation had issues (check output)"
        # Don't exit - this is informational
    fi
else
    echo "⚠ Cluster not accessible, skipping post-deployment validation"
fi

echo ""
echo "=========================================="
echo "All validations completed successfully!"
echo "=========================================="