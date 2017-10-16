#!/usr/bin/env bash
curl -X PATCH -H "Content-Type: application/json" -d '{
        "name": "test_host_fred",
        "template": {
            "alias": "My host...",
            "_templates": ["windows-passive-host", "important"]
        },
        "livestate": [
           {
               "timestamp": 1506522626,
               "state": "up",
               "output": "Output...",
               "long_output": "Long output...",
               "perf_data": "host_counter=1"
           }
        ],
        "variables": {
            "first_name": "Fred",
            "Last name": "Mohier",
            "packages": [
               {
                  "id": "identifier", "name": "Package 2", "other": 1
               },
               {
                  "id": "identifier", "name": "Package 1", "other": 1
               }
            ]
        },
        "services": [
            {
                "name": "test_service",
                "livestate": [
                   {
                       "timestamp": 1506517200,
                       "state": "ok",
                       "output": "Output check ...",
                       "long_output": "Long output...",
                       "perf_data": "counter=1"
                   },
                   {
                       "timestamp": 1506517500,
                       "state": "ok",
                       "output": "Output check ...",
                       "long_output": "Long output...",
                       "perf_data": "counter=2"
                   },
                   {
                       "timestamp": 1506517800,
                       "state": "ok",
                       "output": "Output check ...",
                       "long_output": "Long output...",
                       "perf_data": "counter=3"
                   },
                   {
                       "timestamp": 1506518100,
                       "state": "ok",
                       "output": "Output check ...",
                       "long_output": "Long output...",
                       "perf_data": "counter=4"
                   }
                ]
            }
        ]
    }' "http://demo.alignak.net:8888/host"