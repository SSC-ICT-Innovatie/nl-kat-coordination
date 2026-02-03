#!/usr/bin/env bash
set -euo pipefail

BACKUP_PATH="/tmp/openkatbackups"
IMAGE="alpine:latest"
COMPOSE_FILE="docker-compose.yml"

DRY_RUN=false
REMOVE_OLD_VOLUMES=false

# ---- CLI parsing ----
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --remove-old-volumes)
            REMOVE_OLD_VOLUMES=true
            shift
            ;;
        --backup-path)
            BACKUP_PATH="$2"
            shift 2
            ;;
        --compose-file)
            COMPOSE_FILE="$2"
            shift 2
            ;;
        *)
            printf 'Unknown argument: %s\n' "$1"
            exit 1
            ;;
    esac
done

printf 'DRY RUN: %s\n' "$DRY_RUN"
printf 'BACKUP PATH: %s\n' "$BACKUP_PATH"
printf 'COMPOSE FILE: %s\n' "$COMPOSE_FILE"
printf 'REMOVE OLD VOLUMES: %s\n' "$REMOVE_OLD_VOLUMES"
printf '--------------------------------------\n'

# ---- Helper ----
run_or_echo() {
    if "$DRY_RUN"; then
        printf '[DRY RUN] %q ' "$@"
        printf '\n'
    else
        "$@"
    fi
}

# ---- Step 1: Stop & remove old containers ----
printf 'Stopping and removing old containers...\n'

docker ps -a \
    --filter "name=nl-kat-coordination-" \
    --format '{{.ID}}' |
while IFS= read -r cid; do
    run_or_echo docker stop "$cid"
    run_or_echo docker rm "$cid"
done

# ---- Step 2: Migrate volumes ----
printf 'Migrating volumes...\n'

docker volume ls --format '{{.Name}}' |
{
    grep '^nl-kat-coordination_' || true
} |
while IFS= read -r old_vol; do
    rest="${old_vol#nl-kat-coordination_}"
    new_vol="openkat_${rest}"

    printf '-----------------------------------------\n'
    printf 'Volume Migration:\n'
    printf '  OLD: %s\n' "$old_vol"
    printf '  NEW: %s\n' "$new_vol"

    # Ensure backup directory exists
    run_or_echo mkdir -p "$BACKUP_PATH/$old_vol"

    # Find latest existing backup (lexicographically)
    latest_backup=$(
        find "$BACKUP_PATH/$old_vol" \
            -maxdepth 1 \
            -type f \
            -name '*.tar.gz' \
            -print0 2>/dev/null |
        sort -z |
        tail -z -n 1 |
        tr -d '\0'
    )

    if [[ -z "$latest_backup" && "$DRY_RUN" == false ]]; then
        printf 'ERROR: No existing backup found for %s\n' "$old_vol"
        continue
    fi

    if [[ -n "$latest_backup" ]]; then
        printf '  Latest backup: %s\n' "$latest_backup"
    fi

    # In dry-run, do not actually back up or restore
    if "$DRY_RUN"; then
        continue
    fi

    timestamp="$(date +%Y-%m-%d_%H%M%S)"
    backup_file="${BACKUP_PATH}/${old_vol}/${timestamp}_${old_vol}.tar.gz"

    printf '  Backing up to: %s\n' "$backup_file"

    docker run --rm \
        --mount "type=volume,src=${old_vol},dst=/data" \
        --mount "type=bind,src=$(dirname "$backup_file"),dst=/backup" \
        "$IMAGE" \
        sh -c "cd /data && tar -czf /backup/$(basename "$backup_file") ."

    run_or_echo docker volume create "$new_vol"

    printf '  Restoring into new volume: %s\n' "$new_vol"

    docker run --rm \
        --mount "type=volume,src=$new_vol,dst=/data" \
        --mount "type=bind,src=$(dirname "$backup_file"),dst=/backup,ro" \
        "$IMAGE" \
        sh -c "cd /data && tar -xzf /backup/$(basename "$backup_file")"

    printf '  RESTORE COMPLETE: %s\n' "$new_vol"
done

# ---- Step 3: Remove old volumes (optional) ----
if "$REMOVE_OLD_VOLUMES"; then
    printf 'Removing old volumes...\n'

    docker volume ls --format '{{.Name}}' |
    {
        grep '^nl-kat-coordination_' || true
    } |
    while IFS= read -r old_vol; do
        run_or_echo docker volume rm "$old_vol"
    done
fi

# ---- Step 4: Start new stack ----
printf 'Starting new docker-compose stack...\n'
run_or_echo docker compose -f "$COMPOSE_FILE" up -d
