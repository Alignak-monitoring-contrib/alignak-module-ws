Alignak Web services Module
===========================

*Alignak Web services module*

Build status (stable release)
-----------------------------

.. image:: https://travis-ci.org/Alignak-monitoring-contrib/alignak-module-ws.svg?branch=master
    :target: https://travis-ci.org/Alignak-monitoring-contrib/alignak-module-ws
    :alt: Unit tests

.. image:: https://coveralls.io/repos/Alignak-monitoring-contrib/alignak-module-ws/badge.svg?branch=master&service=github
    :target: https://coveralls.io/github/Alignak-monitoring-contrib/alignak-module-ws?branch=master
    :alt: Code coverage


Build status (development release)
----------------------------------

.. image:: https://travis-ci.org/Alignak-monitoring-contrib/alignak-module-ws.svg?branch=develop
    :target: https://travis-ci.org/Alignak-monitoring-contrib/alignak-module-ws
    :alt: Unit tests

.. image:: https://coveralls.io/repos/Alignak-monitoring-contrib/alignak-module-ws/badge.svg?branch=develop&service=github
    :target: https://coveralls.io/github/Alignak-monitoring-contrib/alignak-module-ws?branch=master
    :alt: Code coverage

Most recent release
-------------------

.. image:: https://badge.fury.io/py/alignak_module_ws.svg
    :target: https://badge.fury.io/py/alignak_module_ws


Short description
-----------------

This module for Alignak exposes some Alignak Web Services:

    * GET /alignak_map that will return the map and status of all the Alignak running daemons

    * POST /alignak_command that will notify an external command to the Alignak framework



Installation
------------

From PyPI
~~~~~~~~~
To install the module from PyPI:
::

    pip install alignak-module-web-services


From source files
~~~~~~~~~~~~~~~~~
To install the module from the source files:
::

    git clone https://github.com/Alignak-monitoring-contrib/alignak-module-ws
    cd alignak-module-ws
    pip install -r requirements
    python setup.py install


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

Please report any issue using the project `GitHub repository: <https://github.com/Alignak-monitoring-contrib/alignak-module-ws/issues>`_.

License
-------

Alignak Module External commands is available under the `GPL version 3 license`_.

.. _GPL version 3 license: http://opensource.org/licenses/GPL-3.0
.. _Alignak monitoring contrib: https://github.com/Alignak-monitoring-contrib
.. _PyPI repository: <https://pypi.python.org/pypi>
