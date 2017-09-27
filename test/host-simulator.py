#!/usr/bin/python
# -*- coding: utf-8 -*-

#
# Copyright (C) 2015-2016: Frédéric Mohier
#
# Alignak Backend Client script is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any later version.
#
# Alignak Backend Client is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE.  See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this script.  If not, see <http://www.gnu.org/licenses/>.

"""
alignak-backend-cli command line interface::

    Usage:
        alignak-backend-cli [-h]
        alignak-backend-cli [-V]
        alignak-backend-cli [-v] [-q] [-c] [-l] [-m] [-e] [-i]
                            [-b url] [-u username] [-p password]
                            [-d data]
                            [-f folder]
                            [-T template] [-t type] [<action>] [<item>]

    Options:
        -h, --help                  Show this screen.
        -V, --version               Show application version.
        -v, --verbose               Run in verbose mode (more info to display)
        -q, --quiet                 Run in quiet mode (display nothing)
        -c, --check                 Check only (dry run), do not change the backend.
        -l, --list                  Get an items list
        -b, --ws url                Specify WS URL [default: http://127.0.0.1:8888]
        -u, --username=username     Backend login username [default: admin]
        -p, --password=password     Backend login password [default: admin]
        -d, --data=data             Data for the new item to create [default: none]
        -f, --folder=folder         Folder where to read/write data files [default: none]
        -i, --include-read-data     Do not use only the provided data, but append the one
                                    read from he backend
        -t, --type=host             Type of the provided item [default: host]
        -e, --embedded              Do not embed linked objects
        -m, --model                 Get only the templates
        -T, --template=template     Template to use for the new item

    Exit code:
        0 if required operation succeeded
        1 if backend access is denied (check provided username/password)
        2 if element operation failed (missing template,...)

        64 if command line parameters are not used correctly

    Use cases:
        Display help message:
            alignak-backend-cli (-h | --help)

        Display current version:
            alignak-backend-cli -V
            alignak-backend-cli --version

        Specify backend parameters if they are different from the default
            alignak-backend-cli -b=http://127.0.0.1:5000 -u=admin -p=admin get host_name

    Actions:
        'get' to get an item in the backend
        'list' (shortcut for 'get -l' to get the list of all items of a type
        'add' to add an(some) item(s) in the backend
        'update' to update an(some) item(s) in the backend
        'delete' to delete an item (or all items of a type) in the backend

    Use cases to get data:
        Get an items list from the backend:
            alignak-backend-cli get -l
            Try to get the list of all hosts and copy the JSON dump in a file named
            './alignak-object-list-hosts.json'

            alignak-backend-cli get -l -t user
            Try to get the list of all users and copy the JSON dump in a file named
            './alignak-object-list-users.json'

            alignak-backend-cli get -l -f /tmp -t user
            Try to get the list of all users and copy the JSON dump in a file named
            '/tmp/alignak-object-list-users.json'

            alignak-backend-cli list -t user
            Shortcut for 'alignak-backend-cli get -l -t user'

        Get the hosts templates list from the backend:
            alignak-backend-cli -l -m
            Try to get the list of all hosts templates and copy the JSON dump in a
            file named './alignak-object-list-hosts.json'

        Get an item from the backend:
            alignak-backend-cli get host_name
            Try to get the definition of an host named 'host_name' and copy the JSON dump
            in a file named './alignak-object-dump-host-host_name.json'

            alignak-backend-cli -t user get contact_name
            Try to get the definition of a user (contact) contact named 'contact_name' and
            copy the JSON dump in a file named './alignak-object-dump-contact-contact_name.json'

        Get a service from the backend:
            alignak-backend-cli get -t service host_name/service_name
            Try to get the definition of the service service_name for an host named 'host_name'
            and copy the JSON dump in a file named
            './alignak-object-dump-service-host_name_service_name.json'

    Use cases to add data:
        Add an item to the backend (without templating):
            alignak-backend-cli new_host
            This will add an host named new_host

            alignak-backend-cli -t user new_contact
            This will add a user named new_contact

        Add an item to the backend (with some data):
            alignak-backend-cli --data="/tmp/input_host.json" add new_host
            This will add an host named new_host with the data that are read from the
            JSON file /tmp/input_host.json

            alignak-backend-cli -t user new_contact --data="stdin"
            This will add a user named new_contact with the JSON data read from the
            stdin. You can 'cat file > alignak-backend-cli -t user new_contact --data="stdin"'

        Add an item to the backend based on a template:
            alignak-backend-cli -T host_template add new_host
            This will add an host named new_host with the data existing in the template
            host_template

        Add an item to the backend based on several templates:
            alignak-backend-cli -T "host_template,host_template2" add new_host
            This will add an host named new_host with the data existing in the templates
            host_template and host_template2

    Use cases to update data:
        Update an item into the backend (with some data):
            alignak-backend-cli --data "./update_host.json" update test_host
            This will update an host named test_host with the data that are read from the
            JSON file ./update_host.json

    Use cases to delete data:
        Delete an item from the backend:
            alignak-backend-cli delete test_host
            This will delete the host named test_host

        Delete all items from the backend:
            alignak-backend-cli delete -t retentionservice
            This will delete all the retentionservice items

        Delete all the services of an host from the backend:
            alignak-backend-cli delete -t service test_host/*
            This will delete all the services of the host named test_host

    Hints and tips:
        You can operate on any backend endpoint: user, host, service, graphite, ... see the
        Alignak backend documentation (http://alignak-backend.readthedocs.io/) to get a full
        list of the available endpoints and their data fields.

        For a service specify the name as 'host_name/service_name' to get a service for a
        specific host, else the script will return the first service with the required name

        By default, the script embeds in the provided result all the possible embeddable data.
        As such, when you get a service, you will also get its host, check period, ...
        Unfortunately, the same embedding can not be used when adding or updating an item :(

        Use the -m (--model) option to get the templates lists for the host, service or user
        when you get a list. If not used, the list do not include the templates

        Use the -e (--embedded) option to get the linked objects embedded in the output. For
        an host, as an example, the result will include the linked check period, contacts,
        check command,... If not used, the result will only include the linked objects identifier.

        To get the list of all the services of an host, you can get the service list with
        a wildcard in the host name. For all the services of the host named 'passive-01',
        use 'passive-01/*' as in 'alignak-backend-cli get -l -t service passive-01/*'

        To get all the information for an host, including the services, you can use
        a wildcard in the host name. For all the information of the host named 'passive-01',
        use 'passive-01/*' as in 'alignak-backend-cli get -t host passive-01/*'. Using the -e
        option will include all the related objects of the host and its services in the
        dump file.

        If somehow you need to update an item and post all the data when updating, use the
        `-i` option. This will use the data read from the backend and update this data with
        the one provided in the data file specified in the `-d` option.

        Use the -v option to have more information

"""
from __future__ import print_function

