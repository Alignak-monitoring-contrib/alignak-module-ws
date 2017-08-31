Alignak Web services Module
===========================

*Alignak Web services module*

.. image:: https://travis-ci.org/Alignak-monitoring-contrib/alignak-module-ws.svg?branch=develop
    :target: https://travis-ci.org/Alignak-monitoring-contrib/alignak-module-ws
    :alt: Develop branch build status

.. image:: https://landscape.io/github/Alignak-monitoring-contrib/alignak-module-ws/develop/landscape.svg?style=flat
    :target: https://landscape.io/github/Alignak-monitoring-contrib/alignak-module-ws/develop
    :alt: Development code static analysis

.. image:: https://coveralls.io/repos/Alignak-monitoring-contrib/alignak-module-ws/badge.svg?branch=develop
    :target: https://coveralls.io/r/Alignak-monitoring-contrib/alignak-module-ws
    :alt: Development code tests coverage

.. image:: https://readthedocs.org/projects/alignak-module-ws/badge/?version=develop
    :target: http://alignak-module-ws.readthedocs.io/en/develop/
    :alt: Development branch documentation Status

.. image:: https://badge.fury.io/py/alignak_module_ws.svg
    :target: https://badge.fury.io/py/alignak-module-ws
    :alt: Most recent PyPi version

.. image:: https://img.shields.io/badge/IRC-%23alignak-1e72ff.svg?style=flat
    :target: http://webchat.freenode.net/?channels=%23alignak
    :alt: Join the chat #alignak on freenode.net

.. image:: https://img.shields.io/badge/License-AGPL%20v3-blue.svg
    :target: http://www.gnu.org/licenses/agpl-3.0
    :alt: License AGPL v3

Installation
------------

The installation of this module will copy some configuration files in the Alignak default configuration directory (eg. */usr/local/etc/alignak*). The copied files are located in the default sub-directory used for the modules (eg. *arbiter/modules*).

From PyPI
~~~~~~~~~
To install the module from PyPI:
::

   sudo pip install alignak-module-ws


From source files
~~~~~~~~~~~~~~~~~
To install the module from the source files (for developing purpose):
::

   git clone https://github.com/Alignak-monitoring-contrib/alignak-module-ws
   cd alignak-module-ws
   sudo pip install . -e

**Note:** *using `sudo python setup.py install` will not correctly manage the package configuration files! The recommended way is really to use `pip`;)*


Short description
-----------------

This module for Alignak exposes some Alignak Web Services:

    * `GET /` will return the list of the available endpoints

    * `GET /alignak_map` that will return the map and status of all the Alignak running daemons

    * `POST /alignak_command` that will notify an external command to the Alignak framework

    * `PATCH /host/<host_name>` that allows to send live state for an host and its services, update host custom variables, enable/disable host checks


Configuration
-------------

Once installed, this module has its own configuration file in the */usr/local/etc/alignak/arbiter/modules* directory.
The default configuration file is *mod-ws.cfg*. This file is commented to help configure all the parameters.

To configure an Alignak daemon (*receiver* is the recommended daemon) to use this module:

    - edit your daemon configuration file (eg. *receiver-master.cfg*)
    - add your module alias value (`web-services`) to the `modules` parameter of the daemon

**Note** that currently the SSL part of this module has not yet been tested!

Documentation
-------------

Alignak Web Service module has `an online documentation page <http://alignak-module-ws.readthedocs.io/en/develop/>`_.

Click on one of the docs badges on this page to browse the documentation.


Bugs, issues and contributing
-----------------------------

Contributions to this project are welcome and encouraged ... `issues in the project repository <https://github.com/alignak-monitoring-contrib/alignak-module-ws/issues>`_ are the common way to raise an information.
