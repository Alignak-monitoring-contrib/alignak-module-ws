.. raw:: LaTeX

    \newpage

.. _authorization:

HTTP authorization
==================

As a default, all the WS endpoints require the client to provide some credentials. You can provide those credentials directly in the HTTP Authorization header or you can use the `/login` and `/logout` endpoints to create a WS session.


To provide the credentials you can use the token delivered by the Alignak backend when you are logging-in. If you do not have this information, you can provide your ``username`` and ``password`` to authenticate near the Alignak backend.
::

    $ curl -H "Content-Type: application/json" -X POST -d '{"username":"admin","password":"admin"}' http://127.0.0.1:8888/login
    {'_status': 'OK', '_result': ["1442583814636-bed32565-2ff7-4023-87fb-34a3ac93d34c"]}

Logging out will clear the session on the server side.
::

    $ curl -H "Content-Type: application/json" -X GET http://127.0.0.1:8888/logout

Example 1 (direct credentials provided):
::

    $ curl -X GET -H "Content-Type: application/json" --user "1442583814636-bed32565-2ff7-4023-87fb-34a3ac93d34c:" http://127.0.0.1:8888/alignak_logs


Example 2 (login session):
::

    $ curl -H "Content-Type: application/json" -X POST -d '{"username":"admin","password":"admin"}' http://127.0.0.1:8888/login
    {'_status': 'OK', '_result': ["1442583814636-bed32565-2ff7-4023-87fb-34a3ac93d34c"]}

    $ curl -X GET -H "Content-Type: application/json" --user "1442583814636-bed32565-2ff7-4023-87fb-34a3ac93d34c:" http://127.0.0.1:8888/alignak_logs


**Note** that using the login / logout session is an easy thing with a python library like requests with its session mechanism ;) Or with any client that handles sessions ...
