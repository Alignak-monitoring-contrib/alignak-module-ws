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


Configuration
-------------

Once installed, this module has its own configuration file in the */usr/local/etc/alignak/arbiter/modules* directory.
The default configuration file is *mod-ws.cfg*. This file is commented to help configure all the parameters.

To configure an Alignak daemon (*receiver* is the recommended daemon) to use this module:

    - edit your daemon configuration file (eg. *receiver-master.cfg*)
    - add your module alias value (`web-services`) to the `modules` parameter of the daemon

**Note** that currently the SSL part of this module has not yet been tested!

HTTP authorization
~~~~~~~~~~~~~~~~~~
As a default, all the WS endpoints require the client to provide some credentials. You can provide those credentials directly in the HTTP Authorization header or you can use the `/login` and `/logout` endpoints to create a WS session.

To provide the credentials you can use the token delivered by the Alignak backend when you are logging-in.

Example 1 (direct credentials provided):
::

    $ curl -X GET -H "Content-Type: application/json" --user "1442583814636-bed32565-2ff7-4023-87fb-34a3ac93d34c:" http://127.0.0.1:8888/alignak_logs


Example 2 (login session):
::

    $ curl -H "Content-Type: application/json" -X POST -d '{"username":"admin","password":"admin"}' http://127.0.0.1:8888/login
    {'_status': 'OK', '_result': ["1442583814636-bed32565-2ff7-4023-87fb-34a3ac93d34c"]}

    $ curl -X GET -H "Content-Type: application/json" --user "1442583814636-bed32565-2ff7-4023-87fb-34a3ac93d34c:" http://127.0.0.1:8888/alignak_logs


**Note** that using the login / logout session is an easy thing with a python library like requests with its session mechanism ;) Or with any client that handles sessions ...


Alignak backend
~~~~~~~~~~~~~~~
The Alignak backend configuration part requires to set the Alignak backend endpoint and some login information. The login information are not mandatory because the module will use the credentials provided by the Web Service client when one will request on an endpoint with some credentials.

Alignak arbiter
~~~~~~~~~~~~~~~
The Alignak arbiter configuration part is not mandatory. It will only be used by the module to get the Alignak daemons states to populate the `/alignak_map` endpoint. §Thus, you should only configure this part if you intend to use this endpoint to get some information.


Web Services
------------

Login / logout
~~~~~~~~~~~~~~
To create a session near the Web Services server, POST on the `/login` endpoint and provide your ``username`` and ``password`` to authenticate near the Alignak backend.
::

    $ curl -H "Content-Type: application/json" -X POST -d '{"username":"admin","password":"admin"}' http://127.0.0.1:8888/login
    {'_status': 'OK', '_result': ["1442583814636-bed32565-2ff7-4023-87fb-34a3ac93d34c"]}

Logging out will clear the session on the server side.
::

    $ curl -H "Content-Type: application/json" -X GET http://127.0.0.1:8888/logout


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

    $ curl --request PATCH \
      --url http://demo.alignak.net:8888/host \
      --header 'authorization: Basic MTQ4NDU1ODM2NjkyMi1iY2Y3Y2NmMS03MjM4LTQ4N2ItYWJkOS0zMGNlZDdlNDI2ZmI6' \
      --header 'cache-control: no-cache' \
      --header 'content-type: application/json' \
      --data '
      {
        "name": "passive-01",
        "variables": {
            "test": "test"
        },
        "active_checks_enabled": false,
        "passive_checks_enabled": true,
        "livestate": {
            "state": "UP",
            "output": "WS output - active checks disabled"
        },
        "services": {
            "first": {
                "name": "dev_BarcodeReader",
                "active_checks_enabled": false,
                "passive_checks_enabled": true,
                "livestate": {
                    "state": "OK",
                    "output": "WS output - I am ok!"
                }
            }
        }
    }'

    # JSON result
    {
      "_status": "OK",
      "_result": [
        "passive-01 is alive :)",
        "[1491368659] PROCESS_HOST_CHECK_RESULT;passive-01;0;WS output - active checks disabled",
        "[1491368659] PROCESS_SERVICE_CHECK_RESULT;passive-01;dev_BarcodeReader;0;WS output - I am ok!",
        "Service 'passive-01/dev_BarcodeReader' unchanged.",
        "Host 'passive-01' unchanged."
      ],
      "_feedback": {
        "passive_checks_enabled": true,
        "active_checks_enabled": false,
        "alias": "Passive host 1",
        "freshness_state": "d",
        "notes": "",
        "retry_interval": 0,
        "_overall_state_id": 4,
        "freshness_threshold": 14400,
        "location": {
          "type": "Point",
          "coordinates": [
            46.60611,
            1.87528
          ]
        },
        "check_interval": 5,
        "services": {
          "first": {
            "active_checks_enabled": false,
            "freshness_threshold": 43200,
            "_overall_state_id": 1,
            "freshness_state": "x",
            "notes": "",
            "retry_interval": 0,
            "alias": "Barcode reader",
            "passive_checks_enabled": true,
            "check_interval": 0,
            "max_check_attempts": 1,
            "check_freshness": true
          }
        },
        "max_check_attempts": 1,
        "check_freshness": true
      }
    }


