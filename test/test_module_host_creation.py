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
import re
import time
import json

import shlex
import subprocess

import logging

import requests

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


class TestModuleWsHostServiceCreation(AlignakTest):
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

        cls.endpoint = 'http://127.0.0.1:5000'

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

    @classmethod
    def tearDownClass(cls):
        cls.p.kill()

    @classmethod
    def tearDown(cls):
        """Delete resources in backend

        :return: None
        """
        for resource in ['host', 'service']:
            requests.delete(cls.endpoint + '/' + resource, auth=cls.auth)

    def test_module_zzz_host_creation(self):
        """Test the module /host API - host creation
        :return:
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
            'give_result': '1',
            'give_feedback': '1',
            # Errors for unknown host/service
            'ignore_unknown_host': '0',
            'ignore_unknown_service': '0',
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

        my_module = self.modulemanager.instances[0]

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
        self.assertIsNotNone(my_module.process)
        self.assertTrue(my_module.process.is_alive())

        time.sleep(1)

        # Do not allow GET request on /host - not authorized
        response = requests.get('http://127.0.0.1:8888/host')
        self.assertEqual(response.status_code, 401)

        session = requests.Session()

        # Login with username/password (real backend login)
        headers = {'Content-Type': 'application/json'}
        params = {'username': 'admin', 'password': 'admin'}
        response = session.post('http://127.0.0.1:8888/login', json=params, headers=headers)
        assert response.status_code == 200
        resp = response.json()

        # Request to create an host - no provided data
        headers = {'Content-Type': 'application/json'}
        data = {
            "name": "new_host_10",
        }
        self.assertEqual(my_module.received_commands, 0)
        response = session.patch('http://127.0.0.1:8888/host', json=data, headers=headers)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result, {
            u'_status': u'OK',
            u'_result': [
                u'new_host_10 is alive :)',
                u"Requested host 'new_host_10' does not exist.",
                u"Requested host 'new_host_10' created."],
            u'_feedback': {
                u'name': u'new_host_10'
            }
        })
        # Host created with default check_command and in default user realm

        # Get new host to confirm creation
        response = requests.get(self.endpoint + '/host', auth=self.auth,
                                params={'where': json.dumps({'name': 'new_host_10'})})
        resp = response.json()
        new_host_10 = resp['_items'][0]
        self.assertEqual('new_host_10', new_host_10['name'])
        self.assertEqual([], new_host_10['_templates'])
        self.assertEqual({}, new_host_10['customs'])

        # Request to create an host - host still existing
        headers = {'Content-Type': 'application/json'}
        data = {
            "name": "new_host_10",
        }
        self.assertEqual(my_module.received_commands, 0)
        response = session.patch('http://127.0.0.1:8888/host', json=data, headers=headers)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result, {
            u'_status': u'OK',
            u'_result': [u'new_host_10 is alive :)'],
            u'_feedback': {
                u'name': u'new_host_10'
            }
        })
        # The host already exists, returns an host alive ;)

        # Request to create an host
        headers = {'Content-Type': 'application/json'}
        data = {
            "name": "new_host_1",
            "template": {
                # "_realm": 'All',
                # "check_command": "unknown"
                "alias": "My host...",
                "check_period": "24x7"
            }
        }
        self.assertEqual(my_module.received_commands, 0)
        response = session.patch('http://127.0.0.1:8888/host', json=data, headers=headers)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result, {
            u'_status': u'OK',
            u'_result': [
                u'new_host_1 is alive :)',
                u"Requested host 'new_host_1' does not exist.",
                u"Requested host 'new_host_1' created."
            ],
            u'_feedback': {
                u'name': u'new_host_1'
            }
        })
        # Host created, even if check_command does not exist, it uses the default check_command!

        # Request to create an host - host created with specified realm and check_command
        headers = {'Content-Type': 'application/json'}
        data = {
            "name": "new_host_2",
            "template": {
                "_realm": 'All',
                "check_command": "_internal_host_up"
            }
        }
        self.assertEqual(my_module.received_commands, 0)
        response = session.patch('http://127.0.0.1:8888/host', json=data, headers=headers)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result, {
            u'_status': u'OK',
            u'_result': [
                u'new_host_2 is alive :)',
                u"Requested host 'new_host_2' does not exist.",
                u"Requested host 'new_host_2' created."
            ],
            u'_feedback': {
                u'name': u'new_host_2'
            }
        })
        # No errors!

        # Get new host to confirm creation
        response = requests.get(self.endpoint + '/host', auth=self.auth,
                                params={'where': json.dumps({'name': 'new_host_2'})})
        resp = response.json()
        new_host_2 = resp['_items'][0]
        self.assertEqual('new_host_2', new_host_2['name'])
        self.assertEqual([], new_host_2['_templates'])
        self.assertEqual({}, new_host_2['customs'])

        # Create a new host with a template and Update host livestate (heartbeat / host is alive): livestate
        data = {
            "name": "new_host_3",
            "template": {
                "_realm": 'All',
                "check_command": "_internal_host_up",
                "_templates": ["generic-host"]
            },
            "livestate": {
                "state": "UP",
                "output": "Output...",
                "long_output": "Long output...",
                "perf_data": "'counter'=1",
            }
        }
        self.assertEqual(my_module.received_commands, 0)
        response = session.patch('http://127.0.0.1:8888/host', json=data, headers=headers)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result, {
            u'_status': u'OK',
            u'_result': [
                u'new_host_3 is alive :)',
                u"Requested host 'new_host_3' does not exist.",
                u"Requested host 'new_host_3' created.",
                u"PROCESS_HOST_CHECK_RESULT;new_host_3;0;Output...|'counter'=1\nLong output...",
            ],
            u'_feedback': {
                u'name': u'new_host_3'
            }
        })
        # No errors!

        # Get new host to confirm creation
        response = requests.get(self.endpoint + '/host', auth=self.auth,
                                params={'where': json.dumps({'name': 'new_host_3'})})
        resp = response.json()
        new_host_3 = resp['_items'][0]
        self.assertEqual('new_host_3', new_host_3['name'])
        self.assertNotEqual([], new_host_3['_templates'])
        self.assertEqual({'_TEMPLATE': 'generic'}, new_host_3['customs'])

        # Create a new host with a template and no _realm and Update host livestate (heartbeat / host is alive): livestate
        data = {
            "name": "new_host_4",
            "template": {
                "_templates": ["generic-host"]
            },
            "livestate": {
                "state": "UP",
                "output": "Output...",
                "long_output": "Long output...",
                "perf_data": "'counter'=1",
            }
        }
        self.assertEqual(my_module.received_commands, 0)
        response = session.patch('http://127.0.0.1:8888/host', json=data, headers=headers)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result, {
            u'_status': u'OK',
            u'_result': [
                u'new_host_4 is alive :)',
                u"Requested host 'new_host_4' does not exist.",
                u"Requested host 'new_host_4' created.",
                u"PROCESS_HOST_CHECK_RESULT;new_host_4;0;Output...|'counter'=1\nLong output...",
            ],
            u'_feedback': {
                u'name': u'new_host_4'
            }
        })
        # No errors!

        # Get new host to confirm creation
        response = requests.get(self.endpoint + '/host', auth=self.auth,
                                params={'where': json.dumps({'name': 'new_host_4'})})
        resp = response.json()
        new_host_4 = resp['_items'][0]
        self.assertEqual('new_host_4', new_host_4['name'])
        self.assertNotEqual([], new_host_4['_templates'])
        self.assertEqual({'_TEMPLATE': 'generic'}, new_host_4['customs'])

        # Logout
        response = session.get('http://127.0.0.1:8888/logout')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result['_status'], 'OK')
        self.assertEqual(result['_result'], 'Logged out')

        self.modulemanager.stop_all()

    def test_module_zzz_service_creation(self):
        """Test the module /host API - service creation
        :return:
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
            'give_result': '1',
            'give_feedback': '1',
            # Errors for unknown host/service
            'ignore_unknown_host': '0',
            'ignore_unknown_service': '0',
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

        my_module = self.modulemanager.instances[0]

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
        self.assertIsNotNone(my_module.process)
        self.assertTrue(my_module.process.is_alive())

        time.sleep(1)

        # Do not allow GET request on /host - not authorized
        response = requests.get('http://127.0.0.1:8888/host')
        self.assertEqual(response.status_code, 401)

        session = requests.Session()

        # Login with username/password (real backend login)
        headers = {'Content-Type': 'application/json'}
        params = {'username': 'admin', 'password': 'admin'}
        response = session.post('http://127.0.0.1:8888/login', json=params, headers=headers)
        assert response.status_code == 200
        resp = response.json()

        # Request to create an host - create a new host
        headers = {'Content-Type': 'application/json'}
        data = {
            "name": "new_host_for_services_0",
            "template": {
                "_realm": 'All',
                "check_command": "_internal_host_up"
            }
        }
        self.assertEqual(my_module.received_commands, 0)
        response = session.patch('http://127.0.0.1:8888/host', json=data, headers=headers)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result, {
            u'_status': u'OK',
            u'_result': [
                u'new_host_for_services_0 is alive :)',
                u"Requested host 'new_host_for_services_0' does not exist.",
                u"Requested host 'new_host_for_services_0' created."
            ],
            u'_feedback': {
                u'name': u'new_host_for_services_0'
            }
        })
        # No errors!


        # Request to create an host - create a new service without any template data
        headers = {'Content-Type': 'application/json'}
        data = {
            "name": "new_host_for_services_0",
            "services": [
                {
                    "name": "test_empty_0",
                    # "template": {
                    #     "_realm": 'All',
                    #     "check_command": "_echo"
                    # },
                    "livestate": {
                        "state": "OK",
                        "output": "Output...",
                        "long_output": "Long output...",
                        "perf_data": "'counter'=1",
                    },
                    "variables": {
                        'test1': 'string',
                        'test2': 1,
                        'test3': 5.0
                    },
                }
            ]
        }
        self.assertEqual(my_module.received_commands, 0)
        response = session.patch('http://127.0.0.1:8888/host', json=data, headers=headers)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result, {
            u'_status': u'OK',
            u'_result': [
                u'new_host_for_services_0 is alive :)',
                u"Requested service 'new_host_for_services_0/test_empty_0' does not exist.",
                u"Requested service 'new_host_for_services_0/test_empty_0' created.",
                u"PROCESS_SERVICE_CHECK_RESULT;new_host_for_services_0;test_empty_0;0;Output...|'counter'=1\nLong output...",
                u"Service 'new_host_for_services_0/test_empty_0' updated",
            ],
            u'_feedback': {
                u'name': u'new_host_for_services_0'
            }
        })
        # No errors!

        # Get new host to confirm creation
        response = requests.get(self.endpoint + '/host', auth=self.auth,
                                params={'where': json.dumps({'name': 'new_host_for_services_0'})})
        resp = response.json()
        new_host_for_services_0 = resp['_items'][0]
        self.assertEqual('new_host_for_services_0', new_host_for_services_0['name'])
        self.assertEqual([], new_host_for_services_0['_templates'])
        self.assertEqual({}, new_host_for_services_0['customs'])

        # Get services data to confirm update
        response = requests.get(self.endpoint + '/service', auth=self.auth,
                                params={'where': json.dumps({'host': new_host_for_services_0['_id'],
                                                             'name': 'test_empty_0'})})
        resp = response.json()
        service = resp['_items'][0]
        # The service still had a variable _CUSTNAME and it inherits from the host variables
        expected = {
            u'_TEST3': 5.0, u'_TEST2': 1, u'_TEST1': u'string'
        }
        self.assertEqual(expected, service['customs'])



        # Request to create an host - create a new service for the new host
        headers = {'Content-Type': 'application/json'}
        data = {
            "name": "new_host_for_services_0",
            "services": [
                {
                    "name": "test_ok_0",
                    "template": {
                        "_realm": 'All',
                        "check_command": "_echo",
                        "alias": "My service...",
                        "check_period": "24x7"
                    },
                    "livestate": {
                        "state": "OK",
                        "output": "Output...",
                        "long_output": "Long output...",
                        "perf_data": "'counter'=1",
                    },
                    "variables": {
                        'test1': 'string',
                        'test2': 1,
                        'test3': 5.0
                    },
                }
            ]
        }
        self.assertEqual(my_module.received_commands, 0)
        response = session.patch('http://127.0.0.1:8888/host', json=data, headers=headers)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result, {
            u'_status': u'OK',
            u'_result': [
                u'new_host_for_services_0 is alive :)',
                u"Requested service 'new_host_for_services_0/test_ok_0' does not exist.",
                u"Requested service 'new_host_for_services_0/test_ok_0' created.",
                u"PROCESS_SERVICE_CHECK_RESULT;new_host_for_services_0;test_ok_0;0;Output...|'counter'=1\nLong output...",
                u"Service 'new_host_for_services_0/test_ok_0' updated",
            ],
            u'_feedback': {
                u'name': u'new_host_for_services_0'
            }
        })
        # No errors!

        # Get new host to confirm creation
        response = requests.get(self.endpoint + '/host', auth=self.auth,
                                params={'where': json.dumps({'name': 'new_host_for_services_0'})})
        resp = response.json()
        new_host_for_services_0 = resp['_items'][0]
        self.assertEqual('new_host_for_services_0', new_host_for_services_0['name'])
        self.assertEqual([], new_host_for_services_0['_templates'])
        self.assertEqual({}, new_host_for_services_0['customs'])

        # Get services data to confirm update
        response = requests.get(self.endpoint + '/service', auth=self.auth,
                                params={'where': json.dumps({'host': new_host_for_services_0['_id'],
                                                             'name': 'test_ok_0'})})
        resp = response.json()
        service = resp['_items'][0]
        # The service still had a variable _CUSTNAME and it inherits from the host variables
        expected = {
            u'_TEST3': 5.0, u'_TEST2': 1, u'_TEST1': u'string'
        }
        self.assertEqual(expected, service['customs'])


        # Create a new service with a template and update service livestate and data
        data = {
            "name": "new_host_for_services_0",
            "services": [
                {
                    "name": "test_ok_1",
                    "template": {
                        "_realm": 'All',
                        "check_command": "_echo",
                        "_templates": ["generic-service"]
                    },
                    "livestate": {
                        "state": "OK",
                        "output": "Output...",
                        "long_output": "Long output...",
                        "perf_data": "'counter'=1",
                    },
                    "variables": {
                        'test1': 'string',
                        'test2': 1,
                        'test3': 5.0
                    },
                }
            ]
        }
        self.assertEqual(my_module.received_commands, 0)
        response = session.patch('http://127.0.0.1:8888/host', json=data, headers=headers)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result, {
            u'_status': u'OK',
            u'_result': [
                u'new_host_for_services_0 is alive :)',
                u"Requested service 'new_host_for_services_0/test_ok_1' does not exist.",
                u"Requested service 'new_host_for_services_0/test_ok_1' created.",
                u"PROCESS_SERVICE_CHECK_RESULT;new_host_for_services_0;test_ok_1;0;Output...|'counter'=1\nLong output...",
                u"Service 'new_host_for_services_0/test_ok_1' updated",
            ],
            u'_feedback': {
                u'name': u'new_host_for_services_0'
            }
        })
        # No errors!

        # Get new service to confirm creation
        response = session.get('http://127.0.0.1:5000/host', auth=self.auth,
                                params={'where': json.dumps({'name': 'new_host_for_services_0'})})
        resp = response.json()
        new_host_for_services_0 = resp['_items'][0]
        self.assertEqual('new_host_for_services_0', new_host_for_services_0['name'])
        self.assertEqual([], new_host_for_services_0['_templates'])
        self.assertEqual({}, new_host_for_services_0['customs'])

        # Get services data to confirm update
        response = requests.get('http://127.0.0.1:5000/service', auth=self.auth,
                                params={'where': json.dumps({'host': new_host_for_services_0['_id'],
                                                             'name': 'test_ok_1'})})
        resp = response.json()
        service = resp['_items'][0]
        # The service still had a variable _CUSTNAME and it inherits from the host variables
        expected = {
            u'_TEST3': 5.0, u'_TEST2': 1, u'_TEST1': u'string'
        }
        self.assertEqual(expected, service['customs'])
        # Logout
        response = session.get('http://127.0.0.1:8888/logout')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result['_status'], 'OK')
        self.assertEqual(result['_result'], 'Logged out')

        self.modulemanager.stop_all()
