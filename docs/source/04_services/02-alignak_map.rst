.. raw:: LaTeX

    \newpage

.. _alignak_map:

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

