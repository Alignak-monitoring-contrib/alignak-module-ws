.. raw:: LaTeX

    \newpage

.. _02_installation:

Installation
============

Requirements
------------


To use this module, you first need to install some Python modules that are listed in the ``requirements.txt`` file:

    .. literalinclude:: ../../../requirements.txt

**Note**: if you proceed to an end-user installation with pip, the required modules are automatically installed.

Installation with PIP
---------------------

**Note** that the recommended way for installing on a production server is mostly often to use the packages existing for your distribution. Nevertheless, the pip installation provides a startup script using an uwsgi server and, for FreeBSD users, rc.d scripts.

End user installation
~~~~~~~~~~~~~~~~~~~~~

You can install with pip::

    sudo pip install alignak-module-ws

The required Python modules are automatically installed if not they are not yet present on your system.


From source
~~~~~~~~~~~

You can install it from source::

    git clone https://github.com/Alignak-monitoring/alignak-module-ws
    cd alignak-module-ws
    pip install .
