#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2016: Alignak team, see AUTHORS.txt file for contributors
#
# This file is part of Alignak.
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
"""
Test the module with an Alignak backend connection
"""

import os
import sys
import time
import json
import shlex
import subprocess

from pprint import pprint

import requests
import pytest

from alignak_test import AlignakTest
from alignak.modulesmanager import ModulesManager
from alignak.objects.module import Module

# Set environment variable to ask code Coverage collection
os.environ['COVERAGE_PROCESS_START'] = '.coveragerc'

from alignak_module_ws.ws import get_instance
from alignak_module_ws.utils.helper import Helper

# # Activate debug logs for the alignak backend client library
# logging.getLogger("alignak_backend_client.client").setLevel(logging.DEBUG)
#
# # Activate debug logs for the module
# logging.getLogger("alignak.module.web-services").setLevel(logging.DEBUG)


class TestModuleWsBackendConnection(AlignakTest):

    @classmethod
    def setUpClass(cls):

        # Set test mode for alignak backend
        os.environ['TEST_ALIGNAK_BACKEND'] = '1'
        os.environ['ALIGNAK_BACKEND_MONGO_DBNAME'] = 'alignak-module-ws-backend-test'

        # Delete used mongo DBs
        print ("Deleting Alignak backend DB...")
        exit_code = subprocess.call(
            shlex.split(
                'mongo %s --eval "db.dropDatabase()"' % os.environ['ALIGNAK_BACKEND_MONGO_DBNAME'])
        )
        assert exit_code == 0

        cls.p = subprocess.Popen(['uwsgi', '--plugin', 'python', '-w', 'alignakbackend:app',
                                  '--socket', '0.0.0.0:5000',
                                  '--protocol=http', '--enable-threads', '--pidfile',
                                  '/tmp/uwsgi.pid'])
        time.sleep(3)

        cls.endpoint = 'http://127.0.0.1:5000'

        # Backend authentication
        headers = {'Content-Type': 'application/json'}
        params = {'username': 'admin', 'password': 'admin'}
        # Get admin user token (force regenerate)
        response = requests.post(cls.endpoint + '/login', json=params, headers=headers)
        resp = response.json()
        cls.token = resp['token']
        cls.auth = requests.auth.HTTPBasicAuth(cls.token, '')

        # Get admin user
        response = requests.get(cls.endpoint + '/user', auth=cls.auth)
        resp = response.json()
        cls.user_admin = resp['_items'][0]

        # Get realms
        response = requests.get(cls.endpoint + '/realm', auth=cls.auth)
        resp = response.json()
        cls.realmAll_id = resp['_items'][0]['_id']

        # Add a user
        data = {'name': 'test', 'password': 'test', 'back_role_super_admin': False,
                'host_notification_period': cls.user_admin['host_notification_period'],
                'service_notification_period': cls.user_admin['service_notification_period'],
                '_realm': cls.realmAll_id}
        response = requests.post(cls.endpoint + '/user', json=data, headers=headers,
                                 auth=cls.auth)
        resp = response.json()
        print("Created a new user: %s" % resp)

        # Get new user restrict role
        params = {'where': json.dumps({'user': resp['_id']})}
        response = requests.get(cls.endpoint + '/userrestrictrole', params=params, auth=cls.auth)
        resp = response.json()

        # Update user's rights - set full CRUD rights
        headers = {'Content-Type': 'application/json', 'If-Match': resp['_items'][0]['_etag']}
        data = {'crud': ['create', 'read', 'update', 'delete', 'custom']}
        resp = requests.patch(cls.endpoint + '/userrestrictrole/' + resp['_items'][0]['_id'],
                              json=data, headers=headers, auth=cls.auth)
        resp = resp.json()
        assert resp['_status'] == 'OK'

        # Add command
        data = {
            "name": "ping",
            "command_line": "check_ping -H $HOSTADDRESS$",
            "_realm": cls.realmAll_id
        }
        requests.post(cls.endpoint + '/command', json=data, headers=headers, auth=cls.auth)
        response = requests.get(cls.endpoint + '/command', auth=cls.auth)
        resp = response.json()
        cls.rc = resp['_items']

        # Add an host
        data = {
            "name": "srv001",
            "address": "192.168.0.2",
            "business_impact": 5,
            "check_command": cls.rc[0]['_id'],
            "_realm": cls.realmAll_id
        }
        response = requests.post(cls.endpoint + '/host', json=data, headers=headers, auth=cls.auth)
        response = requests.get(cls.endpoint + '/host?where={"name":"srv001"}', auth=cls.auth)
        resp = response.json()
        cls.rh = resp['_items']

        # Add a service
        data = {
            "name": "ping",
            "host": cls.rh[0]['_id'],
            "check_command": cls.rc[0]['_id'],
            "business_impact": 4,
            "_realm": cls.realmAll_id
        }
        response = requests.post(cls.endpoint + '/service', json=data, headers=headers, auth=cls.auth)
        response = requests.get(cls.endpoint + '/service', auth=cls.auth)
        resp = response.json()
        cls.rs = resp['_items']

        cls.modulemanager = None

    @classmethod
    def tearDownClass(cls):
        cls.p.kill()

    def setUp(self):
        """Create resources in backend

        :return: None
        """

    def tearDown(self):
        if self.modulemanager:
            time.sleep(1)
            self.modulemanager.stop_all()

    def test_connection_accepted(self):
        """ Test module backend connection accepted """
        # admin user login
        mod = get_instance(Module({
            'module_alias': 'web-services',
            'module_types': 'web-services',
            'python_name': 'alignak_module_ws',
            'alignak_backend': 'http://127.0.0.1:5000',
            'username': 'admin',
            'password': 'admin',
        }))
        self.assertTrue(mod.backend_available)

        # test user login
        mod = get_instance(Module({
            'module_alias': 'web-services',
            'module_types': 'web-services',
            'python_name': 'alignak_module_ws',
            'alignak_backend': 'http://127.0.0.1:5000',
            'username': 'test',
            'password': 'test',
        }))
        self.assertTrue(mod.backend_available)

    def test_connection_refused(self):
        """ Test module backend connection refused """
        # No backend data defined
        mod = get_instance(Module({
            'module_alias': 'web-services',
            'module_types': 'web-services',
            'python_name': 'alignak_module_ws',
        }))
        self.assertFalse(mod.backend_available)

        # Backend bad URL
        mod = get_instance(Module({
            'module_alias': 'web-services',
            'module_types': 'web-services',
            'python_name': 'alignak_module_ws',
            'alignak_backend': 'http://bad_url',
            'username': 'admin',
            'password': 'admin',
        }))
        self.assertFalse(mod.backend_available)

        # Backend refused login
        mod = get_instance(Module({
            'module_alias': 'web-services',
            'module_types': 'web-services',
            'python_name': 'alignak_module_ws',
            'alignak_backend': 'http://127.0.0.1:5000',
            'username': 'fake',
            'password': 'fake',
        }))
        self.assertFalse(mod.backend_available)
