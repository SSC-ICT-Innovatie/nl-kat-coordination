Scripts
=======

There are some scripts in the `scripts/installation
<https://github.com/minvws/nl-kat-coordination/tree/main/scripts/installation>`__ directory
that can be used to install and update OpenKAT on Debian and will do all the
steps described on the :ref:`debian-install` page.

Installation
------------

The `openkat-install.sh
<https://raw.githubusercontent.com/minvws/nl-kat-coordination/main/scripts/installation/openkat-install.sh>`__
script installs OpenKAT. Change the permissions on the file to 755:

``chmod 755 openkat-install.sh``

usage:
``./openkat-install.sh [OpenKAT version] [no_super_user]``

Parameters:
 * openKAT version: optional parameter, e.g. 1.10.0. If not supplied latest version is used.
 * no_super_user: optional parameter used for re-installs and won't create superuser account

Example for initial install of KAT version 1.10.0 (including creatng the super user):

``./openkat-install.sh 1.10.0``

and re-installing KAT version 1.10.0rc1 without super user account:

``./openkat-_install.sh 1.10.0rc1 no_super_user``

Update
-------

The `openkat-update.sh
<https://raw.githubusercontent.com/minvws/nl-kat-coordination/main/scripts/installation/openkat-update.sh>`__
script updates OpenKAT. Change the permissions on the file to 755:

``chmod 755 openkat-update.sh``

Usage:

``./openkat-update.sh [openKAT version]``

Parameters:
 * openKAT version: optional parameter, e.g. 1.10.0. If not supplied latest version is used.

Example to update a previous openKAT installation to version 1.10.0:

``./openkat-update.sh 1.10.0``

Status and logs
---------------

`openkat-status.sh
<https://raw.githubusercontent.com/minvws/nl-kat-coordination/main/scripts/installation/openkat-status.sh>`__
shows you the status of all OpenKAT related processes from systemctl.

`openkat-show-journal.sh
<https://raw.githubusercontent.com/minvws/nl-kat-coordination/main/scripts/installation/openkat-show-journal.sh>`__
shows the journalctl -n of all OpenKAT related processes.

Starting, stopping, restarting
------------------------------

`openkat-start.sh
<https://raw.githubusercontent.com/minvws/nl-kat-coordination/main/scripts/installation/openkat-start.sh>`__
starts all OpenKAT processes.

`openkat-stop.sh
<https://raw.githubusercontent.com/minvws/nl-kat-coordination/main/scripts/installation/openkat-stop.sh>`__
stops all OpenKAT processes.

`openkat-restart.sh
<https://raw.githubusercontent.com/minvws/nl-kat-coordination/main/scripts/installation/openkat-restart.sh>`__
restarts all OpenKAT processes.

Empty queue
-----------

`openkat-empty-job-queue.sh
<https://raw.githubusercontent.com/minvws/nl-kat-coordination/main/scripts/installation/openkat-empty-job-queue.sh>`__
stops your OpenKAT processes, empties the job queue and starts all processes.

Backup
------

TobiasBDO contributed `two backup and restore scripts <https://github.com/tobiasBDO/backup-openkat/tree/master>`_ included as part of his answer to `the question how to backup XTDB <https://github.com/minvws/nl-kat-coordination/issues/1757>`_ properly.

We have slightly adjusted the scripts to prevent some potential issues from occurring (globbing and word splitting: shellcheck SC2086) and to clear some things up in the code. These scripts are maintained on a ‘best effort’ basis, thus no guarantees are provided. You are responsible for your own backups, OpenKAT is not responsible nor liable in case your backups are broken.

Below is a description on how these backup scripts can be used.

How to backup your volume
-------------------------

In your OpenKAT directory go to the ``scripts/backup`` folder:

``$ cd scripts/backup``

Make the script executable:

``$ sudo chmod +x backup-volumes.sh``

Run the backup script with root rights. The -p parameter specifies the folder where your backup files will be stored. If this folder doesn't exist yet, it will automatically be created. Change <backup_path> to a descriptive backup name. The full path for this folder will be: ``/<path_to_OpenKAT_files>/scripts/backup/<backup_path>``.

Optionally, use the -n parameter to specify the docker compose project name. This is used to filter which volumes to backup. If not specified, it defaults to the ``COMPOSE_PROJECT_NAME`` environment variable or the current directory name (matching docker compose behavior).

Run the script with the chosen backup path:

``$ sudo ./backup-volumes.sh -p <backup_path>``

Or with an explicit project name:

``$ sudo ./backup-volumes.sh -p <backup_path> -n <project_name>``

This directory will contain multiple folders each containing the backup file for that specific docker container as archived files (.tar.gz). If you run the command again it will create new archived files into those subdirectories. Your old backup will remain, as each backup name contains the timestamp of moment of creation. An example of such a file is: ``2024-03-28_173258_nl-kat-coordination_bytes-data.tar.gz``.

Restoring your docker volume
----------------------------

In your OpenKAT directory go to the ``scripts/backup`` folder:

``$ cd scripts/backup``

Make the script executable:

``$ sudo chmod +x restore-volumes.sh``

Volumes can be restored by specifying the volume container name and the backup path folder from the previous step. If multiple backup files are available the script will automatically restore from the **newest** snapshot.

Restore a backup volume:

``$ sudo ./restore-volumes.sh -v <volume_name> -p <prefix>``

Optionally if you wish to create a volume with a different name from the backup the script can be invoked in the following manner:

``$ sudo ./restore-volumes.sh -v <volume_name> -p <prefix> -n <new_volume_name>``

Example
-------

Create a backup: ::

 $ sudo ./backup-volumes.sh -p MyOrganisation
 [sudo] password for user:
 Successfully copied 40.8MB to /tmp/a3b27680-02e4-49cd-a155-e2729d8e7b70
 a3b27680-02e4-49cd-a155-e2729d8e7b70
 Successfully copied 1.54kB to /tmp/1f879ea3-c6ec-49e1-814e-863a2c0eeff1
 1f879ea3-c6ec-49e1-814e-863a2c0eeff1
 Successfully copied 103MB to /tmp/b8c048f9-d43a-4aeb-b479-ee7f9288f8c8
 b8c048f9-d43a-4aeb-b479-ee7f9288f8c8
 Successfully copied 426MB to /tmp/6bdfdc41-973b-4cf9-a107-ad4f03b5ed3f
 6bdfdc41-973b-4cf9-a107-ad4f03b5ed3f


The contents of the folder MyOrganisation are: ::

 $ ls -lah MyOrganisation/
 total 24K
 drwxr-xr-x 6 root root 4,0K apr  3 14:27 .
 drwxrwxr-x 4 user user 4,0K apr  3 14:27 ..
 drwxr-xr-x 2 root root 4,0K apr  3 14:27 nl-kat-coordination_bytes-data
 drwxr-xr-x 2 root root 4,0K apr  3 14:27 nl-kat-coordination_postgres-data
 drwxr-xr-x 2 root root 4,0K apr  3 14:27 nl-kat-coordination_xtdb-data

Restoring then works as follows: ::

 $ ./restore-volumes.sh -v nl-kat-coordination_bytes-data -p MyOrganisation
 creating from snapshot: 2024-04-03_142729_nl-kat-coordination_bytes-data.tar.gz
 Successfully copied 40.8MB to fafd7168-7b17-45e7-a41c-dee9e97c948a:/data
 fafd7168-7b17-45e7-a41c-dee9e97c948a
