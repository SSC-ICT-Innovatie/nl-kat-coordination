===========
Quick start
===========

Installation
************
This quick start guides will help you to get OpenKAT started on Ubuntu using the Docker setup. The steps below were performed on a clean Ubuntu 22.04 LTS virtual machine. This quick start assumes you have a working Ubuntu installation ready. Please note that these steps help you to setup a playground/developer environment for OpenKAT, this means you should not use it as a production environment. If you do, you do so at your own risk.

Do *not* install Docker directly from the default Ubuntu repositories. This version is older and OpenKAT generally uses newer features. Using the Ubuntu repository version will likely break your OpenKAT install (at some point).


#. Follow the Docker installation steps as mentioned here: `Docker Ubuntu Installation steps <https://docs.docker.com/engine/install/ubuntu/#installation-methods>`_. This tutorial followed the installation steps using the `apt` repository. Make sure that you can run the `hello-world` Docker image.

#. Follow the post-installations steps as described here: `Docker post-installation steps <https://docs.docker.com/engine/install/linux-postinstall/#manage-docker-as-a-non-root-user>`_. Make sure that the Docker `hello-world` image can run as a normal (non-root) user.

#. Install missing Ubuntu packages.

.. code-block:: sh

    sudo apt install make
..

#. Decide if you want to install the latest stable version of OpenKAT or if you want to run `main`. Clone the OpenKAT repository to a location of your choice as shown below.

.. code-block:: sh

    $ git clone https://github.com/SSC-ICT-Innovatie/nl-kat-coordination.git
..

#. Change into the cloned repository.

.. code-block:: sh

    $ cd nl-kat-coordination/
..

#. Create the environment file and run kat.

.. code-block:: sh

    $ make env
    $ make kat
..

#. Pet your cat while you wait for all the containers to be built.

#. Get your password from the `.env` file. An example of what this looks like is shown below.

.. code-block:: sh

    $ cat .env | grep DJANGO
    DJANGO_SUPERUSER_PASSWORD=83d0ddac75c3fed23d2fc3a607affe432f9916d0f9dcc12680
..

#. Open your browser and go to: `http://localhost:8000/en/login`. Login using the username `superuser@localhost` and the password you found using the previous step (everything after the equal sign `=`).

#. Meowlations! You just installed OpenKAT. As this is your first time using OpenKAT, you will have to walk through the onboarding. This is explained in the user manual: :doc:`../../user-manual/getting-started/onboarding`
