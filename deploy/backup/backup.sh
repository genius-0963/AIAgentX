#!/usr/bin/env bash
# Database backup script for AIAgentX
# Runs as a Kubernetes CronJob or standalone script

set -euo pipefail

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/backups}"
POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_DB="${POSTGRES_DB:-aiagentx}"
POSTGRES_USER="${POSTGRES_USER:-aiagentx}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
ENCRYPTION_KEY="${BACKUP_ENCRYPTION_KEY:-}"
S3_BUCKET="${BACKUP_S3_BUCKET:-}"
S3_PREFIX="${BACKUP_S3_PREFIX:-aiagentx/backups}"

TIMESTAMP=$(date -u +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/aiagentx_${TIMESTAMP}.sql"
COMPRESSED_FILE="${BACKUP_FILE}.gz"
ENCRYPTED_FILE="${COMPRESSED_FILE}.enc"

# Logging function
log() {
    echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] $*"
}

# Check required tools
check_tools() {
    for tool in pg_dump gzip; do
        if ! command -v $tool &> /dev/null; then
            log "ERROR: Required tool '$tool' not found"
            exit 1
        fi
    done
    
    if [[ -n "$ENCRYPTION_KEY" ]] && ! command -v openssl &> /dev/null; then
        log "ERROR: openssl required for encryption but not found"
        exit 1
    fi
    
    if [[ -n "$S3_BUCKET" ]] && ! command -v aws &> /dev/null; then
        log "ERROR: aws cli required for S3 upload but not found"
        exit 1
    fi
}

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Perform database dump
log "Starting database backup for $POSTGRES_DB on $POSTGRES_HOST:$POSTGRES_PORT"

PGPASSWORD="${POSTGRES_PASSWORD}" pg_dump \
    -h "$POSTGRES_HOST" \
    -p "$POSTGRES_PORT" \
    -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB" \
    --no-password \
    --verbose \
    --format=plain \
    --no-owner \
    --no-privileges \
    --column-inserts \
    > "$BACKUP_FILE"

if [[ $? -ne 0 ]]; then
    log "ERROR: pg_dump failed"
    exit 1
fi

log "Database dump completed: $BACKUP_FILE"

# Compress backup
log "Compressing backup..."
gzip -9 "$BACKUP_FILE"

if [[ $? -ne 0 ]]; then
    log "ERROR: Compression failed"
    exit 1
fi

log "Compression completed: $COMPRESSED_FILE"

# Encrypt if key provided
if [[ -n "$ENCRYPTION_KEY" ]]; then
    log "Encrypting backup..."
    openssl enc -aes-256-cbc -salt -pbkdf2 \
        -in "$COMPRESSED_FILE" \
        -out "$ENCRYPTED_FILE" \
        -pass pass:"$ENCRYPTION_KEY"
    
    if [[ $? -ne 0 ]]; then
        log "ERROR: Encryption failed"
        exit 1
    fi
    
    # Remove unencrypted file
    rm "$COMPRESSED_FILE"
    FINAL_FILE="$ENCRYPTED_FILE"
    log "Encryption completed: $ENCRYPTED_FILE"
else
    FINAL_FILE="$COMPRESSED_FILE"
fi

# Upload to S3 if configured
if [[ -n "$S3_BUCKET" ]]; then
    log "Uploading to S3: s3://$S3_BUCKET/$S3_PREFIX/$(basename "$FINAL_FILE")"
    aws s3 cp "$FINAL_FILE" "s3://$S3_BUCKET/$S3_PREFIX/$(basename "$FINAL_FILE")" \
        --storage-class STANDARD_IA
    
    if [[ $? -ne 0 ]]; then
        log "ERROR: S3 upload failed"
        exit 1
    fi
    
    log "S3 upload completed"
fi

# Cleanup old backups
log "Cleaning up backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -name "aiagentx_*.sql.gz*" -mtime +$RETENTION_DAYS -delete

# Also cleanup S3 if configured
if [[ -n "$S3_BUCKET" ]]; then
    aws s3 ls "s3://$S3_BUCKET/$S3_PREFIX/" | while read -r line; do
        FILE_DATE=$(echo "$line" | awk '{print $1}')
        FILE_NAME=$(echo "$line" | awk '{print $4}')
        
        if [[ "$FILE_NAME" =~ ^aiagentx_ ]]; then
            FILE_EPOCH=$(date -d "$FILE_DATE" +%s 2>/dev/null || date -j -f "%Y-%m-%d" "$FILE_DATE" +%s 2>/dev/null)
            CURRENT_EPOCH=$(date +%s)
            AGE_DAYS=$(( (CURRENT_EPOCH - FILE_EPOCH) / 86400 ))
            
            if [[ $AGE_DAYS -gt $RETENTION_DAYS ]]; then
                log "Deleting old S3 backup: $FILE_NAME"
                aws s3 rm "s3://$S3_BUCKET/$S3_PREFIX/$FILE_NAME"
            fi
        fi
    done
fi

log "Backup completed successfully: $FINAL_FILE"

# Output backup info for monitoring
echo "BACKUP_FILE=$(basename "$FINAL_FILE")"
echo "BACKUP_SIZE=$(stat -c%s "$FINAL_FILE" 2>/dev/null || stat -f%z "$FINAL_FILE")"
echo "BACKUP_TIMESTAMP=$TIMESTAMP"