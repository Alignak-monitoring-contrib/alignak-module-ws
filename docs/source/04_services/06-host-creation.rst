.. raw:: LaTeX

    \newpage

.. _host_creation:

Hosts / services creation
=========================

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


