# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2016: Alignak contrib team, see AUTHORS.txt file for contributors
#
# This file is part of Alignak contrib projet.
#
# Alignak is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Alignak is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Alignak.  If not, see <http://www.gnu.org/licenses/>.
#
#

"""
This module is an Alignak Receiver module that exposes a Web services interface.
"""

from __future__ import print_function
import os
import sys
import json
import time
import logging
import inspect
import threading
import Queue
import requests
import cherrypy

from alignak_backend_client.client import Backend, BackendException

# Used for the main function to run module independently
from alignak.objects.module import Module
from alignak.modulesmanager import ModulesManager

from alignak.basemodule import BaseModule
from alignak.http.daemon import HTTPDaemon
from alignak.external_command import ExternalCommand

logger = logging.getLogger('alignak.module')  # pylint: disable=C0103

# pylint: disable=C0103
properties = {
    'daemons': ['receiver'],
    'type': 'web-services',
    'external': True,
    'phases': ['running'],
}


def get_instance(mod_conf):
    """Return a module instance for the modules manager

    :param mod_conf: the module properties as defined globally in this file
    :return:
    """
    logger.info("Give an instance of %s for alias: %s", mod_conf.python_name, mod_conf.module_alias)

    return AlignakWebServices(mod_conf)


class WSInterface(object):
    """Interface for Alignak Web Services.

    """
    def __init__(self, app):
        self.app = app

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def index(self):
        """Wrapper to call api from /

        :return: function list
        """
        return self.api()

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def api(self):
        """List the methods available on the interface

        :return: a list of methods available
        :rtype: list
        """
        return [x[0]for x in inspect.getmembers(self, predicate=inspect.ismethod)
                if not x[0].startswith('__')]

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def api_full(self):
        """List the api methods and their parameters

        :return: a list of methods and parameters
        :rtype: dict
        """
        full_api = {}
        for fun in self.api():
            full_api[fun] = {}
            full_api[fun][u"doc"] = getattr(self, fun).__doc__
            full_api[fun][u"args"] = {}

            spec = inspect.getargspec(getattr(self, fun))
            args = [a for a in spec.args if a != 'self']
            if spec.defaults:
                a_dict = dict(zip(args, spec.defaults))
            else:
                a_dict = dict(zip(args, (u"No default value",) * len(args)))

            full_api[fun][u"args"] = a_dict

        full_api[u"side_note"] = u"When posting data you have to serialize value. Example : " \
                                 u"POST /set_log_level " \
                                 u"{'loglevel' : serialize('INFO')}"

        return full_api

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def are_you_alive(self):
        """Is the module alive

        :return: True if is alive, False otherwise
        :rtype: bool
        """
        return 'Yes I am :)'

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def alignak_map(self):
        """Get the alignak internal map and state

        :return: A json array of the Alignak daemons state
        :rtype: list
        """
        return self.app.daemons_map

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def command(self):
        """ Request to execute an external command
        :return:
        """
        if cherrypy.request.method != "POST":
            return {'_status': 'ko', '_result': 'You must only POST on this endpoint.'}

        if cherrypy.request and not cherrypy.request.json:
            return {'_status': 'ko', '_result': 'You must POST parameters on this endpoint.'}

        command = cherrypy.request.json.get('command', None)
        timestamp = cherrypy.request.json.get('timestamp', None)
        element = cherrypy.request.json.get('element', None)
        host = cherrypy.request.json.get('host', None)
        service = cherrypy.request.json.get('service', None)
        user = cherrypy.request.json.get('user', None)
        parameters = cherrypy.request.json.get('parameters', None)

        if not command:
            return {'_status': 'ko', '_result': 'Missing command parameter'}

        command_line = command.upper()
        if timestamp:
            command_line = '[%d] %s' % (timestamp, command)

        if host or service or user:
            if host:
                command_line = '%s;%s' % (command_line, host)
            if service:
                command_line = '%s;%s' % (command_line, service)
            if user:
                command_line = '%s;%s' % (command_line, user)
        elif element:
            if '/' in element:
                # Replace only the first /
                element = element.replace('/', ';', 1)
            command_line = '%s;%s' % (command_line, element)

        if parameters:
            command_line = '%s;%s' % (command_line, parameters)

        # Add a command to get managed
        self.app.to_q.put(ExternalCommand(command_line))

        return {'_status': 'ok', '_result': command_line}
    command.method = 'post'

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def alignak_logs(self):
        """Get the alignak logs

        :return: True if is alive, False otherwise
        :rtype: dict
        """
        return self.app.getBackendHistory()


