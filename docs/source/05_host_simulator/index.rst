.. raw:: LaTeX

    \newpage

.. _host_simulator:

Host simulator
==============

The module repository contains an host simulator script located in the *test* directory.

This script allows to simulate one or more hosts against the Alignak Web Service.

The ``host-simulator`` script receives some command line parameters to define its behavior and uses a json data file for its data:


Command line interface
----------------------
``host-simulator`` command line interface:
::

    Usage:
        host-simulator [-h]
        host-simulator [-V]
        host-simulator [-v] [-q] [-c]
                       [-n server] [-e encryption]
                       [-w url] [-u username] [-p password]
                       [-d data] [-f folder]
                       [--random-hosts count]
                       [--random-services count]
                       [--random-hosts-sleep delay]
                       [--random-services-sleep delay]
                       [--loop-count count]
                       [--random-loop-sleep delay]

    Options:
        -h, --help                      Show this screen.
        -V, --version                   Show application version.
        -v, --verbose                   Run in verbose mode (more info to display)
        -q, --quiet                     Run in quiet mode (display nothing)
        -c, --check                     Check only (dry run), do not send notifications.
        -w, --ws url                    Specify WS URL [default: http://127.0.0.1:8888]
        -u, --username username         WS login username [default: admin]
        -p, --password password         WS login (or NSCA) password [default: admin]
        -d, --data data                 Data for the simulation [default: none]
        -f, --folder folder             Folder where to read/write data files [default: none]
        -n, --nsca-server server        Send NSCA notifications to the specified server address:port
        -e, --encryption 0              NSCA encryption mode (0 for none, 1 for Xor) [default: 0]
        --random-hosts 2                Random hosts dice roll [default: 2]
        --random-hosts-sleep 200        Random hosts sleep time in ms [default: 200]
        --random-services 2             Random services dice roll [default: 2]
        --random-services-sleep 100     Random services sleep time in ms [default: 100]
        -l, --loop-count 1              Number of iterations to run for the simulation [default: 1]
        --random-loop-sleep 5000        Random loop sleep time in ms [default: 5000]

    Exit code:
        0 if required operation succeeded
        1 if WS access is denied (check provided username/password)
        2 if element operation failed (missing template,...)

        64 if command line parameters are not used correctly

    Use cases:
        Display help message:
            host-simulator (-h | --help)

        Display current version:
            host-simulator -V
            host-simulator --version

        Specify WS parameters if they are different from the default
            host-simulator -w http://127.0.0.1:8888 -u admin -p admin

        Specify data file for simulation
            host-simulator -w http://127.0.0.1:8888 -u admin -p admin -d host-simulator.json -n alignak-fdj.kiosks.ipmfrance.com

        No random host/service selection (all hosts/services are simulated)
            host-simulator -w http://127.0.0.1:8888 -u admin -p admin -d host-simulator.json -n alignak-fdj.kiosks.ipmfrance.com --random-hosts 0 --random-services 0

        Execute 10 simulation loops
            host-simulator -w http://127.0.0.1:8888 -u admin -p admin -d host-simulator.json -n alignak-fdj.kiosks.ipmfrance.com --loop-count 10

        Send NSCA host/service checks
            Without encryption:
            host-simulator -w http://127.0.0.1:8888 -u admin -p admin -d host-simulator.json -n 127.0.0.1:5667

            Xor encryption:
            host-simulator -w http://127.0.0.1:8888 -u admin -p admin -d host-simulator.json -n 127.0.0.1:5667 -e 1:password

    Default behavior:
        The default behavior of the simulator is to randomly decide whether to simulate or not an host/service. Each host, and each service of an host,  has a chance of 1 in 2 to be simulated. You can change this behavior with the --random-hosts-count and --random-services-count parameters.

        By default, the simulation will be run once. Setting the loop count parameter to another value will allow simulation repetition with a random sleep time on each loop turn. Setting the loop count to 0 will create an infinite simulation.

    Hints and tips:
        Use the -v option to have more information log
        Use the -q option for the silent mode

        If the Alignak WS is configured to create unknown hosts/services, using this script will create the unknown hosts/services.

        Set the WS url parameter to 'none' will disable the Web Service. This is useful to only use the NSCA notifications else the script will send NSCA notifications AND Web Service notifications.


   An example:
      python host-simulator.py -v -w http://127.0.0.1:8888 -u admin -p admin -d host-simulator.json
       This will use the Alignak WS to report live state for the hosts/services defined in the file host-simulator.json

      python host-simulator.py -v -w none -d host-simulator.json -n 127.0.0.1 -e 1:my-password
       This will only send some NSCA checks for the hosts/services defined in the file host-simulator.json

      python host-simulator.py -v -w http://127.0.0.1:8888 -u admin -p admin -d host-simulator.json -n 127.0.0.1 -e 1:my-password
       This will use the Alignak WS and send some NSCA checks for the hosts/services defined in the file host-simulator.json


Data file
---------
``host-simulator`` data file:
::

   {
      "hosts": [
         {
            "name": "win-passive-[%02d-0-9]",

            "services": {
                "test_service": {
                    "name": "nsca_uptime"
                },
                "test_service2": {
                    "name": "nsca_cpu"
                },
                "test_service3": {
                    "name": "nsca_memory"
                },
                "test_service4": {
                    "name": "nsca_disk"
                }
            }
         },
         {
            "name": "win-passive-bis-[%02d-0-9]",

            "services": {
                "test_service": {
                    "name": "nsca_uptime"
                },
                "test_service2": {
                    "name": "nsca_cpu"
                },
                "test_service3": {
                    "name": "nsca_memory"
                },
                "test_service4": {
                    "name": "nsca_disk"
                }
            }
         }
      ]
   }

Host simulation
~~~~~~~~~~~~~~~
 You can define some hosts to simulate. The syntax for an host is the same as the one used by the Web Service module for an host livestate::

   "name": "passive-01",
   "livestate": {
      "state": "UP",
      "output": "WS output - active checks disabled"
   },

The script will post an host livestate with the provided data.

If the `name` field contains [] the script will try to generate several hosts. three information are included inside the brackets: a string format, a start index and an end index. This name `host-[%02d-0-9]` will make the script create 10 hosts named as `host-00`, `host-01`, ... `host-09`.