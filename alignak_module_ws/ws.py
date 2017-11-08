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
import sys
import copy
import base64
import json
import time
import datetime
import logging
import threading
import Queue
import requests
import cherrypy

from alignak_backend_client.client import Backend, BackendException

# Used for the main function to run module independently
from alignak.objects.module import Module
from alignak.modulesmanager import ModulesManager

from alignak.external_command import ExternalCommand
from alignak.basemodule import BaseModule

from alignak_module_ws.utils.daemon import HTTPDaemon
from alignak_module_ws.utils.ws_server import WSInterface

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name
for handler in logger.parent.handlers:
    if isinstance(handler, logging.StreamHandler):
        logger.parent.removeHandler(handler)

# pylint: disable=invalid-name
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
        logger.setLevel(getattr(mod_conf, 'log_level', logging.INFO))

        logger.debug("inner properties: %s", self.__dict__)
        logger.debug("received configuration: %s", mod_conf.__dict__)
        logger.debug("loaded into: %s", self.loaded_into)

        self.token = None
        self.default_realm = None

        # Allow host/service creation
        self.allow_host_creation = getattr(mod_conf, 'allow_host_creation', '0') == '1'
        logger.info("Alignak host creation allowed: %s", self.allow_host_creation)
        self.ignore_unknown_host = getattr(mod_conf, 'ignore_unknown_host', '0') == '1'
        logger.info("Alignak unknown host is ignored: %s", self.ignore_unknown_host)

        self.allow_service_creation = getattr(mod_conf, 'allow_service_creation', '0') == '1'
        logger.info("Alignak service creation allowed: %s", self.allow_service_creation)
        self.ignore_unknown_service = getattr(mod_conf, 'ignore_unknown_service', '1') == '1'
        logger.info("Alignak unknown service is ignored: %s", self.ignore_unknown_service)

        # Set timestamp
        self.set_timestamp = getattr(mod_conf, 'set_timestamp', '1') == '1'
        logger.info("Alignak external commands, set timestamp: %s", self.set_timestamp)

        # Give some feedback when updating the host/services
        # 0: no feedback
        # 1: feedback only for host
        # 2: feedback for host and services
        self.give_feedback = int(getattr(mod_conf, 'give_feedback', '1'))
        logger.info("Alignak update, set give_feedback: %s", self.give_feedback)

        self.feedback_host = getattr(mod_conf, 'feedback_host', '')
        self.feedback_host = self.feedback_host.split(',')
        if self.feedback_host:
            logger.info("Alignak host feedback list: %s", self.feedback_host)

        self.feedback_service = getattr(mod_conf, 'feedback_service', '')
        self.feedback_service = self.feedback_service.split(',')
        if self.feedback_service:
            logger.info("Alignak service feedback list: %s", self.feedback_service)

        # Give some results of the executed commands
        self.give_result = getattr(mod_conf, 'give_result', '0') == '1'
        logger.info("Alignak update, set give_result: %s", self.give_result)

        # Alignak Backend part
        # ---
        self.backend = None
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
            self.backend_auto_login = False

            self.backend_username = getattr(mod_conf, 'username', '')
            self.backend_password = getattr(mod_conf, 'password', '')
            self.backend_generate = getattr(mod_conf, 'allowgeneratetoken', False)

            self.alignak_backend_polling_period = \
                int(getattr(mod_conf, 'alignak_backend_polling_period', '10'))

            self.alignak_backend_old_lcr = \
                getattr(mod_conf, 'alignak_backend_old_lcr', '0') == '1'

            self.alignak_backend_timeshift = \
                int(getattr(mod_conf, 'alignak_backend_timeshift', '5'))

            if not self.backend.token and not self.backend_username:
                logger.warning("No Alignak backend credentials configured (empty token and "
                               "empty username). "
                               "The backend connection will use the WS user credentials.")
                self.backend_url = ''
            else:
                self.backend_auto_login = True
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
            int(getattr(mod_conf, 'alignak_polling_period', '5'))
        logger.info("Alignak Arbiter polling period: %d", self.alignak_polling_period)
        self.alignak_daemons_polling_period = \
            int(getattr(mod_conf, 'alignak_daemons_polling_period', '10'))
        logger.info("Alignak daemons get status period: %d", self.alignak_daemons_polling_period)

        # SSL configuration
        self.use_ssl = getattr(mod_conf, 'use_ssl', '0') == '1'

        self.ca_cert = os.path.abspath(
            getattr(mod_conf, 'ca_cert', '/usr/local/etc/alignak/certs/ca.pem')
        )
        if self.use_ssl and not os.path.exists(self.ca_cert):
            logger.error('The CA certificate %s is missing (ca_cert). '
                         'Please fix it in your configuration', self.ca_cert)
            self.use_ssl = False

        self.server_cert = os.path.abspath(
            getattr(mod_conf, 'server_cert', '/usr/local/etc/alignak/certs/server.crt')
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
        self.log_error = getattr(mod_conf, 'log_error', '')
        self.log_access = getattr(mod_conf, 'log_access', '')

        protocol = 'http'
        if self.use_ssl:
            protocol = 'https'
        self.uri = '%s://%s:%s' % (protocol, self.host, self.port)
        logger.info("configuration, listening on: %s", self.uri)

        # HTTP authorization
        self.authorization = getattr(mod_conf, 'authorization', '1') == '1'
        if not self.authorization:
            logger.info("HTTP autorization is not enabled, this is not recommended. "
                        "You should consider enabling authorization!")

        # My own HTTP interface...
        cherrypy.config.update({"tools.wsauth.on": self.authorization})
        cherrypy.config.update({"tools.sessions.on": True})
        cherrypy.config.update({"tools.sessions.name": "alignak_ws"})
        if self.log_error:
            cherrypy.config.update({"log.error_file": "/tmp/alignak-module-ws-error.log"})
        if self.log_access:
            cherrypy.config.update({"log.access_file": "/tmp/alignak-module-ws-access.log"})
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

    def backendCreationData(self, host_name, service_name, data=None):
        """Returns the data that will be posted to the backend for host or service creation

        This function parses the provided data to find out some items that are already
        existing in the alignak backend. If some found, their name is replaced with the
        item identifier read from the backend

        :param host_name: host name
        :param service_name: service name (None for an host creation)
        :param data: posted data for the element creation
        :return: data to post on element creation
        """
        post_data = {}

        host_creation = True
        if service_name is not None:
            host_creation = False

        post_data['name'] = host_name
        if not host_creation:
            post_data['name'] = service_name

        if data is None:
            return post_data

        for field in data:
            logger.info("%s creation field: %s = %s",
                        'Host' if host_creation else 'Service', field, data[field])
            # Filter specific backend inner computed fields
            if field in ['_overall_state_id']:
                continue

            # Manage potential object link fields
            if field not in ['_realm', '_templates',
                             'command', 'host', 'service',
                             'escalation_period', 'maintenance_period',
                             'snapshot_period', 'check_period', 'dependency_period',
                             'notification_period', 'host_notification_period',
                             'host_notification_commands',
                             'service_notification_period',
                             'service_notification_commands',
                             'check_command', 'event_handler', 'grafana', 'statsd']:
                post_data[field] = data[field]
                continue

            field_values = data[field]
            if not isinstance(data[field], list):
                field_values = [data[field]]

            found = None
            for value in field_values:
                logger.debug(" - %s, single value: %s", field, value)
                try:
                    int(value, 16)

                    if not isinstance(data[field], list):
                        found = value
                    else:
                        if found is None:
                            found = []
                        found.append(value)
                except TypeError:
                    pass
                except ValueError:
                    # Not an integer, consider an item name
                    field_params = {'where': json.dumps({'name': value})}
                    if field in ['escalation_period', 'maintenance_period',
                                 'snapshot_period', 'check_period',
                                 'dependency_period', 'notification_period',
                                 'host_notification_period',
                                 'service_notification_period']:
                        response2 = self.backend.get('timeperiod', params=field_params)
                    elif field in ['_realm']:
                        response2 = self.backend.get('realm', params=field_params)
                    elif field in ['check_command', 'event_handler',
                                   'service_notification_commands',
                                   'host_notification_commands']:
                        response2 = self.backend.get('command', params=field_params)
                    elif field in ['_templates']:
                        field_params = {'where': json.dumps({'name': value,
                                                             '_is_template': True})}
                        if host_creation:
                            response2 = self.backend.get('host', params=field_params)
                        else:
                            response2 = self.backend.get('service', params=field_params)
                    else:
                        response2 = self.backend.get(field, params=field_params)

                    if response2['_items']:
                        response2 = response2['_items'][0]
                        logger.info("Replaced %s = %s with found item _id",
                                    field, value)
                        if not isinstance(data[field], list):
                            found = response2['_id']
                        else:
                            if found is None:
                                found = []
                            found.append(response2['_id'])

            if found is None:
                logger.warning("Not found %s = %s, ignoring field!", field, field_values)
            else:
                post_data[field] = found

        if '_realm' not in post_data and self.default_realm:
            logger.info("add default realm (%s) to the data", self.default_realm['_id'])
            post_data.update({'_realm': self.default_realm['_id']})

        if '_id' in post_data:
            post_data.pop('_id')

        logger.debug("post_data: %s", post_data)
        return post_data

    def getHostsGroup(self, name, embedded=False):
        # pylint: disable=too-many-nested-blocks
        """Get the specified hostgroup

        Search the hostgroup in the backend with its name

        If the hosts group exists, the hosts group data and members are returned back

        :param name: hosts group name
        :param embedded: True to embed the linked resources
        :return: hosts group properties
        """
        hostgroups = []

        ws_result = {'_status': 'OK', '_result': [], '_issues': []}
        try:
            if not self.backend_available:
                self.backend_available = self.getBackendAvailability()
            if not self.backend_available:
                ws_result['_status'] = 'ERR'
                ws_result['_issues'].append("Alignak backend is not available currently. "
                                            "Hosts group information cannot be fetched.")
                return ws_result

            search = {
                'where': json.dumps({'name': name}),
                'projection': json.dumps({
                    "name": 1, "alias": 1, "notes": 1,
                    "hostgroups": 1, "hosts": 1,
                    "_level": 1, "_parent": 1, "_tree_parents": 1,
                    '_realm': 1,
                }),
                'embedded': json.dumps({
                    "hostgroups": 1, "hosts": 1,
                    "_parent": 1, "_tree_parents": 1,
                    '_realm': 1,
                })
            }
            if name is None:
                del search['where']
            if not embedded:
                del search['embedded']
            logger.debug("Get hostgroup, parameters: %s", search)
            result = self.backend.get_all('/hostgroup', params=search)
            logger.debug("Get hostgroup, got: %s", result)
            if not result['_items']:
                ws_result['_status'] = 'ERR'
                ws_result['_issues'].append("Requested hostgroup '%s' does not exist" % name)
                return ws_result

            hostgroups = []
            for item in result['_items']:
                # Remove some backend inner fields
                # item.pop('_id')
                item.pop('_etag')
                item.pop('_links')
                # item.pop('_updated')

                # Remove not interesting content from linked elements
                if embedded:
                    # For embedded items, only return their name and alias properties
                    for embedded_item in ['_realm', 'hosts', 'hostgroups',
                                          '_tree_parents', '_parent']:
                        if isinstance(item[embedded_item], list):
                            for linked_item in item[embedded_item]:
                                item_copy = copy.copy(linked_item)
                                for prop in item_copy:
                                    if prop not in ['name', 'alias']:
                                        linked_item.pop(prop)
                        else:
                            item_copy = copy.copy(item[embedded_item])
                            for prop in item_copy:
                                if prop not in ['name', 'alias']:
                                    item[embedded_item].pop(prop)
                hostgroups.append(item)
        except BackendException as exp:  # pragma: no cover, should not happen
            logger.warning("Alignak backend exception, getHostgroup.")
            logger.warning("Exception: %s", exp)
            logger.warning("Exception response: %s", exp.response)
            ws_result['_status'] = 'ERR'
            ws_result['_issues'].append("Alignak backend error. Exception, getHost: %s"
                                        % str(exp))
            ws_result['_issues'].append("Alignak backend error. Response: %s" % exp.response)
            return ws_result

        ws_result['_result'] = hostgroups
        ws_result.pop('_issues')
        return ws_result

    def getHost(self, host_name):
        """Get the specified host

        Search the host in the backend with its name

        If the host exists, the host data are returned back

        :param host_name: host name
        :return: host properties
        """
        hosts = []

        ws_result = {'_status': 'OK', '_result': [], '_issues': []}
        try:
            search = {
                'where': json.dumps({'name': host_name}),
                'embedded': json.dumps({
                    '_realm': 1, '_templates': 1,
                    'check_command': 1, 'snapshot_command': 1, 'event_handler': 1,
                    'check_period': 1, 'notification_period': 1,
                    'snapshot_period': 1, 'maintenance_period': 1,
                    'parents': 1, 'hostgroups': 1, 'users': 1, 'usergroups': 1
                })
            }
            logger.debug("Get host, parameters: %s", search)
            result = self.backend.get_all('/host', params=search)
            logger.debug("Get host, got: %s", result)
            if not result['_items']:
                ws_result['_status'] = 'ERR'
                ws_result['_issues'].append("Requested host '%s' does not exist" % host_name)
                return ws_result

            hosts = result['_items']
        except BackendException as exp:  # pragma: no cover, should not happen
            logger.warning("Alignak backend exception, getHost.")
            logger.warning("Exception: %s", exp)
            logger.warning("Exception response: %s", exp.response)
            ws_result['_status'] = 'ERR'
            ws_result['_issues'].append("Alignak backend error. Exception, getHost: %s"
                                        % str(exp))
            ws_result['_issues'].append("Alignak backend error. Response: %s" % exp.response)
            return ws_result

        ws_result['_result'] = hosts
        ws_result.pop('_issues')
        return ws_result

    def updateHost(self, host_name, data):
        # pylint: disable=too-many-locals, too-many-return-statements
        """Create/update the specified host

        Search the host in the backend
        If the host is not found, and the module is configured to create missing hosts, the
        function tries to create a new host with the provided data as parameters.
        If the creation fails it returns and error message

        If the host exists, it is updated with the provided data.

        :param host_name: host name
        :param data: dictionary of the host properties to be modified
        :return: command line
        """
        host = None

        ws_result = {'_status': 'OK', '_result': ['%s is alive :)' % host_name],
                     '_issues': []}
        try:
            if not self.backend_available:
                self.backend_available = self.getBackendAvailability()
            if not self.backend_available:
                ws_result['_status'] = 'ERR'
                ws_result['_issues'].append("Alignak backend is not available currently. "
                                            "Host properties cannot be modified.")
                return ws_result

            result = self.backend.get('/host', {'where': json.dumps({'name': host_name})})
            logger.debug("Get host, got: %s", result)
            if not result['_items']:
                if not self.allow_host_creation:
                    if not self.ignore_unknown_host:
                        ws_result['_status'] = 'ERR'
                        ws_result['_issues'].append("Requested host '%s' does not exist"
                                                    % host_name)
                    else:
                        ws_result['_result'] = ["Requested host '%s' does not exist" % host_name]
                    return ws_result

            if not result['_items'] and self.allow_host_creation:
                # Tries to create the host
                logger.info("Requested host '%s' does not exist. Trying to create a new host",
                            host_name)
                ws_result['_result'].append("Requested host '%s' does not exist." % host_name)

                if 'template' not in data:
                    data['template'] = None

                # Request data for host creation (no service)
                post_data = self.backendCreationData(host_name, None, data['template'])
                logger.debug("Post host, data: %s", post_data)
                logger.info("Post Backend: %s", self.backend.__dict__)
                result = self.backend.post('host', data=post_data)
                logger.debug("Post host, response: %s", result)
                if result['_status'] != 'OK':
                    logger.warning("Post host, error: %s", result)
                    ws_result['_status'] = 'ERR'
                    ws_result['_issues'].append("Requested host '%s' creation failed." % host_name)
                    return ws_result

                # Get the newly created host
                ws_result['_result'].append("Requested host '%s' created." % host_name)
                host = self.backend.get('/'.join(['host', result['_id']]))
                logger.debug("Get host, got: %s", host)
                logger.info("Created a new host: %s", host_name)
            else:
                host = result['_items'][0]
        except BackendException as exp:  # pragma: no cover, should not happen
            logger.warning("Alignak backend exception for updateHost: %s", exp.response)
            ws_result['_status'] = 'ERR'
            ws_result['_issues'].append("Alignak backend error. Exception, updateHost: %s"
                                        % str(exp))
            ws_result['_issues'].append("Alignak backend error. Response: %s" % exp.response)
            return ws_result

        update = None
        logger.debug("Got host: %s", host)

        # Update host check state
        if 'active_checks_enabled' in data:
            if isinstance(data['active_checks_enabled'], bool):
                update = False
                if data['active_checks_enabled'] != host['active_checks_enabled']:
                    update = True

                    # todo: perharps this command is not useful because the backend is updated...
                    command_line = 'DISABLE_HOST_CHECK;%s' % host_name
                    if data['active_checks_enabled']:
                        command_line = 'ENABLE_HOST_CHECK;%s' % host_name
                        ws_result['_result'].append(
                            'Host %s active checks will be enabled.' % host_name)
                    else:
                        ws_result['_result'].append(
                            'Host %s active checks will be disabled.' % host_name)

                    # Add a command to get managed
                    if self.set_timestamp:
                        command_line = '[%d] %s' % (time.time(), command_line)
                    ws_result['_result'].append('Sent external command: %s.' % command_line)
                    logger.debug("Sending command: %s", command_line)
                    self.to_q.put(ExternalCommand(command_line))
            else:
                data.pop('active_checks_enabled')

        if 'passive_checks_enabled' in data:
            if isinstance(data['passive_checks_enabled'], bool):
                if update is None:
                    update = False
                if data['passive_checks_enabled'] != host['passive_checks_enabled']:
                    update = True

                    # todo: perharps this command is not useful because the backend is updated...
                    command_line = 'DISABLE_PASSIVE_HOST_CHECKS;%s' % host_name
                    if data['passive_checks_enabled']:
                        command_line = 'ENABLE_PASSIVE_HOST_CHECKS;%s' % host_name
                        ws_result['_result'].append(
                            'Host %s passive checks will be enabled.' % host_name)
                    else:
                        ws_result['_result'].append(
                            'Host %s passive checks will be disabled.' % host_name)

                    # Add a command to get managed
                    if self.set_timestamp:
                        command_line = '[%d] %s' % (time.time(), command_line)
                    ws_result['_result'].append('Sent external command: %s.' % command_line)
                    logger.debug("Sending command: %s", command_line)
                    self.to_q.put(ExternalCommand(command_line))
            else:
                data.pop('passive_checks_enabled')

        # Update host variables
        if data['variables']:
            if update is None:
                update = False
            customs = host['customs']
            for prop in data['variables']:
                value = data['variables'][prop]
                logger.debug("Variable: %s = %s, update: %s", prop, value, update)
                custom = '_' + prop.upper()
                if isinstance(value, list):
                    if custom in customs:
                        if all(isinstance(x, dict) for x in value):
                            # List of dictionaries
                            pairs = zip(value, customs[custom])
                            diff = [(x, y) for x, y in pairs if x != y]
                        else:
                            diff = list(set(value) - set(customs[custom]))

                        if diff:
                            update = True
                            logger.info("Modified list: %s, difference: %s (%s vs %s)",
                                        prop, diff, value, customs[custom])
                            customs[custom] = value
                    else:
                        update = True
                        logger.info("Create list: %s = %s", prop, value)
                        customs[custom] = value
                else:
                    if custom in customs and value == "__delete__":
                        update = True
                        logger.info("Delete variable: %s", prop)
                        customs.pop(custom)
                    else:
                        if custom not in customs or customs[custom] != value:
                            update = True
                            logger.info("Update variable: %s = %s", prop, value)
                            customs[custom] = value
            if update:
                data['customs'] = customs

        # Update host livestate
        if data['livestate']:
            if not isinstance(data['livestate'], list):
                data['livestate'] = [data['livestate']]
            for livestate in data['livestate']:
                if 'state' not in livestate:
                    ws_result['_issues'].append('Missing state in the livestate.')
                else:
                    state = livestate.get('state', 'UP').upper()
                    if state not in ['UP', 'DOWN', 'UNREACHABLE']:
                        ws_result['_issues'].append("Host state must be UP, DOWN or UNREACHABLE"
                                                    ", and not '%s'." % (state))
                    else:
                        ws_result['_result'].append(self.buildHostLivestate(host,
                                                                            livestate))

        # Update host services
        if data['services']:
            if '_feedback' not in ws_result:
                ws_result['_feedback'] = {}
            ws_result['_feedback']['services'] = []
            for service in data['services']:
                service_name = service.get('name', None)
                if service_name is None:
                    ws_result['_issues'].append("A service does not have a 'name' property")
                    continue
                service.pop('name')
                result = self.updateService(host, service_name, service)
                if '_result' in result:
                    ws_result['_result'].extend(result['_result'])
                if '_issues' in result:
                    ws_result['_issues'].extend(result['_issues'])
                else:
                    if '_feedback' in result:
                        ws_result['_feedback']['services'].append(result['_feedback'])
            if not ws_result['_feedback']['services']:
                ws_result['_feedback'].pop('services')

        # If no data update requested (only livestate in the data...)
        if update is None:
            # Simple host alive without any required update
            logger.debug("No host update, only livestate: %s / %s",
                         self.give_result, self.give_feedback)
            if ws_result['_issues']:
                if not self.give_feedback and '_feedback' in ws_result:
                    ws_result.pop('_feedback')
                ws_result['_status'] = 'ERR'
                return ws_result

            if self.give_feedback:
                host = self.backend.get('/'.join(['host', host['_id']]))
                if '_feedback' not in ws_result:
                    ws_result['_feedback'] = {}
                ws_result['_feedback'].update({'name': host['name']})
                for prop in host:
                    if prop in self.feedback_host:
                        ws_result['_feedback'].update({prop: host[prop]})
            else:
                if '_feedback' in ws_result:
                    ws_result.pop('_feedback')

            if not self.give_result:
                ws_result.pop('_result')

            ws_result.pop('_issues')
            logger.debug("Result: %s", ws_result)
            return ws_result

        # If no update needed
        if not update:
            # Simple host alive with updates required but no update needed
            logger.debug("No host update: %s / %s",
                         self.give_result, self.give_feedback)
            ws_result['_result'].append("Host '%s' unchanged." % host['name'])
            if ws_result['_issues']:
                if not self.give_feedback and '_feedback' in ws_result:
                    ws_result.pop('_feedback')
                ws_result['_status'] = 'ERR'
                return ws_result

            if self.give_feedback:
                host = self.backend.get('/'.join(['host', host['_id']]))
                if '_feedback' not in ws_result:
                    ws_result['_feedback'] = {}
                ws_result['_feedback'].update({'name': host['name']})
                for prop in host:
                    if prop in self.feedback_host:
                        ws_result['_feedback'].update({prop: host[prop]})
            else:
                if '_feedback' in ws_result:
                    ws_result.pop('_feedback')

            if not self.give_result:
                ws_result.pop('_result')

            ws_result.pop('_issues')
            logger.debug("Result: %s", ws_result)
            return ws_result

        # Clean data to be posted
        if 'template' in data:
            data.pop('template')
        if 'livestate' in data:
            data.pop('livestate')
        if 'variables' in data:
            data.pop('variables')
        if 'services' in data:
            data.pop('services')

        try:
            headers = {'If-Match': host['_etag']}
            logger.info("Updating host '%s': %s", host_name, data)
            patch_result = self.backend.patch('/'.join(['host', host['_id']]),
                                              data=data, headers=headers, inception=True)
            logger.debug("Backend patch, result: %s", patch_result)
            if patch_result['_status'] != 'OK':
                logger.warning("Host patch, got a problem: %s", result)
                return ('ERR', patch_result['_issues'])

            if self.give_feedback:
                host = self.backend.get('/'.join(['host', host['_id']]))
                if '_feedback' not in ws_result:
                    ws_result['_feedback'] = {}
                ws_result['_feedback'].update({'name': host['name']})
                for prop in host:
                    if prop in self.feedback_host:
                        ws_result['_feedback'].update({prop: host[prop]})
            else:
                if '_feedback' in ws_result:
                    ws_result.pop('_feedback')

        except BackendException as exp:  # pragma: no cover, should not happen
            logger.warning("Alignak backend is currently not available.")
            logger.warning("Exception: %s", exp)
            self.backend_available = False
            return ('ERR', "Host update error, backend exception. "
                           "Get exception: %s" % str(exp))

        ws_result['_result'].append("Host '%s' updated." % host['name'])

        if ws_result['_issues']:
            ws_result['_status'] = 'ERR'
            if '_feedback' in ws_result:
                ws_result.pop('_feedback')
            return ws_result

        if not self.give_result:
            ws_result.pop('_result')

        ws_result.pop('_issues')
        return ws_result

    def updateService(self, host, service_name, data):
        # pylint: disable=too-many-locals,too-many-return-statements
        """Create/update the custom variables for the specified service

        Search the service in the backend and update its custom variables with the provided ones.

        :param host: host data
        :param service_name: service description
        :param data: dictionary of the service data to be modified
        :return: (status, message) tuple
        """
        service = None

        ws_result = {'_status': 'OK', '_result': [], '_issues': []}
        try:
            if not self.backend_available:
                self.backend_available = self.getBackendAvailability()
            if not self.backend_available:
                ws_result['_status'] = 'ERR'
                ws_result['_issues'].append("Alignak backend is not available currently. "
                                            "Service properties cannot be modified.")
                return ws_result

            result = self.backend.get('/service', {'where': json.dumps({'host': host['_id'],
                                                                        'name': service_name})})
            logger.debug("Get service, got: %s", result)
            if not result['_items']:
                if not self.allow_service_creation:
                    if not self.ignore_unknown_service:
                        ws_result['_status'] = 'ERR'
                        ws_result['_issues'].append("Requested service '%s/%s' does not exist"
                                                    % (host['name'], service_name))
                    else:
                        ws_result['_result'].append("Requested service '%s/%s' does not exist"
                                                    % (host['name'], service_name))
                    return ws_result

            if not result['_items'] and self.allow_service_creation:
                # Tries to create the service
                logger.info("Requested service '%s/%s' does not exist. "
                            "Trying to create a new service",
                            host['name'], service_name)
                ws_result['_result'].append("Requested service '%s/%s' does not exist."
                                            % (host['name'], service_name))

                if 'template' not in data:
                    data['template'] = None

                # Request data for service creation
                post_data = self.backendCreationData(host['name'], service_name, data['template'])
                post_data.update({'host': host['_id']})
                logger.debug("Post service, data: %s", post_data)
                result = self.backend.post('service', data=post_data)
                logger.debug("Post service, response: %s", result)
                if result['_status'] != 'OK':
                    logger.warning("Post service, error: %s", result)
                    ws_result['_status'] = 'ERR'
                    ws_result['_issues'].append("Requested service '%s/%s' creation failed."
                                                % (host['name'], service_name))
                    return ws_result

                # Get the newly created service
                ws_result['_result'].append("Requested service '%s/%s' created."
                                            % (host['name'], service_name))
                service = self.backend.get('/'.join(['service', result['_id']]))
                logger.debug("Get service, got: %s", service)
            else:
                service = result['_items'][0]
        except BackendException as exp:  # pragma: no cover, should not happen
            logger.warning("Alignak backend exception, updateService.")
            logger.warning("Exception: %s", exp)
            logger.warning("Exception response: %s", exp.response)
            ws_result['_status'] = 'ERR'
            ws_result['_issues'].append("Alignak backend error. Exception, updateService: %s"
                                        % str(exp))
            ws_result['_issues'].append("Alignak backend error. Response: %s" % exp.response)
            return ws_result

        update = None

        # Update service check state
        if 'active_checks_enabled' in data:
            if isinstance(data['active_checks_enabled'], bool):
                update = False
                if data['active_checks_enabled'] != service['active_checks_enabled']:
                    update = True

                    # todo: perharps this command is not useful because the backend is updated...
                    command_line = 'DISABLE_SVC_CHECK;%s;%s' % (host['name'], service_name)
                    if data['active_checks_enabled']:
                        command_line = 'ENABLE_SVC_CHECK;%s;%s' % (host['name'], service_name)
                        ws_result['_result'].append('Service %s/%s active checks will be enabled.'
                                                    % (host['name'], service_name))
                    else:
                        ws_result['_result'].append('Service %s/%s active checks will be disabled.'
                                                    % (host['name'], service_name))

                    # Add a command to get managed
                    if self.set_timestamp:
                        command_line = '[%d] %s' % (time.time(), command_line)
                    ws_result['_result'].append('Sent external command: %s.' % command_line)
                    logger.debug("Sending command: %s", command_line)
                    self.to_q.put(ExternalCommand(command_line))
            else:
                data.pop('active_checks_enabled')

        if 'passive_checks_enabled' in data:
            if isinstance(data['passive_checks_enabled'], bool):
                if update is None:
                    update = False
                if data['passive_checks_enabled'] != service['passive_checks_enabled']:
                    update = True

                    # todo: perharps this command is not useful because the backend is updated...
                    command_line = 'DISABLE_PASSIVE_SVC_CHECKS;%s;%s' % (host['name'], service_name)
                    if data['passive_checks_enabled']:
                        command_line = 'ENABLE_PASSIVE_SVC_CHECKS;%s;%s' \
                                       % (host['name'], service_name)
                        ws_result['_result'].append('Service %s/%s passive checks will be enabled.'
                                                    % (host['name'], service_name))
                    else:
                        ws_result['_result'].append('Service %s/%s passive checks will be disabled.'
                                                    % (host['name'], service_name))

                    # Add a command to get managed
                    if self.set_timestamp:
                        command_line = '[%d] %s' % (time.time(), command_line)
                    ws_result['_result'].append('Sent external command: %s.' % command_line)
                    logger.debug("Sending command: %s", command_line)
                    self.to_q.put(ExternalCommand(command_line))
            else:
                data.pop('passive_checks_enabled')

        # Update service variables
        if 'variables' in data and data['variables']:
            if update is None:
                update = False
            customs = host['customs']
            for prop in data['variables']:
                value = data['variables'][prop]
                custom = '_' + prop.upper()
                if isinstance(value, list):
                    if custom not in customs or cmp(customs[custom], value) == 0:
                        update = True
                        customs[custom] = value
                else:
                    if custom in customs and value == "__delete__":
                        update = True
                        customs.pop(custom)
                    else:
                        if custom not in customs or customs[custom] != value:
                            update = True
                            customs[custom] = value
            if update:
                data['customs'] = customs

        # Update service livestate
        if 'livestate' in data and data['livestate']:
            if not isinstance(data['livestate'], list):
                data['livestate'] = [data['livestate']]
            for livestate in data['livestate']:
                if 'state' not in livestate:
                    ws_result['_issues'].append('Missing state in the livestate.')
                else:
                    state = livestate.get('state', 'OK').upper()
                    if state not in ['OK', 'WARNING', 'CRITICAL', 'UNKNOWN', 'UNREACHABLE']:
                        ws_result['_issues'].append("Service %s state must be OK, WARNING, "
                                                    "CRITICAL, UNKNOWN or UNREACHABLE, and not %s."
                                                    % (service_name, state))
                    else:
                        ws_result['_result'].append(self.buildServiceLivestate(host, service,
                                                                               livestate))

        # If no data update requested (only livestate in the data...)
        if update is None:
            logger.debug("No service update, only livestate: %s / %s",
                         self.give_result, self.give_feedback)
            # Simple service alive without any required update
            if ws_result['_issues']:
                ws_result['_status'] = 'ERR'
                return ws_result

            if self.give_feedback > 1:
                service = self.backend.get('/'.join(['service', service['_id']]))
                if '_feedback' not in ws_result:
                    ws_result['_feedback'] = {}
                ws_result['_feedback'].update({'name': service['name']})
                for prop in host:
                    if prop in self.feedback_service:
                        ws_result['_feedback'].update({prop: service[prop]})
            else:
                if '_feedback' in ws_result:
                    ws_result.pop('_feedback')

            ws_result.pop('_issues')
            return ws_result

        # If no update needed
        if not update:
            # Simple service alive with updates required but no update needed
            logger.debug("No service update: %s / %s",
                         self.give_result, self.give_feedback)
            ws_result['_result'].append("Service '%s/%s' unchanged."
                                        % (host['name'], service_name))
            if ws_result['_issues']:
                ws_result['_status'] = 'ERR'
                return ws_result

            if self.give_feedback > 1:
                service = self.backend.get('/'.join(['service', service['_id']]))
                if '_feedback' not in ws_result:
                    ws_result['_feedback'] = {}
                ws_result['_feedback'].update({'name': service['name']})
                for prop in host:
                    if prop in self.feedback_service:
                        ws_result['_feedback'].update({prop: service[prop]})
            else:
                if '_feedback' in ws_result:
                    ws_result.pop('_feedback')

            ws_result.pop('_issues')
            return ws_result

        # Clean data to be posted
        if 'template' in data:
            data.pop('template')
        if 'livestate' in data:
            data.pop('livestate')
        if 'variables' in data:
            data.pop('variables')
        try:
            headers = {'If-Match': service['_etag']}
            logger.info("Updating service '%s/%s': %s", host['name'], service_name, data)
            patch_result = self.backend.patch('/'.join(['service', service['_id']]),
                                              data=data, headers=headers, inception=True)
            logger.debug("Backend patch, result: %s", patch_result)
            if patch_result['_status'] != 'OK':
                logger.warning("Service patch, got a problem: %s", result)
                return ('ERR', patch_result['_issues'])

            if self.give_feedback > 1:
                service = self.backend.get('/'.join(['service', service['_id']]))
                if '_feedback' not in ws_result:
                    ws_result['_feedback'] = {}
                ws_result['_feedback'].update({'name': service['name']})
                for prop in host:
                    if prop in self.feedback_service:
                        ws_result['_feedback'].update({prop: service[prop]})
            else:
                if '_feedback' in ws_result:
                    ws_result.pop('_feedback')

        except BackendException as exp:  # pragma: no cover, should not happen
            logger.warning("Alignak backend is currently not available.")
            logger.warning("Exception: %s", exp)
            self.backend_available = False
            return ('ERR', "Service update error, backend exception. "
                           "Get exception: %s" % str(exp))

        ws_result['_result'].append("Service '%s/%s' updated" % (host['name'], service_name))

        if ws_result['_issues']:
            ws_result['_status'] = 'ERR'
            return ws_result

        ws_result.pop('_issues')
        return ws_result

    def buildPostComment(self, host_name, service_name, author, comment, timestamp):
        # pylint: disable=too-many-arguments
        """Build the external command for an host comment

        ADD_HOST_COMMENT;<host_name>;<persistent>;<author>;<comment>

        :param host_name: host name
        :param service_name: service description
        :param author: comment author
        :param comment: text comment
        :return: command line
        """
        if service_name:
            command_line = 'ADD_SVC_COMMENT'
            if timestamp:
                command_line = '[%d] ADD_SVC_COMMENT' % (timestamp)

            command_line = '%s;%s;%s;1;%s;%s' % (command_line, host_name, service_name,
                                                 author, comment)
        else:
            command_line = 'ADD_HOST_COMMENT'
            if timestamp:
                command_line = '[%d] ADD_HOST_COMMENT' % (timestamp)

            command_line = '%s;%s;1;%s;%s' % (command_line, host_name,
                                              author, comment)

        # Add a command to get managed
        logger.debug("Sending command: %s", command_line)
        self.to_q.put(ExternalCommand(command_line))

        result = {'_status': 'OK', '_result': [command_line], '_issues': []}

        try:
            if not self.backend_available:
                self.backend_available = self.getBackendAvailability()
            if not self.backend_available:
                logger.warning("Alignak backend is not available currently. "
                               "Comment not stored: %s", command_line)

            data = {
                "host_name": host_name,
                "user_name": author,
                "type": "webui.comment",
                "message": comment
            }
            logger.debug("Posting an event: %s", data)
            post_result = self.backend.post('history', data)
            logger.debug("Backend post, result: %s", post_result)
            if post_result['_status'] != 'OK':
                logger.warning("history post, got a problem: %s", result)
                result['_issues'] = post_result['_issues']
        except BackendException as exp:  # pragma: no cover, should not happen
            logger.warning("Alignak backend is currently not available.")
            logger.warning("Exception: %s", exp)
            logger.warning("Response: %s", exp.response)
            result['_issues'] = str(exp) + ' - ' + exp.response
            self.backend_available = False

        if result['_issues']:
            result['_status'] = 'ERR'
            return result

        result.pop('_issues')
        return result

    def buildHostLivestate(self, host, livestate):
        # pylint: disable=too-many-locals
        """Build and notify the external command for an host livestate

        PROCESS_HOST_CHECK_RESULT;<host_name>;<status_code>;<plugin_output>

        Create and post a logcheckresult to the backend if the timestamp is in the past

        :param host: host from the Alignak backend
        :param livestate: livestate dictionary
        :return: command line
        """
        state = livestate.get('state', 'UP').upper()
        output = livestate.get('output', '')
        long_output = livestate.get('long_output', '')
        perf_data = livestate.get('perf_data', '')
        try:
            timestamp = int(livestate.get('timestamp', 'ABC'))
        except ValueError:
            timestamp = None

        state_to_id = {
            "UP": 0,
            "DOWN": 1,
            "UNREACHABLE": 2
        }

        parameters = '%s;%s' % (state_to_id[state], output)
        if long_output and perf_data:
            parameters = '%s|%s\n%s' % (parameters, perf_data, long_output)
        elif long_output:
            parameters = '%s\n%s' % (parameters, long_output)
        elif perf_data:
            parameters = '%s|%s' % (parameters, perf_data)

        command_line = 'PROCESS_HOST_CHECK_RESULT;%s;%s' % (host['name'], parameters)
        if timestamp is not None:
            command_line = '[%d] %s' % (timestamp, command_line)
        elif self.set_timestamp:
            command_line = '[%d] %s' % (time.time(), command_line)

        # Add a command to get managed
        _ts = time.time()
        logger.debug("Sending command: %s", command_line)
        self.to_q.put(ExternalCommand(command_line))
        logger.debug("Sent command, duration: %s", time.time() - _ts)

        # -------------------------------------------
        # Add a check result for an host if we got a timestamp in the past
        # A passive check with a timestamp older than the host last check data will not be
        # managed by Alignak but we may track this event in the backend logcheckresult
        if self.alignak_backend_old_lcr:
            if timestamp and \
                    (not host['ls_last_check'] or
                     timestamp + self.alignak_backend_timeshift < host['ls_last_check']):
                _ts = time.time()
                past = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                logger.info("Recording a check result from the past (%s) for %s...",
                            past, host['name'])
                # Assume data are in the host livestate
                data = {
                    "last_check": timestamp,
                    "host": host['_id'],
                    "service": None,
                    'acknowledged': host['ls_acknowledged'],
                    'acknowledgement_type': host['ls_acknowledgement_type'],
                    'downtimed': host['ls_downtimed'],
                    'state_id': state_to_id[state],
                    'state': state,
                    'state_type': host['ls_state_type'],
                    'last_state': host['ls_last_state'],
                    'last_state_type': host['ls_last_state_type'],
                    'latency': 0,
                    'execution_time': 0,
                    'output': output,
                    'long_output': long_output,
                    'perf_data': perf_data,
                    "_realm": host['_realm']
                }
                result = self.backend.get('/logcheckresult',
                                          {'max_results': 1,
                                           'where': json.dumps({'host_name': host['name'],
                                                                'last_check': {
                                                                    "$lte": timestamp}})})
                logger.debug("Get logcheckresult, got: %s", result)
                if result['_items']:
                    lcr = result['_items'][0]
                    logger.info("Updating data from an existing logcheckresult: %s", lcr)
                    # Assume some data are in the most recent check result
                    data.update({
                        'acknowledged': lcr['acknowledged'],
                        'acknowledgement_type': lcr['acknowledgement_type'],
                        'downtimed': lcr['downtimed'],
                        'state_type': lcr['state_type'],
                        'last_state': lcr['last_state'],
                        'last_state_type': lcr['last_state_type'],
                        'state_changed': lcr['state_changed']
                    })

                result = self.backend.post('/logcheckresult', data)
                if result['_status'] != 'OK':
                    logger.warning("Post logcheckresult, error: %s", result)
                else:
                    logger.info("Recorded, duration: %s", time.time() - _ts)

        return command_line

    def buildServiceLivestate(self, host, service, livestate):
        # pylint: disable=too-many-locals
        """Build and notify the external command for a service livestate

        PROCESS_SERVICE_CHECK_RESULT;<host_name>;<service_description>;<return_code>;<plugin_output>

        Create and post a logcheckresult to the backend if the timestamp is in the past

        :param host: host from the Alignak backend
        :param service: service from the Alignak backend
        :param livestate: livestate dictionary
        :return: command line
        """
        state = livestate.get('state', 'OK').upper()
        output = livestate.get('output', '')
        long_output = livestate.get('long_output', '')
        perf_data = livestate.get('perf_data', '')
        try:
            timestamp = int(livestate.get('timestamp', 'ABC'))
        except ValueError:
            timestamp = None

        state_to_id = {
            "OK": 0,
            "WARNING": 1,
            "CRITICAL": 2,
            "UNKNOWN": 3,
            "UNREACHABLE": 4
        }

        parameters = '%s;%s' % (state_to_id[state], output)
        if long_output and perf_data:
            parameters = '%s|%s\n%s' % (parameters, perf_data, long_output)
        elif long_output:
            parameters = '%s\n%s' % (parameters, long_output)
        elif perf_data:
            parameters = '%s|%s' % (parameters, perf_data)

        command_line = 'PROCESS_SERVICE_CHECK_RESULT;%s;%s;%s' % \
                       (host['name'], service['name'], parameters)
        if timestamp is not None:
            command_line = '[%d] %s' % (timestamp, command_line)
        elif self.set_timestamp:
            command_line = '[%d] %s' % (time.time(), command_line)

        # Add a command to get managed
        _ts = time.time()
        logger.debug("Sending command: %s", command_line)
        self.to_q.put(ExternalCommand(command_line))
        logger.debug("Sent command, duration: %s", time.time() - _ts)

        # -------------------------------------------
        # Add a check result for a service if we got a timestamp in the past
        # A passive check with a timestamp older than the service last check data will not be
        # managed by Alignak but we may track this event in the backend logcheckresult
        if self.alignak_backend_old_lcr:
            if timestamp and \
                    (not service['ls_last_check'] or
                     timestamp + self.alignak_backend_timeshift < service['ls_last_check']):
                _ts = time.time()
                past = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                logger.info("Recording a check result from the past (%s) for %s/%s...",
                            past, host['name'], service['name'])
                # Assume data are in the service livestate
                data = {
                    "last_check": timestamp,
                    "host": host['_id'],
                    "service": service['_id'],
                    'acknowledged': service['ls_acknowledged'],
                    'acknowledgement_type': service['ls_acknowledgement_type'],
                    'downtimed': service['ls_downtimed'],
                    'state_id': state_to_id[state],
                    'state': state,
                    'state_type': service['ls_state_type'],
                    'last_state': service['ls_last_state'],
                    'last_state_type': service['ls_last_state_type'],
                    'latency': 0,
                    'execution_time': 0,
                    'output': output,
                    'long_output': long_output,
                    'perf_data': perf_data,
                    "_realm": service['_realm']
                }
                result = self.backend.get('/logcheckresult',
                                          {'max_results': 1,
                                           'where': json.dumps({'host_name': host['name'],
                                                                'service_name': service['name'],
                                                                'last_check': {
                                                                    "$lte": timestamp}})})
                if self.alignak_backend_old_lcr:
                    logger.debug("Get logcheckresult, got: %s", result)
                    if result['_items']:
                        lcr = result['_items'][0]
                        logger.debug("Updating data from an existing logcheckresult: %s", lcr)
                        # Assume some data are in the most recent check result
                        data.update({
                            'acknowledged': lcr['acknowledged'],
                            'acknowledgement_type': lcr['acknowledgement_type'],
                            'downtimed': lcr['downtimed'],
                            'state_type': lcr['state_type'],
                            'last_state': lcr['last_state'],
                            'last_state_type': lcr['last_state_type'],
                            'state_changed': lcr['state_changed']
                        })

                result = self.backend.post('/logcheckresult', data)
                if result['_status'] != 'OK':
                    logger.warning("Post logcheckresult, error: %s", result)
                else:
                    logger.info("Recorded, duration: %s", time.time() - _ts)

        return command_line

    def backendLogin(self, username, password):
        """Authenticate and get the backend token

        :return: None
        """
        logger.debug("backendLogin, available: %s, credentials: %s / %s",
                     self.backend_available, username, password)
        if not password:
            # We consider that we received a backend token as login. The WS user is logged-in...
            logger.debug("backendLogin, using token: %s", username)
            self.token = self.backend.token = username
            return self.token

        self.token = None
        self.default_realm = None

        try:
            logger.info("Logging to the backend, username: %s", username)
            if self.backend.login(username, password):
                self.token = self.backend.token
                logger.debug("Logged-in to the backend, token: %s", self.token)

                # Get the higher level realm for the current logger-in user
                # This realm identifier will be used when it is necessary to provide a realm
                # (eg. for new objects creation)
                result = self.backend.get('/realm', {'max_results': 1, 'sort': '_level'})
                self.default_realm = result['_items'][0]
                logger.debug("Got default realm: %s", self.default_realm)
        except BackendException as exp:  # pragma: no cover, should not happen
            logger.warning("Alignak backend is currently not available.")
            logger.warning("Exception: %s", exp)
            logger.warning("Response: %s", exp.response)

        return self.token

    def getBackendAvailability(self):
        """Authenticate and get the backend token

        :return: None
        """
        generate = 'enabled'
        if not self.backend_generate:
            generate = 'disabled'

        self.backend_available = False
        try:
            self.backendCheck = Backend(self.backend_url, self.client_processes)

            logger.info("Signing-in to the backend (%s)...", self.backend_username)
            self.backend_available = self.backendCheck.login(self.backend_username,
                                                             self.backend_password, generate)
            logger.debug("Checking backend availability, token: %s, authenticated: %s",
                         self.backendCheck.token, self.backendCheck.authenticated)
            # Get top level realm
            result = self.backendCheck.get('/realm', {'max_results': 1, 'sort': '_level'})
            logger.info("Backend availability, got default realm: %s", result['_items'][0])
            self.backend_available = True
        except BackendException as exp:  # pragma: no cover, should not happen
            logger.warning("Alignak backend is currently not available.")
            logger.warning("Exception: %s", exp)
            logger.warning("Response: %s", exp.response)

    def getBackendHistory(self, search=None):
        """Get the backend Alignak logs

        :return: None
        """
        if not search:
            search = {}
        if "sort" not in search:
            search.update({'sort': '-_id'})
        if 'projection' not in search:
            search.update({
                'projection': json.dumps({
                    "host_name": 1, "service_name": 1, "user_name": 1,
                    "type": 1, "message": 1, "logcheckresult": 1
                })
            })
        if 'embedded' not in search:
            # Include the logcheckresult into the history resultset.
            search.update({
                'embedded': json.dumps({"logcheckresult": 1})
            })

        try:  # pylint: disable=too-many-nested-blocks
            if not self.backend_available:
                self.backend_available = self.getBackendAvailability()
            if not self.backend_available:
                return {'_status': 'ERR', '_error': u'Alignak backend is not available currently?'}

            logger.info("Searching history: %s", search)
            logger.info("Backend: %s", self.backend.__dict__)
            if 'where' in search:
                search.update({'where': json.dumps(search['where'])})
            result = self.backend.get('history', search)
            logger.debug("Backend history, got: %s", result)
            if result['_status'] == 'OK':
                logger.debug("history, got %d items", len(result['_items']))
                logger.debug("history, meta: %s", result['_meta'])
                items = []
                for item in result['_items']:
                    # Remove some backend inner fields
                    # item.pop('_id')
                    item.pop('_etag')
                    item.pop('_links')
                    item.pop('_updated')

                    # Remove not interesting content from an existing logcheckresult...
                    if 'logcheckresult' in item:
                        for prop in item['logcheckresult'].keys():
                            if prop in ['_id', '_etag', '_links', '_created', '_updated',
                                        '_realm', '_sub_realm', 'user', 'user_name',
                                        'host', 'host_name', 'service', 'service_name']:
                                del item['logcheckresult'][prop]
                        logger.debug("history, lcr: %s", item['logcheckresult'])
                    items.append(item)
                logger.debug("history, return: %s", {'_status': 'OK', 'items': items})
                return {'_status': 'OK', '_meta': result['_meta'], 'items': items}

            logger.warning("history request, got a problem: %s", result)
            return result
        except BackendException as exp:  # pragma: no cover, should not happen
            logger.warning("Alignak backend is currently not available.")
            logger.warning("Exception: %s", exp)
            logger.warning("Response: %s", exp.response)
            self.backend_available = False

        return {'_status': 'ERR', '_error': u'An exception happened during the request'}

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
        except Exception as exp:  # pylint: disable=W0703
            logger.exception('The HTTP daemon failed with the error %s, exiting', str(exp))
            raise Exception(exp)
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
                        logger.debug("Got an external command: %s", message.cmd_line)
                        # Send external command to my Alignak daemon...
                        self.from_q.put(message)
                        self.received_commands += 1
                    else:
                        logger.warning("Got a message that is not an external command: %s", message)
                except Queue.Empty:
                    # logger.debug("No message in the module queue")
                    pass

            if self.backend_url and self.alignak_backend_polling_period > 0:
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

                try:
                    # Ping Alignak Arbiter
                    response = requests.get("http://%s:%s/ping" %
                                            (self.alignak_host, self.alignak_port))
                    if response.status_code == 200:
                        if response.json() == 'pong':
                            self.alignak_is_alive = True
                        else:
                            logger.error("arbiter ping/pong failed!")
                except requests.ConnectionError as exp:
                    logger.warning("Alignak arbiter is currently not available.")
                    logger.debug("Exception: %s", exp)
                time.sleep(0.1)

            # Get daemons map / status only if Alignak is alive and polling period
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

            # Really too verbose :(
            # logger.debug("time to manage queue and Alignak state: %d seconds",
            # time.time() - start)
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