class AlignakWebServices(BaseModule):
    """Web services module main class"""
    def __init__(self, mod_conf):
        """Module initialization

        mod_conf is a dictionary that contains:
        - all the variables declared in the module configuration file
        - a 'properties' value that is the module properties as defined globally in this file

        :param mod_conf: module configuration file as a dictionary
        """
        BaseModule.__init__(self, mod_conf)

        # pylint: disable=global-statement
        global logger
        logger = logging.getLogger('alignak.module.%s' % self.alias)

        logger.debug("inner properties: %s", self.__dict__)
        logger.debug("received configuration: %s", mod_conf.__dict__)
        logger.debug("loaded into: %s", self.loaded_into)

        # Alignak Backend part
        # ---
        self.backend_available = False
        self.backend_url = getattr(mod_conf, 'alignak_backend', '')
        if self.backend_url:
            logger.info("Alignak backend endpoint: %s", self.backend_url)

            self.client_processes = int(getattr(mod_conf, 'client_processes', '1'))
            logger.info("Number of processes used by backend client: %s", self.client_processes)

            self.backend = Backend(self.backend_url, self.client_processes)
            # If a backend token is provided in the configuration, we assume that it is valid
            # and the backend is yet connected and authenticated
            self.backend.token = getattr(mod_conf, 'token', '')
            self.backend.authenticated = (self.backend.token != '')
            self.backend_available = False

            self.backend_username = getattr(mod_conf, 'username', '')
            self.backend_password = getattr(mod_conf, 'password', '')
            self.backend_generate = getattr(mod_conf, 'allowgeneratetoken', False)

            self.alignak_backend_polling_period = \
                int(getattr(mod_conf, 'alignak_backend_polling_period', '10'))

            if not self.backend.token and not self.backend_username:
                logger.warning("No Alignak backend credentials configured (empty token and "
                               "empty username. "
                               "The requested backend connection will not be available")
                self.backend_url = ''
            else:
                self.getBackendAvailability()
        else:
            logger.warning('Alignak Backend is not configured. '
                           'Some module features will not be available.')

        # Alignak Arbiter host / post
        self.alignak_host = getattr(mod_conf, 'alignak_host', '127.0.0.1')
        self.alignak_port = int(getattr(mod_conf, 'alignak_port', '7770'))
        if not self.alignak_host:
            logger.warning('Alignak Arbiter address is not configured. Alignak polling is '
                           'disabled and some information will not be available.')
        else:
            logger.info("Alignak Arbiter configuration: %s:%d",
                        self.alignak_host, self.alignak_port)

        # Alignak polling
        self.alignak_is_alive = False
        self.alignak_polling_period = \
            int(getattr(mod_conf, 'alignak_polling_period', '1'))
        logger.info("Alignak Arbiter polling period: %d", self.alignak_polling_period)
        self.alignak_daemons_polling_period = \
            int(getattr(mod_conf, 'alignak_daemons_polling_period', '10'))
        logger.info("Alignak daemons get status period: %d", self.alignak_daemons_polling_period)

        # SSL configuration
        self.use_ssl = \
            getattr(mod_conf, 'use_ssl', '0') == '1'

        self.ca_cert = os.path.abspath(
            getattr(mod_conf, 'ca_cert', '/usr/local/etc/alignak/certs/ca.pem')
        )
        if self.use_ssl and not os.path.exists(self.ca_cert):
            logger.error('The CA certificate %s is missing (ca_cert). '
                         'Please fix it in your configuration', self.ca_cert)
            self.use_ssl = False

        self.server_cert = os.path.abspath(
            getattr(mod_conf, 'server_cert', '/usr/local/etc/alignak/certs/server.cert')
        )
        if self.use_ssl and not os.path.exists(self.server_cert):
            logger.error("The SSL certificate '%s' is missing (server_cert). "
                         "Please fix it in your configuration", self.server_cert)
            self.use_ssl = False

        self.server_key = os.path.abspath(
            getattr(mod_conf, 'server_key', '/usr/local/etc/alignak/certs/server.key')
        )
        if self.use_ssl and not os.path.exists(self.server_key):
            logger.error('The SSL key %s is missing (server_key). '
                         'Please fix it in your configuration', self.server_key)
            self.use_ssl = False

        self.server_dh = os.path.abspath(
            getattr(mod_conf, 'server_dh', '/usr/local/etc/alignak/certs/server.pem')
        )
        if self.use_ssl and not os.path.exists(self.server_dh):
            logger.error('The SSL DH %s is missing (server_dh). '
                         'Please fix it in your configuration', self.server_dh)
            self.use_ssl = False

        self.hard_ssl_name_check = getattr(mod_conf, 'hard_ssl_name_check', '0') == '0'

        # SSL information log
        if self.use_ssl:
            logger.info("Using SSL CA certificate: %s", self.ca_cert)
            logger.info("Using SSL server files: %s/%s", self.server_cert, self.server_key)
            if self.hard_ssl_name_check:
                logger.info("Enabling hard SSL server name verification")
        else:
            logger.info("SSL is not enabled, this is not recommended. "
                        "You should consider enabling SSL!")

        # Host / post listening to...
        self.host = getattr(mod_conf, 'host', '0.0.0.0')
        self.port = int(getattr(mod_conf, 'port', '8888'))

        protocol = 'http'
        if self.use_ssl:
            protocol = 'https'
        self.uri = '%s://%s:%s' % (protocol, self.host, self.port)
        logger.info("configuration, listening on: %s", self.uri)

        # My own HTTP interface...
        self.http_interface = WSInterface(self)

        # My thread pool (simultaneous connections)
        self.daemon_thread_pool_size = 8

        self.http_daemon = None
        self.http_thread = None

        # Our Alignak daemons map
        self.daemons_map = {}

        # Daemon properties that we are interested in
        self.daemon_properties = ['address', 'port', 'spare', 'is_sent',
                                  'realm_name', 'manage_sub_realms', 'manage_arbiters',
                                  'alive', 'passive', 'reachable', 'last_check',
                                  'check_interval', 'polling_interval', 'max_check_attempts']

        # Count received commands
        self.received_commands = 0

    def init(self):
        """This function initializes the module instance.

        If False is returned, the modules manager will periodically retry to initialize the module.
        If an exception is raised, the module will be definitely considered as dead :/

        This function must be present and return True for Alignak to consider the module as loaded
        and fully functional.

        :return: True if initialization is ok, else False
        """
        return True

    def getBackendAvailability(self):
        """Authenticate and get the token

        :return: None
        """
        generate = 'enabled'
        if not self.backend_generate:
            generate = 'disabled'

        try:
            if not self.backend.authenticated:
                logger.info("Signing-in to the backend...")
                self.backend_available = self.backend.login(self.backend_username,
                                                            self.backend_password, generate)
            logger.debug("Checking backend availability, token: %s, authenticated: %s",
                         self.backend.token, self.backend.authenticated)
            self.backend.get('/realm', {'where': json.dumps({'name': 'All'})})
            self.backend_available = True
        except BackendException as exp:
            logger.warning("Alignak backend is currently not available.")
            logger.debug("Exception: %s", exp)
            self.backend_available = False

    def getBackendHistory(self, search=None):
        """Get the backend Alignak logs

        :return: None
        """
        history = []

        if not search:
            search = {}
        if "sort" not in search:
            search.update({'sort': '-_id'})
        if 'embedded' not in search:
            search.update({'embedded': {'logcheckresult': 1}})

        try:
            if not self.backend.authenticated:
                logger.info("Signing-in to the backend...")
                self.backend_available = self.backend.login(self.backend_username,
                                                            self.backend_password)
            logger.debug("Getting history: %s", search)

            result = self.backend.get('history', json.dumps(search))
            if result['_status'] == 'OK':
                logger.debug("history, got %d items", len(result['_items']))
                result.pop('_links')
                return result

            logger.warning("history request, got a problem: %s", result)
        except BackendException as exp:
            logger.warning("Alignak backend is currently not available.")
            logger.debug("Exception: %s", exp)
            self.backend_available = False

        return history

    def http_daemon_thread(self):
        """Main function of the http daemon thread.

        It will loop forever unless we stop the main process

        :return: None
        """
        logger.info("HTTP main thread running")

        # The main thing is to have a pool of X concurrent requests for the http_daemon,
        # so "no_lock" calls can always be directly answer without having a "locked" version to
        # finish
        try:
            self.http_daemon.run()
        except Exception, exp:  # pylint: disable=W0703
            logger.exception('The HTTP daemon failed with the error %s, exiting', str(exp))
            raise exp
        logger.info("HTTP main thread exiting")

    def do_loop_turn(self):
        """This function is present because of an abstract function in the BaseModule class"""
        logger.info("In loop")
        time.sleep(1)

    def main(self):
        # pylint: disable=too-many-nested-blocks
        """Main loop of the process

        This module is an "external" module
        :return:
        """
        # Set the OS process title
        self.set_proctitle(self.alias)
        self.set_exit_handler()

        logger.info("starting...")

        logger.info("starting http_daemon thread..")
        self.http_daemon = HTTPDaemon(self.host, self.port, self.http_interface,
                                      self.use_ssl, self.ca_cert, self.server_key,
                                      self.server_cert, self.server_dh,
                                      self.daemon_thread_pool_size)

        self.http_thread = threading.Thread(target=self.http_daemon_thread, name='http_thread')
        self.http_thread.daemon = True
        self.http_thread.start()
        logger.info("HTTP daemon thread started")

        # Polling period (-100 to get sure to poll on the first loop iteration)
        ping_alignak_backend_next_time = time.time() - 100
        ping_alignak_next_time = time.time() - 100
        get_daemons_next_time = time.time() - 100

        # Endless loop...
        while not self.interrupted:
            start = time.time()

            if self.to_q:
                # Get messages in the queue
                try:
                    message = self.to_q.get_nowait()
                    if isinstance(message, ExternalCommand):
                        # print("Got an external command: %s", message.cmd_line)
                        logger.info("Got an external command: %s", message.cmd_line)
                        # Send external command to my Alignak daemon...
                        self.from_q.put(message)
                        self.received_commands += 1
                    else:
                        logger.warning("Got a message that is not an external command: %s", message)
                        # print("Got a message that is not an external command: %s", message)
                except Queue.Empty:
                    # logger.debug("No message in the module queue")
                    pass

            if self.backend_url:
                # Check backend connection
                if ping_alignak_backend_next_time < start:
                    ping_alignak_backend_next_time = start + self.alignak_backend_polling_period

                    self.getBackendAvailability()
                    time.sleep(0.1)

            if not self.alignak_host:
                # Do not check Alignak daemons...
                continue

            if ping_alignak_next_time < start:
                ping_alignak_next_time = start + self.alignak_polling_period

                # Ping Alignak Arbiter
                response = requests.get("http://%s:%s/ping" %
                                        (self.alignak_host, self.alignak_port))
                if response.status_code == 200:
                    if response.json() == 'pong':
                        self.alignak_is_alive = True
                    else:
                        logger.error("arbiter ping/pong failed!")
                time.sleep(0.1)

            # Get daemons map / status only if Alignak is alive
            if self.alignak_is_alive and get_daemons_next_time < start:
                get_daemons_next_time = start + self.alignak_daemons_polling_period

                # Get Arbiter all states
                response = requests.get("http://%s:%s/get_all_states" %
                                        (self.alignak_host, self.alignak_port))
                if response.status_code != 200:
                    continue

                response_dict = response.json()
                for daemon_type in response_dict:
                    if daemon_type not in self.daemons_map:
                        self.daemons_map[daemon_type] = {}

                    for daemon in response_dict[daemon_type]:
                        daemon_name = daemon[daemon_type + '_name']
                        if daemon_name not in self.daemons_map:
                            self.daemons_map[daemon_type][daemon_name] = {}

                        for prop in self.daemon_properties:
                            try:
                                self.daemons_map[daemon_type][daemon_name][prop] = daemon[prop]
                            except ValueError:
                                self.daemons_map[daemon_type][daemon_name][prop] = 'unknown'
                time.sleep(0.1)

            logger.debug("time to manage queue and Alignak state: %d seconds", time.time() - start)
            time.sleep(0.5)

        logger.info("stopping...")

        if self.http_daemon:
            logger.info("shutting down http_daemon...")
            self.http_daemon.request_stop()

        if self.http_thread:
            logger.info("joining http_thread...")

            # Add a timeout to join so that we can manually quit
            self.http_thread.join(timeout=15)
            if self.http_thread.is_alive():
                logger.warning("http_thread failed to terminate. Calling _Thread__stop")
                try:
                    self.http_thread._Thread__stop()  # pylint: disable=protected-access
                except Exception:
                    pass

        logger.info("stopped")

if __name__ == '__main__':
    logging.getLogger("alignak_backend_client").setLevel(logging.DEBUG)
    logger.setLevel(logging.DEBUG)

    # Create an Alignak module
    mod = Module({
        'module_alias': 'web-services',
        'module_types': 'web-services',
        'python_name': 'alignak_module_ws',
        # Alignak backend configuration
        'alignak_backend': 'http://127.0.0.1:5000',
        # 'token': '1489219787082-4a226588-9c8b-4e17-8e56-c1b5d31db28e',
        'username': 'admin', 'password': 'admin',
        # Set Arbiter address as empty to not poll the Arbiter else the test will fail!
        'alignak_host': '',
        'alignak_port': 7770,
    })
    # Create the modules manager for a daemon type
    modulemanager = ModulesManager('receiver', None)
    # Load and initialize the module
    modulemanager.load_and_init([mod])
    my_module = modulemanager.instances[0]
    # Start external modules
    modulemanager.start_external_instances()
