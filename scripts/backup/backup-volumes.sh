#!/usr/bin/env bash
set -eu
# creates a backup of the docker volumes

generate_uuid() {
    if command -v uuidgen > /dev/null 2>&1; then
        uuidgen
    elif [ -f /proc/sys/kernel/random/uuid ]; then
        cat /proc/sys/kernel/random/uuid
    else
        printf "Error: no UUID generator found\n" >&2
        exit 1
    fi
}

usage() {
    printf "Usage: %s -p <path> [-n <project-name>]\n" "$(basename "$0")"
    printf "  -p | --path       path where the backups are stored\n"
    printf "  -n | --project    docker compose project name\n"
    printf "                    (default: \$COMPOSE_PROJECT_NAME or current directory name)\n"
    exit 0
}

while [ $# -gt 0 ]; do
    case "$1" in
    -p | --path)
        backup_path="$2"
        shift
        ;;
    -n | --project)
        project_name="$2"
        shift
        ;;
    -h | -help | --help)
        usage
        ;;
    *)
        printf "*******************************\n"
        printf "* Error: Invalid argument: %s *\n" "$1"
        printf "*******************************\n"
        exit 1
        ;;
    esac
    shift
done

if [ -z "${backup_path:-}" ]; then
    printf "Error: --path is required\n" >&2
    exit 1
fi

# Determine project name for docker volume filtering.
# Mirrors docker compose behavior: env var, then current directory name.
if [ -z "${project_name:-}" ]; then
    project_name="${COMPOSE_PROJECT_NAME:-$(basename "$(pwd)")}"
fi

volumes="$(docker volume ls --filter "name=${project_name}_" --quiet)"

if [ -z "$volumes" ]; then
    printf "No volumes found for project '%s'\n" "$project_name"
    exit 0
fi

for volume in $volumes; do
    uuid="$(generate_uuid)"
    if [ ! -d "$backup_path/$volume" ]; then
        mkdir -p "$backup_path/$volume"
    fi

    IMAGE=alpine:latest
    docker create \
        --mount "type=volume,src=${volume},dst=/data" \
        --name "$uuid" \
        "$IMAGE"

    # Clean up container on failure
    trap 'rm -rf "/tmp/$uuid"; docker rm "$uuid" >/dev/null 2>&1' EXIT

    timestamp="$(date +%Y-%m-%d_%H%M%S)"
    docker cp -a "$uuid:/data" "/tmp/$uuid"
    tar -C "/tmp/$uuid" -czf "$backup_path/$volume/${timestamp}_${volume}.tar.gz" .
    rm -rf "/tmp/$uuid"
    docker rm "$uuid"

    trap - EXIT
done
