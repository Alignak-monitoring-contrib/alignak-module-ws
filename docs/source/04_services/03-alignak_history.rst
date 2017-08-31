.. raw:: LaTeX

    \newpage

.. _alignak_history:

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
