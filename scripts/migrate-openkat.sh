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
      echo "Unknown argument: $1"
      exit 1
      ;;
  esac
done

echo "DRY RUN: $DRY_RUN"
echo "BACKUP PATH: $BACKUP_PATH"
echo "COMPOSE FILE: $COMPOSE_FILE"
echo "REMOVE OLD VOLUMES: $REMOVE_OLD_VOLUMES"
echo "--------------------------------------"

# Helper
run_or_echo() {
  if $DRY_RUN; then
    echo "[DRY RUN] $*"
  else
    eval "$@"
  fi
}

# ---- Step 1: Stop & remove old containers ----
echo "Stopping and removing old containers..."
for cid in $(docker ps -a --filter "name=nl-kat-coordination-" --format '{{.ID}}'); do
  run_or_echo "docker stop $cid"
  run_or_echo "docker rm $cid"
done

# ---- Step 2: Migrate volumes ----
echo "Migrating volumes..."

for old_vol in $(docker volume ls --format '{{.Name}}' | grep '^nl-kat-coordination_'); do
  rest="${old_vol#nl-kat-coordination_}"
  new_vol="openkat_${rest}"

  echo "-----------------------------------------"
  echo "Volume Migration:"
  echo "  OLD: $old_vol"
  echo "  NEW: $new_vol"

  # Ensure backup directory exists
  run_or_echo "mkdir -p \"$BACKUP_PATH/$old_vol\""

  # Find backup file
  latest_backup=$(ls -1 "$BACKUP_PATH/$old_vol"/*.tar.gz 2>/dev/null | sort | tail -n 1 || true)
  if [[ -z "$latest_backup" ]]; then
    echo "ERROR: No backup found for $old_vol"
    continue
  fi

  echo "  Latest backup: $latest_backup"

  # In dry-run, we skip actual backup and restore
  if $DRY_RUN; then
    continue
  fi

  # Backup old volume
  timestamp="$(date +%Y-%m-%d_%H%M%S)"
  backup_file="${BACKUP_PATH}/${old_vol}/${timestamp}_${old_vol}.tar.gz"

  echo "  Backing up to: $backup_file"

  docker run --rm \
    --mount "type=volume,src=${old_vol},dst=/data" \
    "$IMAGE" \
    sh -c "cd /data && tar -czf /backup.tar.gz ."

  # Copy out of container
  container_id=$(docker ps -a --filter ancestor="$IMAGE" --format '{{.ID}}' | head -n 1)
  docker cp "${container_id}:/backup.tar.gz" "${backup_file}"
  docker rm "${container_id}"

  # Create new volume
  docker volume create "$new_vol"

  # Restore into new volume
  echo "  Restoring into new volume: $new_vol"

  docker run --rm \
    --mount "type=volume,src=$new_vol,dst=/data" \
    --mount "type=bind,src=$(dirname "$backup_file"),dst=/backup,ro" \
    "$IMAGE" \
    sh -c "cd /data && tar -xzf /backup/$(basename "$backup_file")"

  echo "  RESTORE COMPLETE: $new_vol"
done

# ---- Step 3: Remove old volumes (optional) ----
if $REMOVE_OLD_VOLUMES; then
  echo "Removing old volumes..."
  for old_vol in $(docker volume ls --format '{{.Name}}' | grep '^nl-kat-coordination_'); do
    run_or_echo "docker volume rm \"$old_vol\""
  done
fi

# ---- Step 4: Start new stack ----
echo "Starting new docker-compose stack..."
run_or_echo "docker-compose -f \"$COMPOSE_FILE\" up -d"
