#!/usr/bin/env bash
# Database restore script for AIAgentX
# Restores from backup created by backup.sh

set -euo pipefail

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/backups}"
POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_DB="${POSTGRES_DB:-aiagentx}"
POSTGRES_USER="${POSTGRES_USER:-aiagentx}"
ENCRYPTION_KEY="${BACKUP_ENCRYPTION_KEY:-}"
S3_BUCKET="${BACKUP_S3_BUCKET:-}"
S3_PREFIX="${BACKUP_S3_PREFIX:-aiagentx/backups}"

# Usage
usage() {
    cat <<EOF
Usage: $0 [OPTIONS] <backup-file|TIMESTAMP>

Options:
    -l, --list              List available backups
    -d, --download          Download from S3 before restore
    -f, --force             Force restore without confirmation
    -h, --help              Show this help

Arguments:
    <backup-file>           Path to backup file (local or S3)
    <TIMESTAMP>             Timestamp in format YYYYMMDD_HHMMSS (will find matching backup)

Examples:
    $0 20240115_020000
    $0 /backups/aiagentx_20240115_020000.sql.gz
    $0 --download 20240115_020000
    $0 --list
EOF
}

# Logging function
log() {
    echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] $*"
}

# Check required tools
check_tools() {
    for tool in psql; do
        if ! command -v $tool &> /dev/null; then
            log "ERROR: Required tool '$tool' not found"
            exit 1
        fi
    done
    
    if [[ -n "$ENCRYPTION_KEY" ]] && ! command -v openssl &> /dev/null; then
        log "ERROR: openssl required for decryption but not found"
        exit 1
    fi
    
    if [[ -n "$S3_BUCKET" ]] && ! command -v aws &> /dev/null; then
        log "ERROR: aws cli required for S3 download but not found"
        exit 1
    fi
}

# List available backups
list_backups() {
    log "Available local backups:"
    ls -lh "$BACKUP_DIR"/aiagentx_*.sql.gz* 2>/dev/null || log "No local backups found"
    
    if [[ -n "$S3_BUCKET" ]]; then
        log "Available S3 backups:"
        aws s3 ls "s3://$S3_BUCKET/$S3_PREFIX/" | grep aiagentx_ || log "No S3 backups found"
    fi
}

# Find backup file by timestamp
find_backup() {
    local timestamp="$1"
    local backup_file
    
    # Try local first
    backup_file=$(ls -t "$BACKUP_DIR"/aiagentx_"$timestamp".sql.gz* 2>/dev/null | head -1)
    
    if [[ -n "$backup_file" && -f "$backup_file" ]]; then
        echo "$backup_file"
        return 0
    fi
    
    # Try S3 if configured
    if [[ -n "$S3_BUCKET" ]]; then
        log "Searching S3 for backup with timestamp: $timestamp"
        aws s3 ls "s3://$S3_BUCKET/$S3_PREFIX/" | grep "aiagentx_${timestamp}" | head -1
    fi
    
    return 1
}

# Download from S3
download_backup() {
    local s3_key="$1"
    local local_file="$BACKUP_DIR/$(basename "$s3_key")"
    
    log "Downloading from S3: s3://$S3_BUCKET/$S3_PREFIX/$s3_key"
    aws s3 cp "s3://$S3_BUCKET/$S3_PREFIX/$s3_key" "$local_file"
    
    if [[ $? -ne 0 ]]; then
        log "ERROR: S3 download failed"
        exit 1
    fi
    
    echo "$local_file"
}

# Decrypt backup if needed
decrypt_backup() {
    local input_file="$1"
    local output_file="${input_file%.enc}"
    
    if [[ "$input_file" == *.enc ]]; then
        if [[ -z "$ENCRYPTION_KEY" ]]; then
            log "ERROR: Encrypted backup but no encryption key provided"
            exit 1
        fi
        
        log "Decrypting backup..."
        openssl enc -aes-256-cbc -d -pbkdf2 \
            -in "$input_file" \
            -out "$output_file" \
            -pass pass:"$ENCRYPTION_KEY"
        
        if [[ $? -ne 0 ]]; then
            log "ERROR: Decryption failed"
            exit 1
        fi
        
        echo "$output_file"
    else
        echo "$input_file"
    fi
}

# Decompress backup
decompress_backup() {
    local input_file="$1"
    local output_file="${input_file%.gz}"
    
    if [[ "$input_file" == *.gz ]]; then
        log "Decompressing backup..."
        gunzip -c "$input_file" > "$output_file"
        
        if [[ $? -ne 0 ]]; then
            log "ERROR: Decompression failed"
            exit 1
        fi
        
        echo "$output_file"
    else
        echo "$input_file"
    fi
}

