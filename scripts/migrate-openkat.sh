#!/usr/bin/env bash
set -euo pipefail

PROJECT_NAME="nl-kat-coordination"
BACKUP_PATH="/tmp/openkatbackups"
IMAGE="alpine:latest"
COMPOSE_FILE="docker-compose.yml"

DRY_RUN=false
REMOVE_OLD_VOLUMES=false
CLEANUP_ONLY=false

# ---- CLI parsing ----
while [[ $# -gt 0 ]]; do
    case "$1" in
    --dry-run)
        DRY_RUN=true
        shift
        ;;
    --project)
        PROJECT_NAME="$2"
        shift 2
        ;;
    --remove-old-volumes)
        REMOVE_OLD_VOLUMES=true
        shift
        ;;
    --cleanup-only)
        CLEANUP_ONLY=true
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

printf 'Usage: %s \n' "$(basename "$0")"
printf ' --dry-run, DRY RUN: %s\n' "$DRY_RUN"
printf ' --project, docker compose project name: %s\n' "$PROJECT_NAME"
printf "           (default: \$COMPOSE_PROJECT_NAME or current directory name)\n"
printf ' --backup-path, BACKUP PATH: %s\n' "$BACKUP_PATH"
printf ' --compose-file, COMPOSE FILE: %s\n' "$COMPOSE_FILE"
printf ' --remove-old-volumes, REMOVE OLD VOLUMES: %s\n' "$REMOVE_OLD_VOLUMES"
printf ' --cleanup-only, CLEANUP ONLY: %s\n' "$CLEANUP_ONLY"
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

# Determine project name for docker volume filtering.
# Mirrors docker compose behavior: env var, then current directory name.
if [ -z "${PROJECT_NAME:-}" ]; then
    PROJECT_NAME="${COMPOSE_PROJECT_NAME:-$(basename "$(pwd)")}"
fi

if ! "$CLEANUP_ONLY"; then
    # ---- Step 1: Stop & remove old containers ----
    printf 'Stopping and removing old containers...\n'

    if ! "$DRY_RUN"; then
        docker compose -p "$PROJECT_NAME" down
    fi

    # ---- Step 2: Migrate volumes ----
    printf 'Migrating volumes...\n'

    docker volume ls -q --filter "name=${PROJECT_NAME}_" |
        while IFS= read -r old_vol; do
            rest="${old_vol#"${PROJECT_NAME}"_}"
            new_vol="openkat_${rest}"

            printf '-----------------------------------------\n'
            printf 'Volume Migration:\n'
            printf '  OLD: %s\n' "$old_vol"
            printf '  NEW: %s\n' "$new_vol"

            # Ensure backup directory exists
            run_or_echo mkdir -p "$BACKUP_PATH/$old_vol"

            # In dry-run, only create a backup file
            timestamp="$(date +%Y-%m-%d_%H%M%S)"
            backup_file="${BACKUP_PATH}/${old_vol}/${timestamp}_${old_vol}.tar.gz"

            printf '  Backing up to: %s\n' "$backup_file"

            if ! "$DRY_RUN"; then
                docker run --rm \
                    --mount "type=volume,src=${old_vol},dst=/data" \
                    --mount "type=bind,src=$(dirname "$backup_file"),dst=/backup" \
                    "$IMAGE" \
                    sh -c "cd /data && tar -czf /backup/$(basename "$backup_file") ."

                # create volume, if not exists
                if ! docker volume inspect "$new_vol" > /dev/null 2>&1; then
                    docker volume create "$new_vol"
                fi

                printf '  Restoring into new volume: %s\n' "$new_vol"

                docker run --rm \
                    --mount "type=volume,src=${new_vol},dst=/data" \
                    --mount "type=bind,src=$(dirname "$backup_file"),dst=/backup,ro" \
                    "$IMAGE" \
                    sh -c "cd /data && tar -xzf /backup/$(basename "$backup_file")"

                printf '  RESTORE COMPLETE: %s\n' "$new_vol"
            fi
        done

    if "$DRY_RUN"; then
        printf '  Restart your containers using the old names manually.\n'
    fi
fi

# ---- Step 3: Remove old volumes (optional) ----
if "$REMOVE_OLD_VOLUMES"; then
    printf 'Removing old volumes...\n'

    docker volume ls -q --filter "name=${PROJECT_NAME}_" |
        while IFS= read -r old_vol; do
            run_or_echo docker volume rm "$old_vol"
        done
fi

# ---- Step 4: Start new stack ----
if ! "$CLEANUP_ONLY"; then
    printf 'Starting new docker-compose stack...\n'
    run_or_echo docker compose -f "$COMPOSE_FILE" up -d
fi
