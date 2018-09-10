.. raw:: LaTeX

    \newpage

.. _host_creation:

Hosts / services creation
=========================

If the configuration parameters `allow_host_creation` and `allow_service_creation` are set in the module configuration file, hosts and services may be created when patching (or posting) the `/host` endpoint.

Each time that the `/host` endpoint is patched (or posted), the module will check if the concerned host/services exist in the Alignak backend. If they do not exist, they will be created.

*Note* that it is recommended to use the HTTP PATCH verb. In a REST API, PATCH is used to update only some information of an object whereas POST is used to create a new object. However, some firewall/gateway equipments do not easily allow using the HTTP verb PATCH. This is why, the Alignak Web Service listener allows to POST on the /hot endpoint.

Some data may be provided for the host/service creation in the `template` property. If no template data are provided, the host/service will be created with the default values defined in the backend. The host/service properties managed in the backend and their default values are described in the `backend documentation<http://docs.alignak.net/projects/alignak-backend/en/develop/resources/confighost.html>`_.

The main interesting data that may be used in the `template` property are the `alias`, `_realm` and `_templates` to use for the item creation.

The `alias` is a friendly name tht can be used in the Alignak Web UI instead of the host/service name.

The `_realm` is the name of the realm in which the host will be referenced. If the provided `_realm` is not found in the Alignak backend, the host will be attached to the default *All* realm. Note that the provided realm name can be uppercased, lowercased or capitalized by the Web Service module according to its configuration (see the configuration parameter `realm_case`).

The `_templates` property is the list of the hosts templates to get used for the host creation. The backend templates mechanism is explained in the Alignak backend documentation. The main idea is that a template allows to pre-define all the host properties and services that will be used for a host creation... as suche it make sit easy and simple to create a new host with only one property: its template(s) list!

To create hosts/services, PATCH (or POST) on the `host` endpoint providing the host (service) creation data in the `template` property:
::

    $ curl -X PATCH -H "Content-Type: application/json" -d '{
        "name": "test_host",
        "template": {
            "alias": "My host...",
            "_realm": "My realm",
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


