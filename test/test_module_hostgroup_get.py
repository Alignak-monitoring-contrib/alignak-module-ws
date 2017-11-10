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
Test the module
"""

import os
import time
import json

import shlex
import subprocess

import requests

from pprint import pprint

from alignak_test import AlignakTest, time_hacker
from alignak.modulesmanager import ModulesManager
from alignak.objects.module import Module
from alignak.basemodule import BaseModule

# Set environment variable to ask code Coverage collection
os.environ['COVERAGE_PROCESS_START'] = '.coveragerc'

import alignak_module_ws

# # Activate debug logs for the alignak backend client library
# logging.getLogger("alignak_backend_client.client").setLevel(logging.DEBUG)
#
# # Activate debug logs for the module
# logging.getLogger("alignak.module.web-services").setLevel(logging.DEBUG)


class TestModuleWsHostgroup(AlignakTest):
    """This class contains the tests for the module"""

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

        fnull = open(os.devnull, 'w')
        cls.p = subprocess.Popen(['uwsgi', '--plugin', 'python', '-w', 'alignakbackend:app',
                                  '--socket', '0.0.0.0:5000',
                                  '--protocol=http', '--enable-threads', '--pidfile',
                                  '/tmp/uwsgi.pid'],
                                 stdout=fnull, stderr=fnull)
        time.sleep(3)

        endpoint = 'http://127.0.0.1:5000'

        test_dir = os.path.dirname(os.path.realpath(__file__))
        print("Current test directory: %s" % test_dir)

        print("Feeding Alignak backend... %s" % test_dir)
        exit_code = subprocess.call(
            shlex.split('alignak-backend-import --delete %s/cfg/cfg_default.cfg' % test_dir),
            stdout=fnull, stderr=fnull
        )
        assert exit_code == 0
        print("Fed")

        # Backend authentication
        headers = {'Content-Type': 'application/json'}
        params = {'username': 'admin', 'password': 'admin'}
        # Get admin user token (force regenerate)
        response = requests.post(endpoint + '/login', json=params, headers=headers)
        resp = response.json()
        cls.token = resp['token']
        cls.auth = requests.auth.HTTPBasicAuth(cls.token, '')

        # Get admin user
        response = requests.get(endpoint + '/user', auth=cls.auth)
        resp = response.json()
        cls.user_admin = resp['_items'][0]

        # Get realms
        response = requests.get(endpoint + '/realm', auth=cls.auth)
        resp = response.json()
        cls.realmAll_id = resp['_items'][0]['_id']

        # Add a user
        data = {'name': 'test', 'password': 'test', 'back_role_super_admin': False,
                'host_notification_period': cls.user_admin['host_notification_period'],
                'service_notification_period': cls.user_admin['service_notification_period'],
                '_realm': cls.realmAll_id}
        response = requests.post(endpoint + '/user', json=data, headers=headers,
                                 auth=cls.auth)
        resp = response.json()
        print("Created a new user: %s" % resp)

        # Get new user restrict role
        params = {'where': json.dumps({'user': resp['_id']})}
        response = requests.get(endpoint + '/userrestrictrole', params=params, auth=cls.auth)
        resp = response.json()

        # Update user's rights - set full CRUD rights
        headers = {'Content-Type': 'application/json', 'If-Match': resp['_items'][0]['_etag']}
        data = {'crud': ['create', 'read', 'update', 'delete', 'custom']}
        resp = requests.patch(endpoint + '/userrestrictrole/' + resp['_items'][0]['_id'],
                              json=data, headers=headers, auth=cls.auth)
        resp = resp.json()
        assert resp['_status'] == 'OK'

    @classmethod
    def tearDownClass(cls):
        cls.p.kill()

    def setUp(self):
        """Create resources in backend

        :return: None
        """
        self.print_header()
        # Obliged to call to get a self.logger...
        self.setup_with_file('cfg/cfg_default.cfg')
        self.assertTrue(self.conf_is_correct)

        # -----
        # Provide parameters - logger configuration file (exists)
        # -----
        # Clear logs
        self.clear_logs()

        # Create an Alignak module
        mod = Module({
            'module_alias': 'web-services',
            'module_types': 'web-services',
            'python_name': 'alignak_module_ws',
            # Alignak backend
            'alignak_backend': 'http://127.0.0.1:5000',
            'username': 'admin',
            'password': 'admin',
            # Do not set a timestamp in the built external commands
            'set_timestamp': '0',
            # Set Arbiter address as empty to not poll the Arbiter else the test will fail!
            'alignak_host': '',
            'alignak_port': 7770,
            # Allow host/service creation
            'allow_host_creation': '1',
            'allow_service_creation': '1'
        })

        # Create the modules manager for a daemon type
        self.modulemanager = ModulesManager('receiver', None)

        # Load an initialize the modules:
        #  - load python module
        #  - get module properties and instances
        self.modulemanager.load_and_init([mod])

        self.my_module = self.modulemanager.instances[0]

        # Clear logs
        self.clear_logs()

        # Start external modules
        self.modulemanager.start_external_instances()

        # Starting external module logs
        self.assert_log_match("Trying to initialize module: web-services", 0)
        self.assert_log_match("Starting external module web-services", 1)
        self.assert_log_match("Starting external process for module web-services", 2)
        self.assert_log_match("web-services is now started", 3)

        # Check alive
        self.assertIsNotNone(self.my_module.process)
        self.assertTrue(self.my_module.process.is_alive())

        time.sleep(1)

    def tearDown(self):
        if self.modulemanager:
            time.sleep(1)
            self.modulemanager.stop_all()

    def test_module_zzz_hostgroup_get(self):
        """Test the module /hostgroup API - hostgroup get information
        :return:
        """
        # Do not allow GET request on /hostgroup - not yet authorized!
        response = requests.get('http://127.0.0.1:8888/hostgroup')
        self.assertEqual(response.status_code, 401)

        session = requests.Session()

        # Login with username/password (real backend login)
        headers = {'Content-Type': 'application/json'}
        params = {'username': 'admin', 'password': 'admin'}
        response = session.post('http://127.0.0.1:8888/login', json=params, headers=headers)
        assert response.status_code == 200
        resp = response.json()

        # -----
        # Get a non-existing host - 1st: use parameters in the request
        response = session.get('http://127.0.0.1:8888/hostgroup', auth=self.auth,
                                params={'name': 'fake-hostgroup'})
        result = response.json()
        self.assertEqual(result, {
            u'_status': u'ERR',
            u'_result': [],
            u'_issues': [
                "Requested hostgroup 'fake-hostgroup' does not exist"
            ]
        })

        # Get a non-existing host - 2nd: use hostgroup name in the URI
        response = session.get('http://127.0.0.1:8888/hostgroup/fake-hostgroup', auth=self.auth)
        result = response.json()
        self.assertEqual(result, {
            u'_status': u'ERR',
            u'_result': [],
            u'_issues': [
                "Requested hostgroup 'fake-hostgroup' does not exist"
            ]
        })

        # -----
        # Get all hostgroups ... no parameters!
        response = session.get('http://127.0.0.1:8888/hostgroup', auth=self.auth)
        result = response.json()
        # from pprint import pprint
        # pprint(result)
        self.assertEqual(result['_status'], 'OK')
        self.assertIsNot(result['_result'], {})
        self.assertEqual(len(result['_result']), 13)

        # -----
        # Get a specific hostgroup - 1st: use parameters in the request
        response = session.get('http://127.0.0.1:8888/hostgroup', auth=self.auth,
                                params={'name': 'hostgroup_01'})
        result = response.json()
        self.assertEqual(result['_status'], 'OK')
        self.assertIsNot(result['_result'], {})
        self.assertEqual(result['_result'][0]['name'], 'hostgroup_01')

        # Get a specific hostgroup - 2nd: use hostgroup name in the URI
        response = session.get('http://127.0.0.1:8888/hostgroup/hostgroup_01', auth=self.auth)
        result = response.json()
        self.assertEqual(result['_status'], 'OK')
        self.assertIsNot(result['_result'], {})
        # Comparing is tricky because of the changing objects _id ...
        # self.assertEqual(result['_result'][0], {
        #     u'_level': 1, u'name': u'hostgroup_01', u'notes': u'', u'hostgroups': [],
        #     u'_parent': {u'alias': u'All hosts', u'name': u'All'}, u'alias': u'hostgroup_alias_01',
        #     u'hosts': [{u'alias': u'up_0', u'name': u'test_host_0'}],
        #     u'_tree_parents': [{u'alias': u'All hosts', u'name': u'All'}],
        #     u'_realm': {u'alias': u'All', u'name': u'All'}
        # })

        # Get a specific hostgroup - embed related items
        response = session.get('http://127.0.0.1:8888/hostgroup/hostgroup_01', auth=self.auth,
                                params={'embedded': True})
        result = response.json()
        self.assertEqual(result['_status'], 'OK')
        self.assertIsNot(result['_result'], {})
        print(result['_result'][0])
        result['_result'][0].pop('_id')
        result['_result'][0].pop('_created')
        result['_result'][0].pop('_updated')
        self.assertEqual(result['_result'][0], {
            u'_level': 1, u'name': u'hostgroup_01', u'notes': u'', u'hostgroups': [],
            u'_parent': {u'alias': u'All hosts', u'name': u'All'}, u'alias': u'hostgroup_alias_01',
            u'hosts': [{u'alias': u'up_0', u'name': u'test_host_0'}],
            u'_tree_parents': [{u'alias': u'All hosts', u'name': u'All'}],
            u'_realm': {u'alias': u'All', u'name': u'All'}
        })

        # -----
        # Logout
        response = session.get('http://127.0.0.1:8888/logout')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result['_status'], 'OK')
        self.assertEqual(result['_result'], 'Logged out')
