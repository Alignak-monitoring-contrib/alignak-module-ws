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

    * `GET /` will return the list of the available endpoints

    * `GET /alignak_map` that will return the map and status of all the Alignak running daemons

    * `POST /alignak_command` that will notify an external command to the Alignak framework

    * `PATCH /host/<host_name>` that allows to send live state for an host and its services, update host custom variables, enable/disable host checks


Web Services
------------

Get Alignak state
~~~~~~~~~~~~~~~~~
To get Alignak daemons states, GET on the `alignak_map` endpoint:
::

    $ wget http://demo.alignak.net:8888/alignak_map

    $ cat alignak_map
    {

        "reactionner": {
            .../...
        },
        "broker": {
            .../...
        },
        "arbiter": {
            "arbiter-master": {
                "passive": false,
                "polling_interval": 1,
                "alive": true,
                "realm_name": "",
                "manage_sub_realms": false,
                "is_sent": false,
                "spare": false,
                "check_interval": 60,
                "address": "127.0.0.1",
                "manage_arbiters": false,
                "reachable": true,
                "max_check_attempts": 3,
                "last_check": 0,
                "port": 7770
            }
        },
        "scheduler": {
            .../...
        },
        "receiver": {
            .../...
        },
        "poller": {
            .../...
        }

    }

The state of the all the Alignak running daemons is returned in a JSON object formatted as the former example. each daemon type contains an object for each daemon instance with the daemon configuration and live state.



Get Alignak history
~~~~~~~~~~~~~~~~~~~
To get Alignak history, GET on the `alignak_logs` endpoint:
::

    $ wget http://demo.alignak.net:8888/alignak_logs

    $ cat alignak_logs
    {
        "_status": "OK",
        "items": [
            {
                "service_name": "Zombies",
                "host_name": "chazay",
                "user_name": "Alignak",
                "_created": "Sun, 12 Mar 2017 19:14:48 GMT",
                "message": "",
                "type": "check.result"
            },
            {
                "service_name": "Users",
                "host_name": "denice",
                "user_name": "Alignak",
                "_created": "Sun, 12 Mar 2017 19:14:40 GMT",
                "message": "",
                "type": "check.result"
            },
            {
                "service_name": "Zombies",
                "host_name": "alignak_glpi",
                "user_name": "Alignak",
                "_created": "Sun, 12 Mar 2017 19:14:37 GMT",
                "message": "",
                "type": "check.result"
            },
            {
                "service_name": "Processus",
                "host_name": "lachassagne",
                "user_name": "Alignak",
                "_created": "Sun, 12 Mar 2017 19:14:18 GMT",
                "message": "",
                "type": "check.result"
            },
            .../...
        ]
    }

The result is a JSON object containing a `_status` property that should be 'OK' and an `items` array property that contain the 25 most recent history events stored in the backend. Each item in this array has the properties:

    - _created: GMT date of the event creation in the backend
    - host_name / service_name
    - user_name: Alignak for Alignak self-generated events, else web UI user that provoked the event
    - message: for an Alignak check result, this will contain the main check result information: state[state_type] (acknowledged/downtimed): output (eg. UP[HARD] (False/False): Check output)
    - type is the event type:
        # WebUI user comment
        "webui.comment",

        # Check result
        "check.result",

        # Request to force a check (from WebUI)
        "check.request",
        "check.requested",

        # Add acknowledge (from WebUI)
        "ack.add",
        # Set acknowledge
        "ack.processed",
        # Delete acknowledge
        "ack.delete",

        # Add downtime (from WebUI)
        "downtime.add",
        # Set downtime
        "downtime.processed",
        # Delete downtime
        "downtime.delete"

        # timeperiod transition
        "monitoring.timeperiod_transition",
        # alert
        "monitoring.alert",
        # event handler
        "monitoring.event_handler",
        # flapping start / stop
        "monitoring.flapping_start",
        "monitoring.flapping_stop",
        # downtime start / cancel / end
        "monitoring.downtime_start",
        "monitoring.downtime_cancelled",
        "monitoring.downtime_end",
        # acknowledge
        "monitoring.acknowledge",
        # notification
        "monitoring.notification",


