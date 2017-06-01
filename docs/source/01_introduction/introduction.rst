.. _introduction/introduction:


===========================
Alignak Web Services module
===========================

This module for Alignak exposes some Alignak Web Services:

    * `GET /` will return the list of the available endpoints

    * `GET /alignak_map` that will return the map and status of all the Alignak running daemons

    * `POST /alignak_command` that will notify an external command to the Alignak framework

    * `PATCH /host/<host_name>` that allows to send live state for an host and its services, update host custom variables, enable/disable host checks
One line/s