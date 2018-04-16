# -*- coding: utf-8 -*-

#
# Copyright (C) 2015-2018: Alignak contrib team, see AUTHORS.txt file for contributors
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

"""
This module is an Alignak Receiver module that exposes a Web services interface.
"""

import os
import copy
import traceback
import json
import time
import datetime
import logging
import threading
import Queue
import requests
import cherrypy

from alignak_backend_client.client import Backend, BackendException

# # Used for the main function to run module independently
# from alignak.objects.module import Module
# from alignak.modulesmanager import ModulesManager

from alignak.stats import Stats

from alignak.external_command import ExternalCommand
from alignak.basemodule import BaseModule

# from alignak_module_ws.utils.daemon import HTTPDaemon, PortNotFree
from alignak_module_ws.utils.ws_server import WSInterface, SESSION_KEY

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

    :param mod_conf: the module item created by the Alignak arbiter
    :rtype alignak.objects.Module
    :return:
    """
    logger.info("Give an instance of %s for alias: %s", mod_conf.python_name, mod_conf.module_alias)

    return AlignakWebServices(mod_conf)


class AlignakWebServices(BaseModule):
    """Main class for the Alignak Web Services implementation"""
    host_state_to_id = {
        "UP": 0,
        "DOWN": 1,
        "UNREACHABLE": 2
    }

    service_state_to_id = {
        "OK": 0,
        "WARNING": 1,
        "CRITICAL": 2,
        "UNKNOWN": 3,
        "UNREACHABLE": 4
    }

    def __init__(self, mod_conf):
        """
        Module initialization

        mod_conf is a dictionary that contains:
        - all the variables declared in the module configuration file
        - a 'properties' value that is the module properties as defined globally in this file

        :param mod_conf: the module item created by the Alignak arbiter
        :rtype alignak.objects.Module
        """
        BaseModule.__init__(self, mod_conf)

        # pylint: disable=global-statement
        global logger
        logger = logging.getLogger('alignak.module.%s' % self.alias)
        if getattr(mod_conf, 'log_level', logging.INFO) in ['DEBUG', 'INFO', 'WARNING', 'ERROR']:
            logger.setLevel(getattr(mod_conf, 'log_level'))

        logger.debug("inner properties: %s", self.__dict__)
        logger.debug("received configuration: %s", mod_conf.__dict__)
        logger.debug("loaded into: %s", self.loaded_into)

        # Allow host/service creation
        self.allow_host_creation = getattr(mod_conf, 'allow_host_creation', '1') == '1'
        logger.info("Alignak host creation allowed: %s", self.allow_host_creation)
        self.ignore_unknown_host = getattr(mod_conf, 'ignore_unknown_host', '0') == '1'
        logger.info("Alignak unknown host is ignored: %s", self.ignore_unknown_host)

        self.allow_service_creation = getattr(mod_conf, 'allow_service_creation', '0') == '1'
        logger.info("Alignak service creation allowed: %s", self.allow_service_creation)
        self.ignore_unknown_service = getattr(mod_conf, 'ignore_unknown_service', '1') == '1'
        logger.info("Alignak unknown service is ignored: %s", self.ignore_unknown_service)

        self.realm_case = getattr(mod_conf, 'realm_case', '')
        if self.realm_case not in ['upper', 'lower', 'capitalize']:
            self.realm_case = ''
        logger.info("Alignak realm case: %s", self.realm_case)

        # Set timestamp
        self.set_timestamp = getattr(mod_conf, 'set_timestamp', '1') == '1'
        logger.info("Alignak external commands, set timestamp: %s", self.set_timestamp)

        # Give some feedback when updating the host/services
        # 0: no feedback
        # 1: feedback only for host
        # 2: feedback for host and services
        try:
            self.give_feedback = int(getattr(mod_conf, 'give_feedback', '1'))
        except ValueError:
            self.give_feedback = 1
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
        self.backend_url = getattr(mod_conf, 'alignak_backend', '')
        if not self.backend_url:
            logger.warning('Alignak Backend is not configured. '
                           'Some module features will not be available.')

        logger.info("Alignak backend endpoint: %s", self.backend_url)

        try:
            self.client_processes = int(getattr(mod_conf, 'client_processes', '1'))
        except ValueError:
            self.client_processes = 1
        logger.info("Number of processes used by backend client: %s", self.client_processes)

        self.backend_username = getattr(mod_conf, 'username', '')
        self.backend_password = getattr(mod_conf, 'password', '')
        self.backend_generate = getattr(mod_conf, 'allowgeneratetoken', False)

        try:
            self.alignak_backend_polling_period = int(
                getattr(mod_conf, 'alignak_backend_polling_period', '10'))
        except ValueError:
            self.alignak_backend_polling_period = 10

        # Backend behavior part
        self.alignak_backend_old_lcr = getattr(mod_conf, 'alignak_backend_old_lcr', '1') == '1'
        self.alignak_backend_get_lcr = getattr(mod_conf, 'alignak_backend_get_lcr', '0') == '1'
        try:
            self.alignak_backend_timeshift = int(
                getattr(mod_conf, 'alignak_backend_timeshift', '0'))
        except ValueError:
            self.alignak_backend_timeshift = 0
        self.alignak_backend_livestate_update = getattr(mod_conf,
                                                        'alignak_backend_livestate_update',
                                                        '0') == '1'

        if not self.backend_username:
            logger.warning("No Alignak backend credentials configured (empty username/token). "
                           "The backend connection will use the WS user credentials.")

        # Alignak Arbiter host / post
        self.alignak_host = getattr(mod_conf, 'alignak_host', '127.0.0.1')
        try:
            self.alignak_port = int(getattr(mod_conf, 'alignak_port', '7770'))
        except ValueError:
            self.alignak_port = 7770
        if not self.alignak_host:
            logger.warning('Alignak Arbiter address is not configured. Alignak polling is '
                           'disabled and some information will not be available.')
        else:
            logger.info("Alignak Arbiter configuration: %s:%d",
                        self.alignak_host, self.alignak_port)

        # Alignak polling
        self.alignak_is_alive = False
        try:
            self.alignak_polling_period = int(getattr(mod_conf, 'alignak_polling_period', '5'))
        except ValueError:
            self.alignak_polling_period = 5
        logger.info("Alignak Arbiter polling period: %d", self.alignak_polling_period)
        try:
            self.alignak_daemons_polling_period = \
                int(getattr(mod_conf, 'alignak_daemons_polling_period', '10'))
        except ValueError:
            self.alignak_daemons_polling_period = 10
        logger.info("Alignak daemons get status period: %d", self.alignak_daemons_polling_period)

        self.authorization = getattr(mod_conf, 'authorization', '1') in ['1', '']
        if not self.authorization:
            logger.warning("HTTP autorization is not enabled, this is not recommended. "
                           "You should consider enabling authorization!")

        self.app_name = str(getattr(self, 'name', getattr(self, 'alias')))
        # cherrypy.config.update({"tools.sessions.on": True,
        #                         "tools.sessions.name": self.app_name})
        # This application config overrides the default processors
        # so we put them back in case we need them
        config = {
            '/': {
                'tools.gzip.on': True,
                'tools.gzip.mime_types': ['text/*', 'application/json'],
                'tools.ws_auth.on': self.authorization,
                'tools.sessions.on': True,
                # 'tools.sessions.debug': True,
                'tools.sessions.name': self.app_name
            }
        }

        cherrypy.log("Serving application for %s" % self.app_name)
        # Mount the main application (an Alignak daemon interface)
        cherrypy.tree.mount(WSInterface(self), '/ws', config)

        # Our Alignak daemons map
        self.daemons_map = {}

        # Daemon properties that we are interested in
        self.daemon_properties = ['address', 'port', 'spare', 'is_sent',
                                  'realm_name', 'manage_sub_realms', 'manage_arbiters',
                                  'active', 'reachable', 'alive', 'passive',
                                  'last_check', 'polling_interval', 'max_check_attempts']

        logger.info("StatsD configuration: %s:%s, prefix: %s, enabled: %s",
                    getattr(mod_conf, 'statsd_host', 'localhost'),
                    int(getattr(mod_conf, 'statsd_port', '8125') or 8125),
                    getattr(mod_conf, 'statsd_prefix', 'alignak.modules'),
                    getattr(mod_conf, 'statsd_enabled'))
        self.statsmgr = Stats()
        self.statsmgr.register(self.alias, 'module',
                               statsd_host=getattr(mod_conf, 'statsd_host', 'localhost'),
                               statsd_port=int(getattr(mod_conf, 'statsd_port', '8125') or 8125),
                               statsd_prefix=getattr(mod_conf, 'statsd_prefix', 'alignak'),
                               statsd_enabled=(getattr(mod_conf, 'statsd_enabled')))

        # Count received commands
        self.received_commands = 0

    def _backend(self):
        """
        Return a new Client Backend instance
        :return: backend.Client
        """
        backend = Backend(self.backend_url, self.client_processes)
        return backend

    def _auth_backend(self):
        """
        Return a new Client Backend instance with authenticated user
        User is an external user (for CherryPy)
        :return: backend.Client
        """
        backend = self._backend()
        if self.authorization:
            backend.token = cherrypy.session[SESSION_KEY]
        return backend

    def _backend_available(self):
        """Is the backend available?
        We use the internal credentials set in the config file
        :return: bool
        """
        logger.debug("Checking backend availability")

        available = False

        generate = 'enabled'
        if not self.backend_generate:
            generate = 'disabled'

        backend = self._backend()
        try:
            available = backend.login(self.backend_username, self.backend_password, generate)
        except BackendException as err:  # pragma: no cover, should not happen
            logger.warning("Alignak backend is currently not available.")
            logger.warning("Exception: %s", err)
            logger.warning("Response: %s", err.response)

        return available

    def _default_realm(self):
        """
        Get the higher level realm for the current logger-in user
        This realm identifier will be used when it is necessary to provide a realm
        (eg. for new objects creation)
        :return: dict
        """
        default_realm = None

        try:
            backend = self._auth_backend()
            result = backend.get('/realm', {'max_results': 1, 'sort': '_level'})
            default_realm = result['_items'][0]
            logger.debug("Got default realm: %s", default_realm)
        except BackendException as err:
            logger.warning("Can't get default realm.")
            logger.warning("Exception: %s", err)
            logger.warning("Response: %s", err.response)

        return default_realm

    def backend_token(self, username, password):
        """Get the token from the backend

        :param username: str. User name to log in
        :param password: str. User's password
        :return: str or None
        """
        logger.debug("Retrieving token for user: %s (hidden password)", username)

        token = None
        if not username and not password:
            return token

        if username and not password:
            # We consider that we received a backend token in the username
            logger.debug("Returning the username as token (no password supplied)")
            return username

        backend = self._backend()
        try:
            backend.login(username, password)
            token = backend.token
            logger.debug("Token retrieved: %s", token)
        except BackendException as exp:  # pragma: no cover, should not happen
            logger.warning("Alignak backend is currently not available.")
            logger.warning("Exception: %s", exp)
            logger.warning("Response: %s", exp.response)

        return token

    def init(self):
        """This function initializes the module instance.

        If False is returned, the modules manager will periodically retry to initialize the module.
        If an exception is raised, the module will be definitely considered as dead :/

        This function must be present and return True for Alignak to consider the module as loaded
        and fully functional.

        :return: True if initialization is ok, else False
        """
        return True

    def backend_creation_data(self, host_name, service_name, data=None):
        """Returns the data that will be posted to the backend for host or service creation

        This function parses the provided data to find out some items that are already
        existing in the alignak backend. If some found, their name is replaced with the
        item identifier read from the backend

        :param host_name: host name
        :param service_name: service name (None for an host creation)
        :param data: posted data for the element creation
        :return: data to post on element creation
        """

        backend = self._auth_backend()
        #
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
                        response2 = backend.get('timeperiod', params=field_params)
                    elif field in ['_realm']:
                        response2 = backend.get('realm', params=field_params)
                    elif field in ['check_command', 'event_handler',
                                   'service_notification_commands',
                                   'host_notification_commands']:
                        response2 = backend.get('command', params=field_params)
                    elif field in ['_templates']:
                        field_params = {'where': json.dumps({'name': value,
                                                             '_is_template': True})}
                        if host_creation:
                            response2 = backend.get('host', params=field_params)
                        else:
                            response2 = backend.get('service', params=field_params)
                    else:
                        response2 = backend.get(field, params=field_params)

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

        default_realm = self._default_realm()
        if '_realm' not in post_data and default_realm:
            logger.info("add default realm (%s) to the data", default_realm['_id'])
            post_data.update({'_realm': default_realm['_id']})

        if '_id' in post_data:
            post_data.pop('_id')

        logger.debug("post_data: %s", post_data)
        return post_data

    def get_host_group(self, name, embedded=False):
        # pylint: disable=too-many-nested-blocks
        """Get the specified hostgroup

        Search the hostgroup in the backend with its name

        If the hosts group exists, the hosts group data and members are returned back

        :param name: hosts group name
        :param embedded: True to embed the linked resources
        :return: hosts group properties
        """
        hostgroups = []

        backend = self._auth_backend()

        ws_result = {'_status': 'OK', '_result': [], '_issues': []}
        try:
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
            start = time.time()
            result = backend.get_all('hostgroup', params=search)
            self.statsmgr.counter('backend-getall.hostgroup', 1)
            self.statsmgr.timer('backend-getall-time.hostgroup', time.time() - start)
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
            return exp.response

        ws_result['_result'] = hostgroups
        ws_result.pop('_issues')
        return ws_result

    def get_host(self, host_name):
        """Get the specified host

        Search the host in the backend with its name

        If the host exists, the host data are returned back

        :param host_name: host name
        :return: host properties
        """
        hosts = []

        backend = self._auth_backend()

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
            start = time.time()
            result = backend.get_all('host', params=search)
            self.statsmgr.counter('backend-getall.host', 1)
            self.statsmgr.timer('backend-getall-time.host', time.time() - start)
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
            return exp.response

        ws_result['_result'] = hosts
        ws_result.pop('_issues')
        return ws_result

    def update_host(self, host_name, data):
        # pylint: disable=too-many-locals, too-many-return-statements, too-many-nested-blocks
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
        host_created = False

        backend = self._auth_backend()

        ws_result = {'_status': 'OK', '_result': ['%s is alive :)' % host_name],
                     '_issues': []}

        if self.backend_url:
            try:
                start = time.time()
                result = backend.get('/host', {'where': json.dumps({'name': host_name})})
                self.statsmgr.counter('backend-get.host', 1)
                self.statsmgr.timer('backend-get-time.host', time.time() - start)
                logger.debug("Get host, got: %s", result)
                if not result['_items']:
                    if not self.allow_host_creation:
                        if not self.ignore_unknown_host:
                            ws_result['_status'] = 'ERR'
                            ws_result['_issues'].append("Requested host '%s' does not exist. "
                                                        "Note that host creation is not allowed."
                                                        % host_name)
                        else:
                            ws_result['_result'] = ["Requested host '%s' does not exist"
                                                    % host_name]

                        if not self.give_feedback and '_feedback' in ws_result:
                            ws_result.pop('_feedback')
                        return ws_result

                if not result['_items'] and self.allow_host_creation:
                    # Tries to create the host
                    logger.info("Requested host '%s' does not exist. "
                                "Trying to create a new host...", host_name)
                    ws_result['_result'].append("Requested host '%s' does not exist." % host_name)

                    if 'template' not in data:
                        data['template'] = None

                    # Change Realm case
                    if data['template'] and '_realm' in data['template']:
                        if data['template']['_realm'] != 'All':
                            if self.realm_case == 'upper':
                                data['template']['_realm'] = data['template']['_realm'].upper()
                            if self.realm_case == 'lower':
                                data['template']['_realm'] = data['template']['_realm'].lower()
                            if self.realm_case == 'capitalize':
                                data['template']['_realm'] = data['template']['_realm'].capitalize()

                    # Request data for host creation (no service)
                    post_data = self.backend_creation_data(host_name, None, data['template'])
                    logger.debug("Post host, data: %s", post_data)
                    start = time.time()
                    result = backend.post('host', data=post_data)
                    self.statsmgr.counter('backend-post.host', 1)
                    self.statsmgr.timer('backend-post-time.host', time.time() - start)
                    logger.debug("Post host, response: %s", result)
                    if result['_status'] != 'OK':
                        logger.warning("Post host, error: %s", result)
                        ws_result['_status'] = 'ERR'
                        ws_result['_issues'].append("Requested host '%s' creation failed."
                                                    % host_name)
                        if not self.give_feedback and '_feedback' in ws_result:
                            ws_result.pop('_feedback')

                        return ws_result

                    # Get the newly created host
                    ws_result['_result'].append("Requested host '%s' created." % host_name)
                    host = backend.get('/'.join(['host', result['_id']]))
                    logger.debug("Get host, got: %s", host)
                    logger.info("Created a new host: %s", host_name)
                    self.statsmgr.counter('host-created', 1)
                    host_created = True
                else:
                    host = result['_items'][0]
            except BackendException as exp:
                logger.warning("Alignak backend exception for updateHost: %s", exp.response)
                ws_result['_status'] = 'ERR'
                ws_result['_issues'].append("Alignak backend error. Exception, updateHost: %s"
                                            % str(exp))
                ws_result['_issues'].append("Alignak backend error. Response: %s" % exp.response)
                return ws_result
        if not host:
            host = {'name': host_name}

        update = None

        # Update host check state
        if 'active_checks_enabled' in data:
            if isinstance(data['active_checks_enabled'], bool):
                if data['active_checks_enabled'] != host['active_checks_enabled']:
                    logger.info("Host active checks state is different '%s': %s -> %s",
                                host_name,
                                host['active_checks_enabled'], data['active_checks_enabled'])
            data.pop('active_checks_enabled')

        if 'passive_checks_enabled' in data:
            if isinstance(data['passive_checks_enabled'], bool):
                if data['passive_checks_enabled'] != host['passive_checks_enabled']:
                    logger.info("Host passive checks state is different '%s': %s -> %s",
                                host_name,
                                host['passive_checks_enabled'], data['passive_checks_enabled'])
            data.pop('passive_checks_enabled')

        if 'check_freshness' in data:
            if isinstance(data['check_freshness'], bool):
                if data['check_freshness'] != host['check_freshness']:
                    logger.info("Host freshness checks state is different '%s': %s -> %s",
                                host_name,
                                host['check_freshness'], data['check_freshness'])
            data.pop('check_freshness')

        # Update host variables
        if 'variables' in data and data['variables']:
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
                            logger.info("Update host %s variable: %s = %s", host_name, prop, value)
                            customs[custom] = value
            if update:
                data['customs'] = customs

        # -----
        # Tag host and services livestate with the current time
        # This will allow to measure the livestate management latency
        now = time.time()
        if data['livestate']:
            if not isinstance(data['livestate'], list):
                data['livestate'] = [data['livestate']]
            last_ts = 0
            for livestate in data['livestate']:
                livestate['_ws_timestamp'] = now
                try:
                    timestamp = int(livestate.get('timestamp', 'ABC'))
                    if timestamp < last_ts:
                        logger.info("Got unordered timestamp for the host: %s. "
                                    "The Alignak scheduler may not handle the check result!",
                                    host['name'])
                    last_ts = timestamp
                except ValueError:
                    pass

        if data['services']:
            for service in data['services']:
                if 'livestate' in service and service['livestate']:
                    if not isinstance(service['livestate'], list):
                        service['livestate'] = [service['livestate']]
                    last_ts = 0
                    for livestate in service['livestate']:
                        livestate['_ws_timestamp'] = now
                        try:
                            timestamp = int(livestate.get('timestamp', 'ABC'))
                            if timestamp < last_ts:
                                logger.info("Got unordered timestamp for the service: %s/%s. "
                                            "The Alignak scheduler may not handle "
                                            "the check result!", host['name'], service['name'])
                            last_ts = timestamp
                        except ValueError:
                            pass
        # -----

        # Update host livestate
        if data['livestate']:
            for livestate in data['livestate']:
                if 'state' not in livestate:
                    ws_result['_issues'].append('Missing state in the livestate.')
                else:
                    state = livestate.get('state', 'UP').upper()
                    if state not in ['UP', 'DOWN', 'UNREACHABLE']:
                        ws_result['_issues'].append("Host state must be UP, DOWN or UNREACHABLE"
                                                    ", and not '%s'." % (state))
                    else:
                        self.statsmgr.counter('host-livestate', 1)
                        # Update the host live state
                        if self.alignak_backend_livestate_update or host_created:
                            update = True
                            data['ls_state'] = livestate.get('state', 'UP').upper()
                            data['ls_state_id'] = self.host_state_to_id[data['ls_state']]
                            data['ls_state_type'] = 'HARD'
                            try:
                                data['ls_last_check'] = int(livestate.get('timestamp', 'ABC'))
                            except ValueError:
                                data['ls_last_check'] = int(time.time())
                            data['ls_output'] = livestate.get('output', '')
                            data['ls_long_output'] = livestate.get('long_output', '')
                            data['ls_perf_data'] = livestate.get('perf_data', '')
                        ws_result['_result'].append(self.build_host_livestate(host, livestate,
                                                                              host_created))

        # Update host services
        if data['services']:
            if '_feedback' not in ws_result:
                ws_result['_feedback'] = {}
            ws_result['_feedback']['services'] = []

            # Get all current host services from the backend
            services = copy.deepcopy(data['services'])
            if self.backend_url:
                try:
                    start = time.time()
                    result = backend.get_all('service',
                                             {'where': json.dumps({'host': host['_id']})})
                    self.statsmgr.counter('backend-getall.service', 1)
                    self.statsmgr.timer('backend-getall-time.service', time.time() - start)
                    logger.debug("Get host services, got: %s", result)
                    if not result['_items']:
                        if not self.allow_service_creation:
                            ws_result['_issues'].append("No services exist for the host '%s'"
                                                        % host['name'])
                            if not self.ignore_unknown_service:
                                ws_result['_status'] = 'ERR'
                            return ws_result

                    services = result['_items']
                except BackendException as exp:  # pragma: no cover, should not happen
                    logger.warning("Alignak backend exception, updateService.")
                    logger.warning("Exception: %s", exp)
                    logger.warning("Exception response: %s", exp.response)
                    return exp.response

            for service in data['services']:
                service_name = service.get('name', None)
                if service_name is None:
                    ws_result['_issues'].append("A service does not have a 'name' property")
                    continue
                service.pop('name')
                result = self.update_service(host, services, service_name, service, host_created)
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
                self.statsmgr.counter('host-livestate-error', 1)
                return ws_result

            if self.give_feedback:
                host = backend.get('/'.join(['host', host['_id']]))
                if '_feedback' not in ws_result:
                    ws_result['_feedback'] = {}
                ws_result['_feedback'].update({'name': host['name']})
                for prop in host:
                    if prop in self.feedback_host:
                        ws_result['_feedback'].update({prop: host[prop]})

            if not self.give_feedback and '_feedback' in ws_result:
                ws_result.pop('_feedback')

            if not self.give_result:
                ws_result.pop('_result')

            ws_result.pop('_issues')
            logger.debug("Result: %s", ws_result)
            self.statsmgr.counter('host-livestate-only', 1)
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
                self.statsmgr.counter('host-no_update-error', 1)
                return ws_result

            if self.give_feedback:
                host = backend.get('/'.join(['host', host['_id']]))
                if '_feedback' not in ws_result:
                    ws_result['_feedback'] = {}
                ws_result['_feedback'].update({'name': host['name']})
                for prop in host:
                    if prop in self.feedback_host:
                        ws_result['_feedback'].update({prop: host[prop]})

            if not self.give_feedback and '_feedback' in ws_result:
                ws_result.pop('_feedback')

            if not self.give_result:
                ws_result.pop('_result')

            ws_result.pop('_issues')
            logger.debug("Result: %s", ws_result)
            self.statsmgr.counter('host-no_update-only', 1)
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
            if '_etag' in host:
                headers = {'Content-Type': 'application/json', 'If-Match': host['_etag']}
                logger.info("Updating host '%s': %s", host_name, data)
                start = time.time()
                patch_result = backend.patch('/'.join(['host', host['_id']]),
                                             data=data, headers=headers, inception=True)
                self.statsmgr.counter('backend-patch.host', 1)
                self.statsmgr.timer('backend-patch-time.host', time.time() - start)
                logger.debug("Backend patch, result: %s", patch_result)
                if patch_result['_status'] != 'OK':
                    logger.warning("Host patch, got a problem: %s", result)
                    return ('ERR', patch_result['_issues'])

                if self.give_feedback:
                    host = backend.get('/'.join(['host', host['_id']]))
                    if '_feedback' not in ws_result:
                        ws_result['_feedback'] = {}
                    ws_result['_feedback'].update({'name': host['name']})
                    for prop in host:
                        if prop in self.feedback_host:
                            ws_result['_feedback'].update({prop: host[prop]})

            if not self.give_feedback and '_feedback' in ws_result:
                ws_result.pop('_feedback')

        except BackendException as exp:  # pragma: no cover, should not happen
            logger.warning("Alignak backend is currently not available.")
            logger.warning("Exception: %s", exp)
            return ('ERR', "Host update error, backend exception. "
                           "Get exception: %s" % str(exp))

        ws_result['_result'].append("Host '%s' updated." % host['name'])

        if ws_result['_issues']:
            ws_result['_status'] = 'ERR'
            if not self.give_feedback and '_feedback' in ws_result:
                ws_result.pop('_feedback')
            return ws_result

        if not self.give_result:
            ws_result.pop('_result')

        if not self.give_feedback and '_feedback' in ws_result:
            ws_result.pop('_feedback')

        ws_result.pop('_issues')
        return ws_result

    def update_service(self, host, services, service_name, data, host_created):
        # pylint: disable=too-many-arguments, too-many-locals
        # pylint: disable=too-many-return-statements, too-many-nested-blocks
        """Create/update the custom variables for the specified service

        Search the service in the backend and update its custom variables with the provided ones.

        :param host: host data
        :param services: the host services got from the backend
        :param service_name: service description
        :param data: dictionary of the service data to be modified
        :param host_created: the host just got created
        :return: (status, message) tuple
        """
        service = None

        backend = self._auth_backend()

        ws_result = {'_status': 'OK', '_result': [], '_issues': []}
        try:
            if self.allow_service_creation and not any(s['name'] == service_name for s in services):
                # Tries to create the service
                logger.info("Requested service '%s/%s' does not exist. "
                            "Trying to create a new service",
                            host['name'], service_name)
                ws_result['_result'].append("Requested service '%s/%s' does not exist."
                                            % (host['name'], service_name))

                if 'template' not in data:
                    data['template'] = None

                # Change Realm case
                if data['template'] and '_realm' in data['template']:
                    if data['template']['_realm'] != 'All':
                        if self.realm_case == 'upper':
                            data['template']['_realm'] = data['template']['_realm'].upper()
                        if self.realm_case == 'lower':
                            data['template']['_realm'] = data['template']['_realm'].lower()
                        if self.realm_case == 'capitalize':
                            data['template']['_realm'] = data['template']['_realm'].capitalize()

                # Request data for service creation
                post_data = self.backend_creation_data(host['name'], service_name, data['template'])
                post_data.update({'host': host['_id']})
                logger.debug("Post service, data: %s", post_data)
                start = time.time()
                result = backend.post('service', data=post_data)
                self.statsmgr.counter('backend-post.service', 1)
                self.statsmgr.timer('backend-post-time.service', time.time() - start)
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
                service = backend.get('/'.join(['service', result['_id']]))
                logger.debug("Get service, got: %s", service)
                self.statsmgr.counter('service-created', 1)
            else:
                for s in services:
                    if s['name'] == service_name:
                        service = s
        except BackendException as exp:  # pragma: no cover, should not happen
            logger.warning("Alignak backend exception, updateService.")
            logger.warning("Exception: %s", exp)
            logger.warning("Exception response: %s", exp.response)
            return exp.response

        if not service:
            # Raise an information for a non existing service
            message = "Requested service '%s/%s' does not exist." \
                      % (host['name'], service_name)
            if not self.allow_service_creation:
                message += " Note that service creation is not allowed."
            logger.info(message)
            if not self.ignore_unknown_service:
                ws_result['_status'] = 'ERR'
                ws_result['_issues'].append(message)
            else:
                ws_result['_result'].append(message)

            return ws_result

        update = None

        # Update service check state
        if 'active_checks_enabled' in data:
            if isinstance(data['active_checks_enabled'], bool):
                update = False
                if data['active_checks_enabled'] != service['active_checks_enabled']:
                    update = True

                    logger.info("Service active checks state modified '%s/%s': %s -> %s",
                                host['name'], service_name,
                                service['active_checks_enabled'], data['active_checks_enabled'])
                    # Except when an host just got created...
                    if not host_created:
                        # todo: perharps this command is not useful
                        # because the backend is updated...
                        command_line = 'DISABLE_SVC_CHECK;%s;%s' % (host['name'], service_name)
                        if data['active_checks_enabled']:
                            command_line = 'ENABLE_SVC_CHECK;%s;%s' % (host['name'], service_name)
                            ws_result['_result'].append('Service %s/%s active checks will be '
                                                        'enabled.' % (host['name'], service_name))
                        else:
                            ws_result['_result'].append('Service %s/%s active checks will be '
                                                        'disabled.' % (host['name'], service_name))

                        # Add a command to get managed
                        if self.set_timestamp:
                            command_line = '[%d] %s' % (time.time(), command_line)
                        ws_result['_result'].append('Sent external command: %s.' % command_line)
                        logger.debug("Sending command: %s", command_line)
                        self.from_q.put(ExternalCommand(command_line))
                        self.received_commands += 1
                else:
                    data.pop('active_checks_enabled')
            else:
                data.pop('active_checks_enabled')

        if 'passive_checks_enabled' in data:
            if isinstance(data['passive_checks_enabled'], bool):
                if update is None:
                    update = False
                if data['passive_checks_enabled'] != service['passive_checks_enabled']:
                    update = True

                    logger.info("Service passive checks state modified '%s/%s': %s -> %s",
                                host['name'], service_name,
                                service['passive_checks_enabled'], data['passive_checks_enabled'])
                    # Except when an host just got created...
                    if not host_created:
                        # todo: perharps this command is not useful
                        # because the backend is updated...
                        command_line = 'DISABLE_PASSIVE_SVC_CHECKS;%s;%s' \
                                       % (host['name'], service_name)
                        if data['passive_checks_enabled']:
                            command_line = 'ENABLE_PASSIVE_SVC_CHECKS;%s;%s' \
                                           % (host['name'], service_name)
                            ws_result['_result'].append('Service %s/%s passive checks will be '
                                                        'enabled.' % (host['name'], service_name))
                        else:
                            ws_result['_result'].append('Service %s/%s passive checks will be '
                                                        'disabled.' % (host['name'], service_name))

                        # Add a command to get managed
                        if self.set_timestamp:
                            command_line = '[%d] %s' % (time.time(), command_line)
                        ws_result['_result'].append('Sent external command: %s.' % command_line)
                        logger.debug("Sending command: %s", command_line)
                        self.from_q.put(ExternalCommand(command_line))
                        self.received_commands += 1
                else:
                    data.pop('passive_checks_enabled')
            else:
                data.pop('passive_checks_enabled')

        if 'check_freshness' in data:
            if isinstance(data['check_freshness'], bool):
                if update is None:
                    update = False
                if data['check_freshness'] != service['check_freshness']:
                    update = True

                    logger.info("Service freshness check state modified '%s/%s': %s -> %s",
                                host['name'], service_name,
                                service['check_freshness'], data['check_freshness'])
                    # todo: as of Alignak #938, no external command exist
                    # to enable/disable on a service basis
                else:
                    data.pop('check_freshness')
            else:
                data.pop('check_freshness')

        # Update service variables
        if 'variables' in data and data['variables']:
            if update is None:
                update = False
            customs = service['customs']
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
                            logger.info("Update service variable: %s = %s", prop, value)
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
                        self.statsmgr.counter('service-livestate', 1)
                        # Update the service live state
                        if self.alignak_backend_livestate_update or host_created:
                            update = True
                            data['ls_state'] = livestate.get('state', 'OK').upper()
                            data['ls_state_id'] = self.service_state_to_id[data['ls_state']]
                            data['ls_state_type'] = 'HARD'
                            try:
                                data['ls_last_check'] = int(livestate.get('timestamp', 'ABC'))
                            except ValueError:
                                data['ls_last_check'] = int(time.time())
                            data['ls_output'] = livestate.get('output', '')
                            data['ls_long_output'] = livestate.get('long_output', '')
                            data['ls_perf_data'] = livestate.get('perf_data', '')
                        ws_result['_result'].append(self.build_service_livestate(host, service,
                                                                                 livestate,
                                                                                 host_created))

        # If no data update requested (only livestate in the data...)
        if update is None:
            logger.debug("No service update, only livestate: %s / %s",
                         self.give_result, self.give_feedback)
            # Simple service alive without any required update
            if ws_result['_issues']:
                ws_result['_status'] = 'ERR'
                self.statsmgr.counter('service-livestate-error', 1)
                return ws_result

            if self.give_feedback > 1:
                # Do not get from the backend, we already did this before...
                # service = backend.get('/'.join(['service', service['_id']]))
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
            self.statsmgr.counter('service-livestate-only', 1)
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
                self.statsmgr.counter('service-no_update-error', 1)
                return ws_result

            if self.give_feedback > 1:
                # Do not get from the backend, we already did this before...
                # service = backend.get('/'.join(['service', service['_id']]))
                if '_feedback' not in ws_result:
                    ws_result['_feedback'] = {}
                ws_result['_feedback'].update({'name': service['name']})
                for prop in service:
                    if prop in self.feedback_service:
                        ws_result['_feedback'].update({prop: service[prop]})
            else:
                if '_feedback' in ws_result:
                    ws_result.pop('_feedback')

            ws_result.pop('_issues')
            self.statsmgr.counter('service-no_update-only', 1)
            return ws_result

        # Clean data to be posted
        if 'template' in data:
            data.pop('template')
        if 'livestate' in data:
            data.pop('livestate')
        if 'variables' in data:
            data.pop('variables')

        try:
            headers = {'Content-Type': 'application/json', 'If-Match': service['_etag']}
            logger.info("Updating service '%s/%s': %s", host['name'], service_name, data)
            start = time.time()
            patch_result = backend.patch('/'.join(['service', service['_id']]),
                                         data=data, headers=headers, inception=True)
            self.statsmgr.counter('backend-patch.service', 1)
            self.statsmgr.timer('backend-patch-time.service', time.time() - start)
            logger.debug("Backend patch, result: %s", patch_result)
            if patch_result['_status'] != 'OK':
                logger.warning("Service patch, got a problem: %s", result)
                return ('ERR', patch_result['_issues'])

            if self.give_feedback > 1:
                service = backend.get('/'.join(['service', service['_id']]))
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
            return ('ERR', "Service update error, backend exception. "
                           "Get exception: %s" % str(exp))

        ws_result['_result'].append("Service '%s/%s' updated" % (host['name'], service_name))

        if ws_result['_issues']:
            ws_result['_status'] = 'ERR'
            return ws_result

        ws_result.pop('_issues')
        return ws_result

    def build_host_comment(self, host_name, service_name, author, comment, timestamp):
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
        self.from_q.put(ExternalCommand(command_line))
        self.received_commands += 1

        result = {'_status': 'OK', '_result': [command_line], '_issues': []}

        # -----
        # This to post an event in the Alignak backend
        # todo: check if the exernal command raise is not enough !
        # -----
        backend = self._auth_backend()

        try:
            data = {
                "host_name": host_name,
                "user_name": author,
                "type": "webui.comment",
                "message": comment
            }
            logger.debug("Posting an event: %s", data)
            post_result = backend.post('history', data)
            logger.debug("Backend post, result: %s", post_result)
            if post_result['_status'] != 'OK':
                logger.warning("history post, got a problem: %s", result)
                result['_issues'] = post_result['_issues']
        except BackendException as exp:  # pragma: no cover, should not happen
            logger.warning("Alignak backend is currently not available.")
            logger.warning("Exception: %s", exp)
            logger.warning("Response: %s", exp.response)
            return exp.response

        if result['_issues']:
            result['_status'] = 'ERR'
            return result

        result.pop('_issues')
        return result

    def build_host_livestate(self, host, livestate, host_created):
        # pylint: disable=too-many-locals
        """Build and notify the external command for an host livestate

        PROCESS_HOST_CHECK_RESULT;<host_name>;<status_code>;<plugin_output>

        Create and post a logcheckresult to the backend for the livestate

        :param host: host from the Alignak backend
        :param livestate: livestate dictionary
        :param host_created: the host just got created
        :return: external command line
        """
        backend = self._auth_backend()

        now = time.time()
        past = None

        state = livestate.get('state', 'UP').upper()
        output = livestate.get('output', '')
        long_output = livestate.get('long_output', '')
        perf_data = livestate.get('perf_data', '')
        try:
            timestamp = int(livestate.get('timestamp', 'ABC'))
        except ValueError:
            timestamp = None

        if timestamp and timestamp + self.alignak_backend_timeshift < now:
            past = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            logger.debug("Got a check result from the past (%s / %d s) for %s...",
                         past, now - timestamp + self.alignak_backend_timeshift, host['name'])

        parameters = '%s;%s' % (self.host_state_to_id[state], output)
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

        # Except when an host just got created...
        if not host_created:
            # ... add a command to get managed by Alignak
            self.from_q.put(ExternalCommand(command_line))
            self.received_commands += 1
            logger.debug("Sent command: %s", command_line)

        now = time.time()
        self.statsmgr.timer('host-livestate-time', now - livestate.get('_ws_timestamp', now))

        # -------------------------------------------
        # Add a check result for an host if we got a timestamp in the past
        # A passive check with a timestamp older than the host last check data will not be
        # managed by Alignak but we may track this event in the backend log check result
        if timestamp and self.alignak_backend_old_lcr:
            past = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            logger.debug("Recording a check result from the past (%s / %d s) for %s...",
                         past, now - timestamp + self.alignak_backend_timeshift, host['name'])
            # Assume data are in the host livestate
            data = {
                "last_check": timestamp or livestate.get('_ws_timestamp', now),
                "host": host['_id'],
                "service": None,
                'acknowledged': host['ls_acknowledged'],
                'acknowledgement_type': host['ls_acknowledgement_type'],
                'downtimed': host['ls_downtimed'],
                'state_id': self.host_state_to_id[state],
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
            if self.alignak_backend_get_lcr:
                logger.info("Updating data from the last LCR...")
                logger.debug("Get the most recent check result for %s...",
                             host['name'])
                start = time.time()
                result = backend.get('logcheckresult',
                                     {'max_results': 1,
                                      'where': json.dumps({
                                          'host_name': host['name'],
                                          'last_check': {"$lte": timestamp}})})
                self.statsmgr.counter('backend-get.lcr', 1)
                self.statsmgr.timer('backend-get-time.lcr', time.time() - start)
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

            start = time.time()
            result = backend.post('logcheckresult', data)
            self.statsmgr.counter('backend-lcr.host', 1)
            self.statsmgr.timer('backend-lcr-time.host', time.time() - start)
            if result['_status'] != 'OK':
                logger.warning("Post logcheckresult, error: %s", result)

        return command_line

    def build_service_livestate(self, host, service, livestate, host_created):
        # pylint: disable=too-many-locals
        """Build and notify the external command for a service livestate

        PROCESS_SERVICE_CHECK_RESULT;<host_name>;<service_description>;<return_code>;<plugin_output>

        Create and post a logcheckresult to the backend for the livestate

        :param host: host from the Alignak backend
        :param service: service from the Alignak backend
        :param livestate: livestate dictionary
        :param host_created: the host just got created
        :return: external command line
        """
        backend = self._auth_backend()

        now = time.time()
        past = None

        state = livestate.get('state', 'OK').upper()
        output = livestate.get('output', '')
        long_output = livestate.get('long_output', '')
        perf_data = livestate.get('perf_data', '')
        try:
            timestamp = int(livestate.get('timestamp', 'ABC'))
        except ValueError:
            timestamp = None

        if timestamp and timestamp + self.alignak_backend_timeshift < now:
            past = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            logger.debug("Got a check result from the past (%s / %d s) for %s/%s...",
                         past, now - timestamp + self.alignak_backend_timeshift,
                         host['name'], service['name'])

        parameters = '%s;%s' % (self.service_state_to_id[state], output)
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

        # Except when an host just got created or a livestate from the past...
        if not host_created:
            # Add a command to get managed by Alignak
            self.from_q.put(ExternalCommand(command_line))
            self.received_commands += 1
            logger.debug("Sent command: %s", command_line)

        now = time.time()
        self.statsmgr.timer('service-livestate-time', now - livestate.get('_ws_timestamp', now))

        # -------------------------------------------
        # Add a check result for a service if we got a timestamp in the past
        # A passive check with a timestamp older than the service last check data will not be
        # managed by Alignak but we may track this event in the backend logcheckresult
        if timestamp and self.alignak_backend_old_lcr:
            past = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            logger.debug("Recording a check result from the past (%s / %d s) for %s/%s...",
                         past, now - timestamp + self.alignak_backend_timeshift,
                         host['name'], service['name'])
            # Assume data are in the service livestate
            data = {
                "last_check": timestamp,
                "host": host['_id'],
                "service": service['_id'],
                'acknowledged': service['ls_acknowledged'],
                'acknowledgement_type': service['ls_acknowledgement_type'],
                'downtimed': service['ls_downtimed'],
                'state_id': self.service_state_to_id[state],
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
            if self.alignak_backend_get_lcr:
                logger.debug("Get the most recent check result for %s/%s...",
                             host['name'], service['name'])
                start = time.time()
                result = backend.get('/logcheckresult', {
                    'max_results': 1,
                    'where': json.dumps({'host_name': host['name'],
                                         'service_name': service['name'],
                                         'last_check': {"$lte": timestamp}})})
                self.statsmgr.counter('backend-get.lcr', 1)
                self.statsmgr.timer('backend-get-time.lcr', time.time() - start)
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

            start = time.time()
            result = backend.post('/logcheckresult', data)
            self.statsmgr.counter('backend-lcr.service', 1)
            self.statsmgr.timer('backend-lcr-time.service', time.time() - start)
            if result['_status'] != 'OK':
                logger.warning("Post logcheckresult, error: %s", result)

        return command_line

    def get_backend_history(self, search=None):
        """Get the backend Alignak logs

        :return: None
        """
        backend = self._auth_backend()

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
            logger.info("Searching history: %s", search)
            # logger.info("Backend: %s", backend.__dict__)
            if 'where' in search:
                search.update({'where': json.dumps(search['where'])})
            result = backend.get('history', search)
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
            return exp.response

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

        try:
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
                            logger.warning("Got a message that is not an external command: %s",
                                           message)
                    except Queue.Empty:
                        # logger.debug("No message in the module queue")
                        pass

                if self.backend_url and self.alignak_backend_polling_period > 0:
                    # Check backend connection
                    if ping_alignak_backend_next_time < start:
                        ping_alignak_backend_next_time = start + self.alignak_backend_polling_period

                        self._backend_available()
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
                                except (ValueError, KeyError):
                                    self.daemons_map[daemon_type][daemon_name][prop] = 'unknown'
                    time.sleep(0.1)

                # Really too verbose :(
                # logger.debug("time to manage queue and Alignak state: %d seconds",
                # time.time() - start)
                time.sleep(0.1)
        except Exception as exp:
            logger.error("Exception: %s", exp)

        logger.info("stopped")
