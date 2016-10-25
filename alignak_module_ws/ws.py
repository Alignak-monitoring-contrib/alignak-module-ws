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

import os
import time

import logging

import threading

import requests
import cherrypy

from alignak.objects.module import Module
from alignak.basemodule import BaseModule
from alignak.http.daemon import HTTPDaemon
from alignak.http.arbiter_interface import ArbiterInterface

logger = logging.getLogger('alignak.module')  # pylint: disable=C0103

# pylint: disable=C0103
properties = {
    'daemons': ['receiver'],
    'type': 'web-services',
    'external': True,
    'phases': ['running'],
}


def get_instance(mod_conf):
    """
    Return a module instance for the modules manager

    :param mod_conf: the module properties as defined globally in this file
    :return:
    """
    logger.info("Give an instance of %s for alias: %s", mod_conf.python_name, mod_conf.module_alias)

    return AlignakWebServices(mod_conf)


class WSInterface(ArbiterInterface):  # pragma: no cover, not with unit tests
    """Interface for Alignak Web Services.

    The WS interface is based on the Arbiter interface and completed with some more methods.
    """
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def are_you_alive(self):
        """Is the module alive

        :return: True if is alive, False otherwise
        :rtype: bool
        """
        return 'Yes!'

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def alignak_map(self):
        """Get the alignak internal map and state

        :return: True if is alive, False otherwise
        :rtype: dict
        """
        return self.app.daemons_map


class AlignakWebServices(BaseModule):
    """
    Web services module main class
    """
    def __init__(self, mod_conf):
        """
        Module initialization

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

        # Alignak Arbiter host / post
        self.alignak_host = getattr(mod_conf, 'alignak_host', '127.0.0.1')
        self.alignak_port = int(getattr(mod_conf, 'alignak_port', '7770'))
        logger.info("configuration, Alignak Arbiter: %s:%d", self.alignak_host, self.alignak_port)
        if not self.alignak_host:
            logger.warning('Alignak Arbiter address is not configured. Alignak polling is '
                           'disabled and some information will not be available.')

        # Alignak polling
        self.alignak_is_alive = False
        self.alignak_polling_period = \
            int(getattr(mod_conf, 'alignak_polling_period', '1'))
        self.alignak_daemons_polling_period = \
            int(getattr(mod_conf, 'alignak_daemons_polling_period', '10'))

        # Host / post listening to...
        self.host = getattr(mod_conf, 'host', '0.0.0.0')
        self.port = int(getattr(mod_conf, 'port', '8888'))
        logger.info("configuration, listening on: %s:%d", self.host, self.port)

        # SSL configuration
        self.use_ssl = \
            getattr(mod_conf, 'use_ssl', '0') == '1'

        self.ca_cert = os.path.abspath(
            getattr(mod_conf, 'ca_cert', '/usr/local/etc/alignak/certs/ca.pem')
        )
        if self.use_ssl and not os.path.exists(self.ca_cert):
            logger.error('Error : the CA certificate %s is missing (ca_cert).'
                         'Please fix it in your configuration', self.ca_cert)
            self.use_ssl = False

        self.server_cert = os.path.abspath(
            getattr(mod_conf, 'server_cert', '/usr/local/etc/alignak/certs/server.cert')
        )
        if self.use_ssl and not os.path.exists(self.server_cert):
            logger.error('Error : the SSL certificate %s is missing (server_cert).'
                         'Please fix it in your configuration', self.server_cert)
            self.use_ssl = False

        self.server_key = os.path.abspath(
            getattr(mod_conf, 'server_key', '/usr/local/etc/alignak/certs/server.key')
        )
        if self.use_ssl and not os.path.exists(self.server_key):
            logger.error('Error : the SSL key %s is missing (server_key).'
                         'Please fix it in your configuration', self.server_key)
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
                                  'realm', 'manage_sub_realms', 'manage_arbiters',
                                  'alive', 'passive', 'reachable', 'last_check',
                                  'check_interval', 'polling_interval', 'max_check_attempts']

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
        pass

    def main(self):
        """
        Main loop of the process

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
                                      self.server_cert, self.daemon_thread_pool_size)

        self.http_thread = threading.Thread(None, self.http_daemon_thread, 'http_thread')
        self.http_thread.daemon = True
        self.http_thread.start()
        logger.info("HTTP daemon thread started")

        # Polling period (-100 to get sure to poll on the first loop iteration)
        ping_alignak_next_time = time.time() - 100
        get_daemons_next_time = time.time() - 100

        # Endless loop...
        while not self.interrupted:
            now = time.time()

            if not self.alignak_host:
                time.sleep(0.5)
                continue

            if ping_alignak_next_time < now:
                ping_alignak_next_time = now + self.alignak_polling_period

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
            if self.alignak_is_alive and get_daemons_next_time < now:
                get_daemons_next_time = now + self.alignak_daemons_polling_period

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
                            self.daemons_map[daemon_type][daemon_name][prop] = daemon[prop]
                time.sleep(0.1)

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
    # Create an Alignak module
    mod = Module({
        'module_alias': 'external-commands',
        'module_types': 'external-commands',
        'python_name': 'alignak_module_external_commands',
        'file_path': '/tmp/my_external_commands_file'
    })
    instance = get_instance(mod)
    instance.main()