# Perform restore
perform_restore() {
    local sql_file="$1"
    
    log "Starting database restore from: $sql_file"
    
    # Verify database exists and is accessible
    log "Testing database connection..."
    PGPASSWORD="${POSTGRES_PASSWORD}" psql \
        -h "$POSTGRES_HOST" \
        -p "$POSTGRES_PORT" \
        -U "$POSTGRES_USER" \
        -d "$POSTGRES_DB" \
        -c "SELECT 1;" > /dev/null
    
    if [[ $? -ne 0 ]]; then
        log "ERROR: Cannot connect to database"
        exit 1
    fi
    
    # Terminate existing connections
    log "Terminating existing connections..."
    PGPASSWORD="${POSTGRES_PASSWORD}" psql \
        -h "$POSTGRES_HOST" \
        -p "$POSTGRES_PORT" \
        -U "$POSTGRES_USER" \
        -d "$POSTGRES_DB" \
        -c "
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = '$POSTGRES_DB'
            AND pid <> pg_backend_pid();"
    
    # Drop and recreate database
    log "Dropping and recreating database..."
    PGPASSWORD="${POSTGRES_PASSWORD}" psql \
        -h "$POSTGRES_HOST" \
        -p "$POSTGRES_PORT" \
        -U "$POSTGRES_USER" \
        -d "postgres" \
        -c "DROP DATABASE IF EXISTS $POSTGRES_DB;"
    
    PGPASSWORD="${POSTGRES_PASSWORD}" psql \
        -h "$POSTGRES_HOST" \
        -p "$POSTGRES_PORT" \
        -U "$POSTGRES_USER" \
        -d "postgres" \
        -c "CREATE DATABASE $POSTGRES_DB OWNER $POSTGRES_USER;"
    
    # Restore from SQL dump
    log "Restoring database from dump..."
    PGPASSWORD="${POSTGRES_PASSWORD}" psql \
        -h "$POSTGRES_HOST" \
        -p "$POSTGRES_PORT" \
        -U "$POSTGRES_USER" \
        -d "$POSTGRES_DB" \
        -f "$sql_file" \
        --quiet
    
    if [[ $? -ne 0 ]]; then
        log "ERROR: Restore failed"
        exit 1
    fi
    
    log "Database restore completed successfully"
    
    # Run migrations to ensure schema is up to date
    log "Running migrations..."
    PGPASSWORD="${POSTGRES_PASSWORD}" psql \
        -h "$POSTGRES_HOST" \
        -p "$POSTGRES_PORT" \
        -U "$POSTGRES_USER" \
        -d "$POSTGRES_DB" \
        -c "SELECT version FROM alembic_version;" || true
}

# Main
main() {
    local list_only=false
    local download=false
    local force=false
    local backup_arg=""
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -l|--list)
                list_only=true
                shift
                ;;
            -d|--download)
                download=true
                shift
                ;;
            -f|--force)
                force=true
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            -*)
                log "ERROR: Unknown option: $1"
                usage
                exit 1
                ;;
            *)
                backup_arg="$1"
                shift
                ;;
        esac
    done
    
    check_tools
    
    if [[ "$list_only" == true ]]; then
        list_backups
        exit 0
    fi
    
    if [[ -z "$backup_arg" ]]; then
        log "ERROR: Backup file or timestamp required"
        usage
        exit 1
    fi
    
    # Find backup file
    local backup_file
    backup_file=$(find_backup "$backup_arg")
    
    if [[ -z "$backup_file" ]]; then
        log "ERROR: Backup not found for: $backup_arg"
        list_backups
        exit 1
    fi
    
    # Download from S3 if requested
    if [[ "$download" == true && "$backup_file" == s3://* ]]; then
        backup_file=$(download_backup "$backup_file")
    elif [[ "$backup_file" == s3://* ]]; then
        log "ERROR: Backup is in S3. Use --download flag to download first."
        exit 1
    fi
    
    # Confirm restore
    if [[ "$force" != true ]]; then
        echo "WARNING: This will DESTROY the current database '$POSTGRES_DB' and restore from backup."
        echo "Backup file: $backup_file"
        read -p "Are you sure you want to continue? (yes/no): " confirm
        if [[ "$confirm" != "yes" ]]; then
            log "Restore cancelled by user"
            exit 0
        fi
    fi
    
    # Decrypt if needed
    backup_file=$(decrypt_backup "$backup_file")
    
    # Decompress
    local sql_file
    sql_file=$(decompress_backup "$backup_file")
    
    # Perform restore
    perform_restore "$sql_file"
    
    # Cleanup temp files
    if [[ "$sql_file" != "$backup_arg" ]]; then
        rm -f "$sql_file"
    fi
    
    log "Restore completed successfully!"
}

main "$@"