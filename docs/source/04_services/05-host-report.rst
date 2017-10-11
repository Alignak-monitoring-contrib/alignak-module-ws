.. raw:: LaTeX

    \newpage

.. _host_livestate:

Hosts / services state report
=============================

Host/service livestate
~~~~~~~~~~~~~~~~~~~~~~
To send an host/service live state, PATCH on the `host` endpoint providing the host name and its state:
::

    $ curl --request PATCH \
      --url http://demo.alignak.net:8888/host \
      --header 'authorization: Basic MTQ4NDU1ODM2NjkyMi1iY2Y3Y2NmMS03MjM4LTQ4N2ItYWJkOS0zMGNlZDdlNDI2ZmI6' \
      --header 'cache-control: no-cache' \
      --header 'content-type: application/json' \
      --data '
      {
        "name": "passive-01",
        "variables": {
            "test": "test"
        },
        "active_checks_enabled": false,
        "passive_checks_enabled": true,
        "livestate": {
            "state": "UP",
            "output": "WS output - active checks disabled"
        },
        "services": {
            "first": {
                "name": "dev_BarcodeReader",
                "active_checks_enabled": false,
                "passive_checks_enabled": true,
                "livestate": {
                    "state": "OK",
                    "output": "WS output - I am ok!"
                }
            }
        }
    }'

    # JSON result
    {
      "_status": "OK",
      "_result": [
        "passive-01 is alive :)",
        "[1491368659] PROCESS_HOST_CHECK_RESULT;passive-01;0;WS output - active checks disabled",
        "[1491368659] PROCESS_SERVICE_CHECK_RESULT;passive-01;dev_BarcodeReader;0;WS output - I am ok!",
        "Service 'passive-01/dev_BarcodeReader' unchanged.",
        "Host 'passive-01' unchanged."
      ],
      "_feedback": {
        "passive_checks_enabled": true,
        "active_checks_enabled": false,
        "alias": "Passive host 1",
        "freshness_state": "d",
        "notes": "",
        "retry_interval": 0,
        "_overall_state_id": 4,
        "freshness_threshold": 14400,
        "location": {
          "type": "Point",
          "coordinates": [
            46.60611,
            1.87528
          ]
        },
        "check_interval": 5,
        "services": {
          "first": {
            "active_checks_enabled": false,
            "freshness_threshold": 43200,
            "_overall_state_id": 1,
            "freshness_state": "x",
            "notes": "",
            "retry_interval": 0,
            "alias": "Barcode reader",
            "passive_checks_enabled": true,
            "check_interval": 0,
            "max_check_attempts": 1,
            "check_freshness": true
          }
        },
        "max_check_attempts": 1,
        "check_freshness": true
      }
    }


The result is a JSON object containing a `_status` property that should be 'OK' and a `_result` array property that contains information about the actions that were executed. A `_feedback` dictionary property provides some informatyion about the host/service.

If an error is detected, the `_status` property is not 'OK' and a `_issues` array property will report the detected error(s).

The `/host/host_name` can be used to target the host. If a `name` property is present in the JSON data then this property will take precedence over the `host_name` in the endpoint.

For the host services states, use the same syntax as for an host:
::

    $ curl -X PATCH -H "Content-Type: application/json" -d '{
        "name": "test_host",
        "livestate": {
            "state": "up",
            "output": "Output...",
            "long_output": "Long output...",
            "perf_data": "'counter'=1"
        },
        "services": {
            "test_service": {
                "name": "test_service",
                "livestate": {
                    "state": "ok",
                    "output": "Output...",
                    "long_output": "Long output...",
                    "perf_data": "'counter'=1"
                }
            },
            "test_service2": {
                "name": "test_service2",
                "livestate": {
                    "state": "warning",
                    "output": "Output...",
                    "long_output": "Long output...",
                    "perf_data": "'counter'=2"
                }
            },
            "test_service3": {
                "name": "test_service3",
                "livestate": {
                    "state": "critical",
                    "output": "Output...",
                    "long_output": "Long output...",
                    "perf_data": "'counter'=3"
                }
            },
        }
    }' "http://demo.alignak.net:8888/host"


The livestate data for an host or service may contain:
- `state`: "ok","warning","critical","unknown","unreachable" for a service. "up","down","unreachable" for an host.
- `output`: the host/service check output
- `long_output`: the host/service long output (second part of the output)
- `perf_data`: the host/service check performance data
- `timestamp`: timestamp for the host/service check

**Note** that the `livestate` for the host or for any service may be an array if more than one result is to be reported to the Web Service.

Host custom variables
~~~~~~~~~~~~~~~~~~~~~
To create/update host custom variables, PATCH on the `host` endpoint providing the host name and its variables:
::

    $ curl -X PATCH -H "Content-Type: application/json" -d '{
        "name": "test_host",
        "variables": {
            "test1": "string",
            "test2": 12,
            "test3": 15055.0,
            "test4": "new!"
        }
    }' "http://demo.alignak.net:8888/host"


The result is a JSON object containing a `_status` property that should be 'OK' and an `_result` array property that contains information about the actions that were executed.

If an error is detected, the `_status` property is not 'OK' and a `_issues` array property will report the detected error(s).

The `/host/host_name` can be used to target the host. If a `name` property is present in the JSON data then this property will take precedence over the `host_name` in the endpoint.


Host enable/disable checks
~~~~~~~~~~~~~~~~~~~~~~~~~~
To enable/disable hosts/services checks, PATCH on the `host` endpoint providing the host (service) name and its checks configuration:
::

    $ curl -X PATCH -H "Content-Type: application/json" -d '{
        "name": "test_host",
        "active_checks_enabled": True,
        "passive_checks_enabled": True,
        "services": {
            "test_service": {
                "name": "test_ok_0",
                "active_checks_enabled": True,
                "passive_checks_enabled": True,
            },
            "test_service2": {
                "name": "test_ok_1",
                "active_checks_enabled": False,
                "passive_checks_enabled": False,
            },
            "test_service3": {
                "name": "test_ok_2",
                "active_checks_enabled": True,
                "passive_checks_enabled": False,
            },
        }
    }' "http://demo.alignak.net:8888/host"


The result is a JSON object containing a `_status` property that should be 'OK' and an `_result` array property that contains information about the actions that were executed.

If an error is detected, the `_status` property is not 'OK' and a `_issues` array property will report the detected error(s).

The `/host/host_name` can be used to target the host. If a `name` property is present in the JSON data then this property will take precedence over the `host_name` in the endpoint.


Host/service creation
~~~~~~~~~~~~~~~~~~~~~
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