The result is a JSON object containing a `_status` property that should be 'OK' and a `_result` array property that contains information about the actions that were executed. A `_feedback` dictionary property provides some informatyion about the host/service.

If an error is detected, the `_status` property is not 'OK' and a `_issues` array property will report the detected error(s).

The `/host/host_name` can be used to target the host. If a `name` property is present in the JSON data then this property will take precedence over the `host_name` in the endpoint.

For the host services states, use the same syntax as for an host:
::

    $ curl -X PATCH -H "Content-Type: application/json" -d '{
        "name": "test_host",
        "livestate": {
            "state": "up",
            "output": "Output...",
            "long_output": "Long output...",
            "perf_data": "'counter'=1"
        },
        "services": {
            "test_service": {
                "name": "test_service",
                "livestate": {
                    "state": "ok",
                    "output": "Output...",
                    "long_output": "Long output...",
                    "perf_data": "'counter'=1"
                }
            },
            "test_service2": {
                "name": "test_service2",
                "livestate": {
                    "state": "warning",
                    "output": "Output...",
                    "long_output": "Long output...",
                    "perf_data": "'counter'=2"
                }
            },
            "test_service3": {
                "name": "test_service3",
                "livestate": {
                    "state": "critical",
                    "output": "Output...",
                    "long_output": "Long output...",
                    "perf_data": "'counter'=3"
                }
            },
        }
    }' "http://demo.alignak.net:8888/host"


The livestate data for an host or service may contain:
- `state`: "ok","warning","critical","unknown","unreachable" for a service. "up","down","unreachable" for an host.
- `output`: the host/service check output
- `long_output`: the host/service long output (second part of tha output)
- `perf_data`: the host/service check performance data
- `timestamp`: timestamp for the host/service check


Host custom variables
~~~~~~~~~~~~~~~~~~~~~
To create/update host custom variables, PATCH on the `host` endpoint providing the host name and its variables:
::

    $ curl -X PATCH -H "Content-Type: application/json" -d '{
        "name": "test_host",
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
To enable/disable hosts/services checks, PATCH on the `host` endpoint providing the host (service) name and its checks configuration:
::

    $ curl -X PATCH -H "Content-Type: application/json" -d '{
        "name": "test_host",
        "active_checks_enabled": True,
        "passive_checks_enabled": True,
        "services": {
            "test_service": {
                "name": "test_ok_0",
                "active_checks_enabled": True,
                "passive_checks_enabled": True,
            },
            "test_service2": {
                "name": "test_ok_1",
                "active_checks_enabled": False,
                "passive_checks_enabled": False,
            },
            "test_service3": {
                "name": "test_ok_2",
                "active_checks_enabled": True,
                "passive_checks_enabled": False,
            },
        }
    }' "http://demo.alignak.net:8888/host"


The result is a JSON object containing a `_status` property that should be 'OK' and an `_result` array property that contains information about the actions that were executed.

If an error is detected, the `_status` property is not 'OK' and a `_issues` array property will report the detected error(s).

The `/host/host_name` can be used to target the host. If a `name` property is present in the JSON data then this property will take precedence over the `host_name` in the endpoint.


Host/service creation
~~~~~~~~~~~~~~~~~~~~~
If the configuration parameters `allow_host_creation` and `allow_service_creation` are set in the module configuration file, hosts and services may be created when patching the `/host` endpoint.

Each time that the `/host` endpoint is patched, the module will check if the concerned host/services exist in the Alignak backend. If they do not exist, they will be created.

Some data may be provided for the creation in the `template` property. If no template data are provided, the host/service will be created with the default values defined in the backend. The host/service properties managed in the backend are described in the `backend documentation<http://docs.alignak.net/projects/alignak-backend/en/develop/resources/confighost.html>`_.

To create hosts/services, PATCH on the `host` endpoint providing the host (service) data in the `template` property:
::

    $ curl -X PATCH -H "Content-Type: application/json" -d '{
        "name": "test_host",
        "template": {
            "alias": "My host...",
            "_templates": ["generic-host", "important"]
        },
        "services": {
            "test_service": {
                "name": "test_ok_0",
                "template": {
                    "alias": "My service...",
                    "_templates": ["generic-service", "normal"]
                },
            }
        }
    }' "http://demo.alignak.net:8888/host"




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

Bugs, issues and contributing
-----------------------------

Contributions to this project are welcome and encouraged ... `issues in the project repository <https://github.com/alignak-monitoring-contrib/alignak-module-ws/issues>`_ are the common way to raise an information.
