=======================
Installing OpenKAT
=======================

This guide will help you get a working OpenKAT setup.

Before you start
================

You need:

- at least 50GB of disk space (OpenKAT installation is ~25-30GB)


Installation steps
==================

This guide gives you two ways to install OpenKAT:

- Automatic installation using a script - for Debian/Ubuntu
- Manual installation - for all distributions



Automatic installation using a script (Debian/Ubuntu)
-----------------------------------------------------

Download the Debian installation script and give it executable rights.

.. code-block:: sh

    curl -O https://raw.githubusercontent.com/SSC-ICT-Innovatie/nl-kat-coordination/refs/heads/main/scripts/installation/openkat-install.sh
    chmod 755 openkat-install.sh

Now execute the installation script.
The installation script will prompt for an e-mailaddress and password. You need these to sign in once the installation is complete.

.. code-block:: sh

    ./openkat-install.sh

Grab a tea while you pet your cat. Once it is finished you can reach the OpenKAT interface at

    http://localhost:8000


You should see a login prompt. You can now continue with the next section <LINK>.


Manual installation via Github
------------------------------

This installation can be used for other Linux distributions, and/or MacOS and Windows systems.

Docker installation
*******************

Do **not** install Docker directly from the default Ubuntu/Debian repositories. This version is older and OpenKAT generally uses newer features. This will likely break your OpenKAT installation.

#. Follow the Docker installation steps as mentioned here: `Docker Ubuntu Installation steps <https://docs.docker.com/engine/install/ubuntu/#installation-methods>`_. This tutorial followed the installation steps using the `apt` repository. Make sure that you can run the `hello-world` Docker image.

#. Follow the post-installations steps as described here: `Docker post-installation steps <https://docs.docker.com/engine/install/linux-postinstall/#manage-docker-as-a-non-root-user>`_. Make sure that the Docker `hello-world` image can run as a normal (non-root) user.


OpenKAT installation
********************

Make sure you have the following packages installed:

.. code-block:: sh

    sudo apt install gcc g++ make python3-pip curl git


Next clone the OpenKAT repository to a folder of your choice:

.. code-block:: sh

    git clone https://github.com/SSC-ICT-Innovatie/nl-kat-coordination.git

Now change into this directory:

.. code-block:: sh

    cd nl-kat-coordination

Run the following commands to prepare your environment and then build the latest stable OpenKAT release version.

.. code-block:: sh

    make env
    make last-release

Grab a tea while you pet your cat. Once it is finished you can reach the OpenKAT interface at

    http://localhost:8000
