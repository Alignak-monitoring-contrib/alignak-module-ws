.. raw:: LaTeX

    \newpage

.. _configuration:

Configuration
=============

Once installed, this module has its own configuration file in the */usr/local/etc/alignak/arbiter/modules* directory.
The default configuration file is *mod-ws.cfg*. This file is commented to help configure all the parameters.

To configure an Alignak daemon (*receiver* is the recommended daemon) to use this module:

    - edit your daemon configuration file (eg. *receiver-master.cfg*)
    - add your module alias value (`web-services`) to the `modules` parameter of the daemon

**Note** that currently the SSL part of this module has not yet been tested!


Alignak backend
~~~~~~~~~~~~~~~
The Alignak backend configuration part requires to set the Alignak backend endpoint and some login information. The login information are not mandatory because the module will use the credentials provided by the Web Service client when one will request on an endpoint with some credentials.

Alignak arbiter
~~~~~~~~~~~~~~~
The Alignak arbiter configuration part is not mandatory. It will only be used by the module to get the Alignak daemons states to populate the `/alignak_map` endpoint. Thus, you should only configure this part if you intend to use this endpoint to get some information.



The default ``mod-ws.cfg`` file:

    .. literalinclude:: ../../../alignak_module_ws/etc/arbiter/modules/mod-ws.cfg

