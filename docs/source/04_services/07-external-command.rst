.. raw:: LaTeX

    \newpage

.. _external_commands:

External commands
=================

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
