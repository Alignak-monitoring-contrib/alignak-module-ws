.. raw:: LaTeX

    \newpage

.. _host_livestate:

Host event
==========

Host event
~~~~~~~~~~
To send an host/service comment, POST on the `event` endpoint providing the host/service name and the required comment.

The result is a JSON object containing a `_status` property that should be 'OK' and a `_result` array property that contains information about the actions that were executed.

If an error is detected, the `_status` property is not 'OK' and a `_issues` array property will report the detected error(s).

Adding a comment for an host
::

    $ curl --request POST \
      --url http://demo.alignak.net:8888/event \
      --header 'authorization: Basic MTQ4NDU1ODM2NjkyMi1iY2Y3Y2NmMS03MjM4LTQ4N2ItYWJkOS0zMGNlZDdlNDI2ZmI6' \
      --header 'cache-control: no-cache' \
      --header 'content-type: application/json' \
      --data '
      {
         "host": "test_host",
         "comment": "My host comment"
      }'

    # JSON result
    {"_status": "OK", "_result": ["ADD_HOST_COMMENT;test_host;1;Alignak WS;My host comment"]}

Adding a comment for a service
::

    $ curl --request POST \
      --url http://demo.alignak.net:8888/event \
      --header 'authorization: Basic MTQ4NDU1ODM2NjkyMi1iY2Y3Y2NmMS03MjM4LTQ4N2ItYWJkOS0zMGNlZDdlNDI2ZmI6' \
      --header 'cache-control: no-cache' \
      --header 'content-type: application/json' \
      --data '
      {
         "host": "test_host",
         "service": "test_service",
         "comment": "My comment"
      }'

    # JSON result
    {"_status": "OK", "_result": ["ADD_SVC_COMMENT;test_host;test_service;1;Alignak WS;My comment"]}

If `author` is not specified in the posted data, "Alignak WS" will be used as the author of the comment.
If `timestamp` is not specified in the posted data, the comment will be timestamped with the current date/time.
