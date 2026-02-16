#!/usr/bin/env bash
# creates a docker volume from a backup
set -eu

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

# Cross-platform stat: get modification time in unix epoch seconds
get_mtime() {
    if stat --version > /dev/null 2>&1; then
        # GNU stat (Linux)
        stat --format="%Y" "$1"
    else
        # BSD stat (macOS)
        stat -f "%m" "$1"
    fi
}

usage() {
    printf "Usage: %s -v <volume> -p <path> [-n <volume-name>] [-s <snapshot>]\n" "$(basename "$0")"
    printf "  -v | --volume       the volume name in the backup\n"
    printf "  -n | --volume-name  (optional) create the restore as this new volume name\n"
    printf "  -p | --path         the storage path of the backup location\n"
    printf "  -s | --snapshot     the snapshot to restore\n"
    exit 0
}

while [ $# -gt 0 ]; do
    case "$1" in
    -v | -volume | --volume)
        volume="$2"
        shift
        ;;
    -p | -path | --path)
        backup_path="$2"
        shift
        ;;
    -n | -volume-name | --volume-name)
        volume_name="$2"
        shift
        ;;
    -s | -snapshot | --snapshot)
        snapshot="$2"
        shift
        ;;
    -h | -help | --help)
        usage
        ;;
    *)
        printf "***************************\n"
        printf "* Error: Invalid argument.*\n"
        printf "***************************\n"
        exit 1
        ;;
    esac
    shift
done

if [ -z "${volume:-}" ]; then
    printf "Error: --volume is required\n"
    exit 1
fi

if [ -z "${backup_path:-}" ]; then
    printf "Error: --path is required\n"
    exit 1
fi

if [ -z "${volume_name:-}" ]; then
    volume_name="$volume"
fi

if docker volume inspect "$volume_name" > /dev/null 2>&1; then
    printf "***********************************\n"
    printf "Error: volume %s exists. \n" "$volume_name"
    printf "Please delete before proceeding    \n"
    printf "***********************************\n"
    exit 1
fi

# If no snapshot is given, find the newest snapshot in the backup_path/volume
# Does not use ls in order to keep doing the correct thing even with special
# characters like newlines in the filenames.
if [ -z "${snapshot:-}" ]; then
    NEWEST=0
    for dirent in "${backup_path}/${volume}"/*; do
        # Get the modification time of the directory entry with stat in unix time
        MTIME="$(get_mtime "$dirent")"
        if [ "$MTIME" -gt "$NEWEST" ]; then
            NEWEST="$MTIME"
            snapshot="$dirent"
        fi
    done
    snapshot="$(basename "$snapshot")"
fi

if [ -z "${snapshot:-}" ]; then
    printf "**********************************\n"
    printf "* Error: Unable to find snapshot.*\n"
    printf "**********************************\n"
    exit 1
else
    echo "creating from snapshot: ${snapshot}"
fi

uuid="$(generate_uuid)"
dir="$(mktemp -d)"

# Clean up temp directory and container on exit
trap 'rm -rf "$dir"; docker rm "$uuid" >/dev/null 2>&1' EXIT

IMAGE=alpine:latest
docker create \
    --mount "type=volume,src=${volume_name},dst=/data" \
    --name "$uuid" \
    "$IMAGE"

tar -xf "$backup_path/$volume/$snapshot" -C "$dir"
docker cp -a "$dir/." "$uuid:/data"