import os
import sys
import json
import logging

import copy
from datetime import datetime
import psutil

import requests

from docopt import docopt, DocoptExit

from alignak_backend_client.client import Backend, BackendException

# Configure logger
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)8s - %(message)s')
# Name the logger to get the backend client logs
logger = logging.getLogger('host-simulator')
logger.setLevel('INFO')

# Use the same version as the main alignak backend
__version__ = "0.0.1"


class HostSimulator(object):
    """Class to simulate an host for the Alignak WS"""

    def __init__(self):
        self.logged_in = False
        self.logged_in_user = None
        
        # Get command line parameters
        args = None
        try:
            args = docopt(__doc__, version=__version__)
        except DocoptExit as exp:
            print("Command line parsing error:\n%s." % (exp))
            print("~~~~~~~~~~~~~~~~~~~~~~~~~~")
            print("Exiting with error code: 64")
            exit(64)

        # Verbose mode
        self.verbose = False
        if args['--verbose']:
            logger.setLevel('DEBUG')
            self.verbose = True

        # Quiet mode
        self.quiet = False
        if args['--quiet']:
            logger.setLevel('NOTSET')
            self.quiet = True

        logger.debug("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        logger.debug("host-simulator, version: %s", __version__)
        logger.debug("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")

        # Dry-run mode?
        self.dry_run = args['--check']
        logger.debug("Dry-run mode (check only): %s", self.dry_run)

        # WS URL
        self.session = None
        self.session_url = args['--ws']
        logger.debug("Backend URL: %s", self.session_url)

        # WS credentials
        self.username = args['--username']
        self.password = args['--password']
        logger.debug("WS login with credentials: %s/%s", self.username, self.password)

        # NSCA mode
        self.nsca_notifier = args['--nsca-server']
        self.port = 5667
        if self.nsca_notifier and ':' in self.nsca_notifier:
            data = self.nsca_notifier.split(':')
            self.nsca_notifier = data[0]
            self.port = int(data[1])
        self.encryption = args['--encryption']
        self.nsca_password = None
        if ':' in self.encryption:
            data = self.encryption.split(':')
            self.encryption = int(data[0])
            self.nsca_password = data[1]
        logger.debug("NSCA notifications: %s, port: %s", self.nsca_notifier, self.port)

        # Get the data files folder
        self.folder = None
        if args['--folder'] != 'none':
            self.folder = args['--folder']
        logger.debug("Data files folder: %s", self.folder)

        # Get the associated data file
        self.data = None
        if args['--data'] != 'none':
            self.data = args['--data']
        logger.debug("Item data provided: %s", self.data)
        self.include_read_data = args['--include-read-data']
        logger.debug("Use backend read data: %s", self.include_read_data)

    def initialize(self):
        # pylint: disable=attribute-defined-outside-init
        """Login on backend with username and password

        :return: None
        """
        try:
            logger.info("Authenticating...")
            self.session = requests.Session()

            # Login with username/password (real backend login)
            headers = {'Content-Type': 'application/json'}
            params = {'username': self.username, 'password': self.password}
            response = self.session.post(self.session_url + '/login', json=params, headers=headers)
            assert response.status_code == 200
            resp = response.json()
        except Exception as exp:  # pragma: no cover, should never happen
            logger.error("Response: %s", str(exp))
            print("Access denied!")
            print("~~~~~~~~~~~~~~~~~~~~~~~~~~")
            print("Exiting with error code: 1")
            exit(1)

        logger.info("Authenticated.")

    def simulate(self):
        """Simulate hosts in the configuration

        :return: True is all simulation succeeded else False
        """
        if self.data is None:
            self.data = {}

        # If some data are provided, try to get them
        json_data = None
        path = None
        if self.data:
            try:
                # Data may be provided on the command line or from a file
                if self.data == 'stdin':
                    input_file = sys.stdin
                else:
                    path = os.path.join(self.folder or os.getcwd(), self.data)
                    input_file = open(path)

                json_data = json.load(input_file)
                logger.info("Got provided data: %s", json_data)
                if input_file is not sys.stdin:
                    input_file.close()
            except IOError:
                logger.error("Error reading data file: %s", path)
                return False
            except ValueError:
                logger.error("Error malformed data file: %s", path)
                return False

        if json_data is None:
            logger.error("-> missing simulation data!")
            return False

        if 'hosts' not in json_data:
            logger.error("-> missing hosts in the simulation data!")
            return False

        # Simulate the hosts
        update = True
        for host in json_data['hosts']:
            if 'name' not in host:
                logger.error("-> missing host name in: %s", host)
                continue
            logger.info("Found host: %s", host['name'])

            simulated_hosts = [host]
            # If host name is a pattern...
            name = host['name']
            if '[' in name and ']' in name:
                pattern = name[name.find("[")+1:name.find("]")]
                logger.info("Found host name pattern: %s", pattern)
                if '-' in pattern:
                    # pattern is format-min-max
                    limits = pattern.split('-')
                    logger.info("Found host name pattern limits: %s", limits)
                    if len(limits) == 3:
                        new_name = name.replace('[%s-%s-%s]' % (limits[0], limits[1], limits[2]), '***')
                        logger.info("Found host name pattern: %s", new_name)

                        simulated_hosts = []
                        for index in range(int(limits[1]), int(limits[2]) + 1):
                            logger.info("Host: %s", new_name.replace('***', limits[0] % index))
                            new_host = copy.copy(host)
                            new_host['name'] = new_name.replace('***', limits[0] % index)
                            simulated_hosts.append(new_host)

            for simulated_host in simulated_hosts:
                name = simulated_host['name']

                # Define host livestate as uptime if no data is provided
                if 'livestate' not in host:
                    uptime = psutil.boot_time()
                    str_uptime = datetime.fromtimestamp(uptime).strftime("%Y-%m-%d %H:%M:%S")

                    simulated_host["livestate"] = {
                        "state": "up",
                        "output": "Host is up since %s" % str_uptime,
                        "perf_data": "'uptime'=%d" % uptime
                    }
                    logger.info(". built livestate: %s", simulated_host['livestate'])

                if 'services' in host:
                    for service_id, service in host['services'].iteritems():
                        if 'name' not in service:
                            logger.error("-> missing service name in: %s", service)
                            continue
                        logger.info(". found service: %s", service['name'])

                        # Host disks
                        if 'livestate' not in service and service['name'] in ['nsca_disk']:
                            perfdatas = []
                            disk_partitions = psutil.disk_partitions(all=False)
                            for disk_partition in disk_partitions:
                                logger.debug("  . disk partition: %s", disk_partition)

                                disk = getattr(disk_partition, 'mountpoint')
                                disk_usage = psutil.disk_usage(disk)
                                logger.debug("  . disk usage: %s", disk_usage)
                                for key in disk_usage._fields:
                                    if 'percent' in key:
                                        perfdatas.append("'disk_%s_percent_used'=%.2f%%"
                                                         % (disk, getattr(disk_usage, key)))
                                    else:
                                        perfdatas.append("'disk_%s_%s'=%dB"
                                                         % (disk, key, getattr(disk_usage, key)))


                            service["livestate"] = {
                                "state": "ok",
                                "output": "Host disks statistics",
                                "perf_data": ", ".join(perfdatas)
                            }
                            logger.debug("  . built livestate: %s", service['livestate'])

                        # Host memory
                        if 'livestate' not in service and service['name'] in ['nsca_memory']:
                            perfdatas = []
                            virtual_memory = psutil.virtual_memory()
                            logger.debug("  . memory: %s", virtual_memory)
                            for key in virtual_memory._fields:
                                if 'percent' in key:
                                    perfdatas.append("'mem_percent_used_%s'=%.2f%%"
                                                     % (key, getattr(virtual_memory, key)))
                                else:
                                    perfdatas.append("'mem_%s'=%dB"
                                                     % (key, getattr(virtual_memory, key)))

                            swap_memory = psutil.swap_memory()
                            logger.debug("  . memory: %s", swap_memory)
                            for key in swap_memory._fields:
                                if 'percent' in key:
                                    perfdatas.append("'swap_used_%s'=%.2f%%"
                                                     % (key, getattr(swap_memory, key)))
                                else:
                                    perfdatas.append("'swap_%s'=%dB"
                                                     % (key, getattr(swap_memory, key)))

                            service["livestate"] = {
                                "state": "ok",
                                "output": "Host memory statistics",
                                "perf_data": ", ".join(perfdatas)
                            }
                            logger.debug("  . built livestate: %s", service['livestate'])

                        # Host CPU
                        if 'livestate' not in service and service['name'] in ['nsca_cpu']:
                            perfdatas = []
                            cpu_count = psutil.cpu_count()
                            perfdatas.append("'cpu_count'=%d" % cpu_count)
                            logger.debug("  . cpu count: %d", cpu_count)

                            cpu_percents = psutil.cpu_percent(percpu=True)
                            cpu = 1
                            for percent in cpu_percents:
                                perfdatas.append("'cpu_%d_percent'=%.2f%%" % (cpu, percent))
                                cpu += 1

                            cpu_times_percent = psutil.cpu_times_percent(percpu=True)
                            cpu = 1
                            for cpu_times_percent in cpu_times_percent:
                                logger.debug("  . cpu time percent: %s", cpu_times_percent)
                                for key in cpu_times_percent._fields:
                                    perfdatas.append("'cpu_%d_%s_percent'=%.2f%%" % (cpu, key, getattr(cpu_times_percent, key)))
                                cpu += 1

                            service["livestate"] = {
                                "state": "ok",
                                "output": "Host CPU statistics",
                                "perf_data": ", ".join(perfdatas)
                            }
                            logger.debug("  . built livestate: %s", service['livestate'])

                        # Host uptime
                        if 'livestate' not in service and service['name'] in ['nsca_uptime']:
                            uptime = psutil.boot_time()
                            str_uptime = datetime.fromtimestamp(uptime).strftime("%Y-%m-%d %H:%M:%S")

                            service["livestate"] = {
                                "state": "ok",
                                "output": "Host is up since %s" % str_uptime,
                                "perf_data": "'uptime'=%d" % uptime
                            }
                            logger.debug("  . built livestate: %s", service['livestate'])

                # Update host services livestate
                headers = {'Content-Type': 'application/json'}
                response = self.session.patch(self.session_url + '/host',
                                              json=simulated_host, headers=headers)
                if response.status_code != 200:
                    update = False
                    logger.error("Host '%s' did not updated correctly!", name)
                else:
                    result = response.json()
                    logger.info("Host '%s' update result: %s", name, result)
                    if result['_status'] == 'OK':
                        logger.info("Host '%s' updated:", name)
                        for log in result['_result']:
                            logger.info(" -> %s", log)
                    else:
                        update = False
                        logger.error("Host '%s' did not updated correctly!", name)
                        for log in result['_issues']:
                            logger.error(" -> %s", log)

        return update


def main():
    """
    Main function
    """
    bc = HostSimulator()
    bc.initialize()

    success = bc.simulate()

    if not success:
        logger.error("Simulation failed. See the log for more details.")
        if not bc.verbose:
            logger.warning("Set verbose mode to have more information (-v)")
        exit(2)

    exit(0)


if __name__ == "__main__":  # pragma: no cover
    main()
