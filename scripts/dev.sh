#!/usr/bin/env bash
# Development startup script for AIAgentX
# Provides hot-reload, service management, and common dev workflows

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

function print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

function print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

function print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

function print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

function check_dependencies() {
    print_info "Checking dependencies..."
    
    local missing=()
    
    command -v docker >/dev/null 2>&1 || missing+=("docker")
    command -v docker-compose >/dev/null 2>&1 || missing+=("docker-compose")
    command -v python3 >/dev/null 2>&1 || missing+=("python3")
    command -v uv >/dev/null 2>&1 || missing+=("uv (or pip)")
    
    if [ ${#missing[@]} -ne 0 ]; then
        print_error "Missing dependencies: ${missing[*]}"
        print_info "Please install missing dependencies and try again"
        exit 1
    fi
    
    print_success "All dependencies found"
}

function setup_env() {
    if [ ! -f .env ]; then
        print_warning ".env file not found, copying from .env.example"
        cp .env.example .env
        print_info "Please edit .env with your configuration"
    fi
    
    # Source .env for this script
    set -a
    source .env
    set +a
}

function start_services() {
    print_info "Starting infrastructure services (PostgreSQL, Redis)..."
    docker-compose up -d
    
    print_info "Waiting for services to be healthy..."
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if docker-compose ps | grep -q "healthy"; then
            print_success "Services are healthy"
            return 0
        fi
        sleep 2
        ((attempt++))
    done
    
    print_error "Services failed to become healthy within timeout"
    docker-compose ps
    exit 1
}

function stop_services() {
    print_info "Stopping infrastructure services..."
    docker-compose down
    print_success "Services stopped"
}

function run_migrations() {
    print_info "Running database migrations..."
    alembic upgrade head
    print_success "Migrations complete"
}

function install_deps() {
    print_info "Installing Python dependencies..."
    if command -v uv >/dev/null 2>&1; then
        uv pip install -e ".[dev]"
    else
        pip install -e ".[dev]"
    fi
    print_success "Dependencies installed"
}

function run_server() {
    print_info "Starting development server with hot-reload..."
    print_info "API will be available at http://localhost:8000"
    print_info "Documentation at http://localhost:8000/docs"
    print_info "Press Ctrl+C to stop"
    echo
    
    exec uvicorn app.main:app \
        --reload \
        --reload-dir app \
        --host 0.0.0.0 \
        --port 8000 \
        --log-level info
}

function run_tests() {
    local test_type="${1:-unit}"
    
    case "$test_type" in
        unit)
            print_info "Running unit tests..."
            pytest tests/unit -v --tb=short
            ;;
        integration)
            print_info "Running integration tests..."
            pytest tests/integration -v --tb=short -m integration
            ;;
        all)
            print_info "Running all tests..."
            pytest tests/ -v --tb=short
            ;;
        *)
            print_error "Unknown test type: $test_type"
            print_info "Usage: $0 test [unit|integration|all]"
            exit 1
            ;;
    esac
}

function run_lint() {
    print_info "Running code quality checks..."
    
    print_info "Running Ruff (lint)..."
    ruff check .
    
    print_info "Running Ruff (format check)..."
    ruff format --check .
    
    print_info "Running MyPy (type check)..."
    mypy app
    
    print_success "All checks passed"
}

function run_format() {
    print_info "Formatting code with Ruff..."
    ruff format .
    print_success "Formatting complete"
}

function show_help() {
    cat << EOF
AIAgentX Development Script

Usage: $0 <command> [options]

Commands:
  start           Start services, run migrations, and launch dev server
  stop            Stop infrastructure services
  services        Start only infrastructure services (PostgreSQL, Redis)
  migrate         Run database migrations
  server          Start development server with hot-reload (assumes services running)
  test [type]     Run tests (unit|integration|all) - default: unit
  lint            Run all code quality checks (ruff + mypy)
  format          Format code with Ruff
  install         Install Python dependencies
  setup           Full setup: install deps, start services, run migrations
  help            Show this help message

Examples:
  $0 setup              # First-time setup
  $0 start              # Start everything and run server
  $0 test               # Run unit tests
  $0 test integration   # Run integration tests
  $0 lint               # Run all quality checks
  $0 stop               # Stop services
EOF
}

# Main command dispatch
case "${1:-help}" in
    start)
        check_dependencies
        setup_env
        install_deps
        start_services
        run_migrations
        run_server
        ;;
    stop)
        stop_services
        ;;
    services)
        check_dependencies
        setup_env
        start_services
        ;;
    migrate)
        setup_env
        run_migrations
        ;;
    server)
        setup_env
        run_server
        ;;
    test)
        setup_env
        run_tests "${2:-unit}"
        ;;
    lint)
        setup_env
        run_lint
        ;;
    format)
        setup_env
        run_format
        ;;
    install)
        check_dependencies
        setup_env
        install_deps
        ;;
    setup)
        check_dependencies
        setup_env
        install_deps
        start_services
        run_migrations
        print_success "Setup complete! Run '$0 server' to start the development server"
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac