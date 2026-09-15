================================
Development: make kat on Windows
================================

This manual helps you to install and run OpenKAT on your Windows with the use of WSL2.

Follow these steps
===================

The installation is easy if you just follow these steps.

Step 1: Install WSL
--------------------

WSL (Windows Subsystem for Linux) allows you to run Linux commands from your Windows operating system. This example uses Debian, but this could also be another Linux distribution, such as Ubuntu.

- Open PowerShell as administrator
- Run:

.. code-block:: sh

    $ wsl --install debian

- (Or run the following command and then search in the Microsoft Store for 'Debian' and install it.)

.. code-block:: sh

    $ wsl --install

Step 2: Preparation
--------------------

Now it's time to prepare your system.

- Make sure Docker is installed, updated and running
- Check the settings of Docker
  - Settings -> General: "Enable the WSL 2 based engine" should be checked.
  - Settings -> Resources -> WSL Integration: Make sure your subsystem is checked.
  - Settings -> Docker Engine: Increase the defaultKeepStorage (to e.g. 50GB).
  - If you have changed anything, click "Apply & Restart".
- Make sure nothing is running on port 5432

Step 3: Open your Linux subsystem
----------------------------------

- In PowerShell, run:

.. code-block:: sh

    $ debian

- Leave this screen open, you'll need it in the next steps.

Step 4: Clone nl-kat-coordination
----------------------------------

Clone the repository of OpenKAT into your WSL. It is important that you do it in WSL and not in Windows!

- In your Debian PowerShell, run:

.. code-block:: sh

    $ sudo apt install git
    $ git clone https://github.com/minvws/nl-kat-coordination.git
    $ cd nl-kat-coordination

Step 5: Open the code in Visual Studio Code
--------------------------------------------

To do this, VS Code must already be installed on your Windows and you must have the WSL plugin installed in VS Code.

- In your Debian PowerShell, run:

.. code-block:: sh

    $ code .

Doing this from the nl-kat-coordination folder on your WSL will open VS Code.

Step 6: Complete the .env file
-------------------------------

If you go to the ``.env`` file in the code, you should see that the passwords don't have a value yet. To fix this, run the following command.

- In your Debian PowerShell, run:

.. code-block:: sh

    $ make env

This will complete the .env file.

Step 7: Start OpenKAT
----------------------

Now you can start OpenKat.
- In your Debian PowerShell, run:

.. code-block:: sh

    $ make kat

- Go to `http://localhost:8000` and follow the onboarding.
- Once you are through the onboarding, check that all of OpenKAT's services are running properly using the "Health" link at the right side of the footer (http://localhost:8000/nl/{organization_id}/health/v1).

Troubleshooting
================

If you encounter any problems, please check :doc:`/installation-and-deployment/index` for more information.
