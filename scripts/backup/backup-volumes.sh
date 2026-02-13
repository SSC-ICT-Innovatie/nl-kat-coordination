#!/usr/bin/env bash
set -eu
# creates a backup of the docker volume

while [ $# -gt 0 ]; do
    case "$1" in
    -p | --path)
        backup_path="$2"
        ;;
    -h | -help | --help)
        printf -- "--path  path where the backups are stored\n"
        exit 1
        ;;
    *)
        printf "*******************************\n"
        printf "* Error: Invalid argument: %s *\n" "$1"
        printf "*******************************\n"
        exit 1
        ;;
    esac
    shift
    shift
done

for volume in $(docker volume ls --filter name=openkat* --quiet); do
    uuid="$(cat /proc/sys/kernel/random/uuid)"
    if [ ! -d "$backup_path/$volume" ]; then
        mkdir -p "$backup_path/$volume"
    fi

    IMAGE=alpine:latest
    docker run \
        --mount "type=volume,src=${volume},dst=/data" \
        --name "$uuid" \
        "$IMAGE"

    timestamp="$(date +%Y-%m-%d_%H%M%S)"
    docker cp -a "$uuid:/data" "/tmp/$uuid"
    tar -C "/tmp/$uuid" -czf "$backup_path/$volume/${timestamp}_${volume}.tar.gz" .
    rm -rf "/tmp/$uuid"
    docker rm "$uuid"
done
