# OpenKAT Migration Tool

This tool migrates Docker volumes from the **old OpenKAT naming scheme** to the **new OpenKAT naming scheme**, while creating backups and starting the new stack.

---

## Table of Contents

1. [Purpose](#purpose)  
2. [Prerequisites](#prerequisites)  
3. [Usage](#usage)  
4. [Options](#options)  
5. [Migration Flow](#migration-flow)  
6. [Cleanup Only Mode](#cleanup-only-mode)  
7. [Recommended Workflow](#recommended-workflow)  
8. [Safety Notes](#safety-notes)

---

## Purpose

The script performs the following tasks:

- Stops and removes old containers (`nl-kat-coordination-*`)
- Backs up old volumes to `.tar.gz` files
- Creates new volumes (`openkat_*`)
- Restores backups into new volumes
- Optionally removes old volumes
- Starts the new OpenKAT Docker Compose stack

---

## Prerequisites

Before running the script, ensure:

- Docker is installed and running
- Docker Compose v2 (`docker compose`) is installed
- The old OpenKAT stack is present and running (volumes exist)
- You have sufficient disk space for backups
- The new `docker-compose.yml` is available

---

## Usage

`./migrate-openkat.sh`

This performs a full migration, creates backups but does not remove the old volumes.

---

## Options

| Option                   | Description                                                           |
| ------------------------ | --------------------------------------------------------------------- |
| `--dry-run`              | Show what will happen without making changes                          |
| `--backup-path <path>`   | Directory to store backups (default: `/tmp/openkatbackups`)           |
| `--compose-file <path>`  | Docker Compose file for the new stack (default: `docker-compose.yml`) |
| `--cleanup-only`         | Skip migration; only remove old volumes                               |
| `--remove-old-volumes`   | Remove legacy volumes after migration                                 |

---

## Migration Flow

When run normally, the script performs:

### Step 1 — Stop & Remove Old Containers

All containers matching:

`nl-kat-coordination-*`

are stopped and removed.

---

### Step 2 — Migrate Volumes

For each volume matching:

`nl-kat-coordination_*`

The script:

1. Creates a backup directory:
   `<backup-path>/nl-kat-coordination_<service>`

2. Backs up old volume into:
   `<backup-path>/nl-kat-coordination_<service>/<timestamp>_nl-kat-coordination_<service>.tar.gz`

3. Creates a new volume:
   `openkat_<service>`

4. Restores the backup into the new volume

---

### Step 3 — Remove Old Volumes

If `--remove-old-volumes` was specified, old volumes have already been deleted,
if not, use the `--clean-up-only` mode to finish migration later.

---

### Step 4 — Start New Stack

The new OpenKAT stack is started:

`docker compose -f <compose-file> up -d`
or run `make up` from the root folder.

---

## Cleanup Only Mode

If you already completed migration and only want to delete old volumes, use:

`./migrate-openkat.sh --cleanup-only`

This skips migration and only removes legacy volumes.

---

## Recommended Workflow

### 1. Preview Migration (safe)

`./migrate-openkat.sh --dry-run`

### 2. Run Migration

`./migrate-openkat.sh --backup-path /var/backups/openkat`

### 3. Verify the new OpenKAT stack

`make up`

### 4. Remove old volumes (optional)

`./migrate-openkat.sh --cleanup-only`

---

## Safety Notes

- Backups are **never deleted automatically**
- Old volumes are removed only if explicitly requested
- Dry run mode is fully non-destructive
- The script exits on errors to avoid partial migrations
