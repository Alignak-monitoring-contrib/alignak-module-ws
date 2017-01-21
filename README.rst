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

    * GET /alignak_map that will return the map and status of all the Alignak running daemons

    * POST /alignak_command that will notify an external command to the Alignak framework


Web Services
------------

Get Alignak state
~~~~~~~~~~~~~~~~~
To get Alignak daemons states, GET on the `alignak_map` endpoint:
::

    $wget http://demo.alignak.net:8888/alignak_map

    $cat alignak_map


Send external command
~~~~~~~~~~~~~~~~~~~~~
To send an external command, JSON post on the `command` endpoint.

For a global Alignak command:
::

    # Disable all notifications from Alignak
    $curl -X POST -H "Content-Type: application/json" -d '{
        "command": "disable_notifications"
    }' "http://demo.alignak.net:8888/command"

    {"_status": "ok", "_result": "DISABLE_NOTIFICATIONS"}

    # Enable all notifications from Alignak
    $curl -X POST -H "Content-Type: application/json" -d '{
        "command": "enable_notifications"
    }' "http://demo.alignak.net:8888/command"

    {"_status": "ok", "_result": "ENABLE_NOTIFICATIONS"}

If your command requires to target a specific element:
::

    # Notify a host check result for `always_down` host
    $curl -X POST -H "Content-Type: application/json" -d '{
        "command": "PROCESS_HOST_CHECK_RESULT",
        "element": "always_down",
        "parameters": "0;Host is UP and running"
    }' "http://demo.alignak.net:8888/command"

    {"_status": "ok", "_result": "PROCESS_HOST_CHECK_RESULT;always_down;0;Host is UP and running"}

    # Notify a service check result for `always_down/Load` host
    $curl -X POST -H "Content-Type: application/json" -d '{
        "command": "PROCESS_SERVICE_CHECK_RESULT",
        "element": "always_down/Load",
        "parameters": "0;Service is OK|'My metric=12%:80:90:0:100"
    }' "http://demo.alignak.net:8888/command"

    {"_status": "ok", "_result": "PROCESS_SERVICE_CHECK_RESULT;always_down/Load;0;Service is OK"}

    # Notify a service check result for `always_down/Load` host (Alignak syntax)
    $curl -X POST -H "Content-Type: application/json" -d '{
        "command": "PROCESS_SERVICE_CHECK_RESULT",
        "host": "always_down",
        "service": "Load",
        "parameters": "0;Service is OK|'My metric=12%:80:90:0:100"
    }' "http://demo.alignak.net:8888/command"

    {"_status": "ok", "_result": "PROCESS_SERVICE_CHECK_RESULT;always_down/Load;0;Service is OK"}

**Note:** the `element` parameter is the old fashioned Nagios way to target an element and you can target a service with `host;service` syntax or with `host/service` syntax. Alignak recommands to use the `host`, `service` or `user` parameters in place of `element` !

**Note:** a timestamp (integer or float) can also be provided. If it does not exist, Alignak will use the time it receives the command as a timestamp. Specify a `timestamp` parameter if you want to set a specific one for the command
::

    # Notify a host check result for `always_down` host at a specific time stamp
    $curl -X POST -H "Content-Type: application/json" -d '{
        "timestamp": "1484992154",
        "command": "PROCESS_HOST_CHECK_RESULT",
        "element": "always_down",
        "parameters": "0;Host is UP and running"
    }' "http://demo.alignak.net:8888/command"

    {"_status": "ok", "_result": "PROCESS_HOST_CHECK_RESULT;always_down;0;Host is UP and running"}


**Note:** for the available external commands, see the `Alignak documentation chapter on the external commands <http://alignak-doc.readthedocs.io/en/latest/20_annexes/external_commands_list.html>`_.

Configuration
-------------

Once installed, this module has its own configuration file in the */usr/local/etc/alignak/arbiter/modules* directory.
The default configuration file is *mod-ws.cfg*. This file is commented to help configure all the parameters.

To configure an Alignak daemon to use this module:

    - edit your daemon configuration file
    - add your module alias value (`web-services`) to the `modules` parameter of the daemon

**Note** that currently the SSL part of this module as not yet been tested!


Bugs, issues and contributing
-----------------------------

Contributions to this project are welcome and encouraged ... `issues in the project repository <https://github.com/alignak-monitoring-contrib/alignak-module-ws/issues>`_ are the common way to raise an information.