Some parameters can be used to refine the results:

    - count: number of elements to get (default=25). According to the Alignak backend pagination, the maximu number of elements taht can be returned is 50.
    - page: page number (default=0). With the default count (25 items), page=0 returns the items from 0 to 24, page=1 returns the items from 25 to 49, ...
    - search: search criteria in the items fields. The search criteria is using the same search engin as the one implemented in the WebUI.
        `host_name:pattern`, search for pattern in the host_name field (pattern can be a regex)
        `service_name:pattern`, search for pattern in the host_name field (pattern can be a regex)
        `user_name:pattern`, search for pattern in the host_name field (pattern can be a regex)

        `type:monitoring-alert`, search for all events that have the `monitoring.alert` type

        several search criterias can be used simultaneously. Simply separate them with a space character:
            `host_name:pattern type:monitoring-alert``
        (To be completed...)



**Note** that the returned items are always sorted to get the most recent first


Host/service livestate
~~~~~~~~~~~~~~~~~~~~~~
To send an host/service live state, PATCH on the `host` endpoint providing the host name and its state:
::

    $ curl -X POST -H "Content-Type: application/json" -d '{
        "host_name": "test_host",
        "livestate": {
            "state": "up",
            "output": "Output...",
            "long_output": "Long output...",
            "perf_data": "'counter':1"
        }
    }' "http://demo.alignak.net:8888/host"


The result is a JSON object containing a `_status` property that should be 'OK' and an `_result` array property that contains information about the actions that were executed.

If an error is detected, the `_status` property is not 'OK' and a `_issues` array property will report the detected error(s).

The `/host/host_name` can be used to target the host. If a `name` property is present in the JSON data then this property will take precedence over the `host_name` in the endpoint.

**Note** that the returned items are always sorted to get the most recent first


Host custom variables
~~~~~~~~~~~~~~~~~~~~~
To create/update host custom variables, PATCH on the `host` endpoint providing the host name and its variables:
::

    $ curl -X POST -H "Content-Type: application/json" -d '{
        "host_name": "test_host",
         "name": "_dummy",
         "variables": {
             'test1': 'string',
             'test2': 12,
             'test3': 15055.0,
             'test4': "new!"
         }
    }' "http://demo.alignak.net:8888/host"


The result is a JSON object containing a `_status` property that should be 'OK' and an `_result` array property that contains information about the actions that were executed.

If an error is detected, the `_status` property is not 'OK' and a `_issues` array property will report the detected error(s).

The `/host/host_name` can be used to target the host. If a `name` property is present in the JSON data then this property will take precedence over the `host_name` in the endpoint.

**Note** that the returned items are always sorted to get the most recent first


Host enable/disable checks
~~~~~~~~~~~~~~~~~~~~~~~~~~
To enable/disable an host checks, PATCH on the `host` endpoint providing the host name and its checks configuration:
::

    $ curl -X POST -H "Content-Type: application/json" -d '{
        "host_name": "test_host",
        "active_checks_enabled": True,
        "passive_checks_enabled": True
    }' "http://demo.alignak.net:8888/host"


The result is a JSON object containing a `_status` property that should be 'OK' and an `_result` array property that contains information about the actions that were executed.

If an error is detected, the `_status` property is not 'OK' and a `_issues` array property will report the detected error(s).

The `/host/host_name` can be used to target the host. If a `name` property is present in the JSON data then this property will take precedence over the `host_name` in the endpoint.

**Note** that the returned items are always sorted to get the most recent first


Send external command
~~~~~~~~~~~~~~~~~~~~~
To send an external command, JSON post on the `command` endpoint.

For a global Alignak command:
::

    # Disable all notifications from Alignak
    $ curl -X POST -H "Content-Type: application/json" -d '{
        "command": "disable_notifications"
    }' "http://demo.alignak.net:8888/command"

    {"_status": "ok", "_result": "DISABLE_NOTIFICATIONS"}

    # Enable all notifications from Alignak
    $ curl -X POST -H "Content-Type: application/json" -d '{
        "command": "enable_notifications"
    }' "http://demo.alignak.net:8888/command"

    {"_status": "ok", "_result": "ENABLE_NOTIFICATIONS"}

If your command requires to target a specific element:
::

    # Notify a host check result for `always_down` host
    $ curl -X POST -H "Content-Type: application/json" -d '{
        "command": "PROCESS_HOST_CHECK_RESULT",
        "element": "always_down",
        "parameters": "0;Host is UP and running"
    }' "http://demo.alignak.net:8888/command"

    {"_status": "ok", "_result": "PROCESS_HOST_CHECK_RESULT;always_down;0;Host is UP and running"}

    # Notify a service check result for `always_down/Load` host
    $ curl -X POST -H "Content-Type: application/json" -d '{
        "command": "PROCESS_SERVICE_CHECK_RESULT",
        "element": "always_down/Load",
        "parameters": "0;Service is OK|'My metric=12%:80:90:0:100"
    }' "http://demo.alignak.net:8888/command"

    {"_status": "ok", "_result": "PROCESS_SERVICE_CHECK_RESULT;always_down/Load;0;Service is OK"}

    # Notify a service check result for `always_down/Load` host (Alignak syntax)
    $ curl -X POST -H "Content-Type: application/json" -d '{
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
    $ curl -X POST -H "Content-Type: application/json" -d '{
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

To configure an Alignak daemon (*receiver* is the recommended daemon) to use this module:

    - edit your daemon configuration file (eg. *receiver-master.cfg*)
    - add your module alias value (`web-services`) to the `modules` parameter of the daemon

**Note** that currently the SSL part of this module as not yet been tested!


Bugs, issues and contributing
-----------------------------

Contributions to this project are welcome and encouraged ... `issues in the project repository <https://github.com/alignak-monitoring-contrib/alignak-module-ws/issues>`_ are the common way to raise an information.
