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
Test the module with an lignak backend connection
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


class TestModuleWsHistory(AlignakTest):

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
        for resource in ['logcheckresult', 'history']:
            requests.delete('http://127.0.0.1:5000/' + resource, auth=self.auth)
        if self.modulemanager:
            time.sleep(1)
            self.modulemanager.stop_all()

    def file_dump(self, data, filename):  # pylint: disable=no-self-use
        """Dump the data to a JSON formatted file
        :param data: data to be dumped
        :param filename: name of the file to use. Only the file name, not the full path!
        :return: dumped file absolute file name
        """
        dump = json.dumps(data, indent=4,
                          separators=(',', ': '), sort_keys=True)
        path = os.path.join(self.folder or os.getcwd(), filename)
        try:
            dfile = open(path, "wt")
            dfile.write(dump)
            dfile.close()
            return path
        except (OSError, IndexError) as exp:  # pragma: no cover, should never happen
            print("Error when writing the list dump file %s : %s" % (path, str(exp)))
            assert False
        return None

    def test_module_zzz_get_history_admin(self):
        """Test the module log collection functions
        :return:
        """
        self.print_header()
        self._get_history("admin", "admin")

    def test_module_zzz_get_history_test(self):
        """Test the module log collection functions
        :return:
        """
        self.print_header()
        self._get_history("test", "test")

    def _get_history(self, username, password):

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
            # Set Arbiter address as empty to not poll the Arbiter else the test will fail!
            'alignak_host': '',
            'alignak_port': 7770,
            # Alignak backend URL
            'alignak_backend': 'http://127.0.0.1:5000',
            'username': 'admin',
            'password': 'admin',
            # Activate CherryPy file logs
            'log_access': '/tmp/alignak-module-ws-access.log',
            'log_error': '/tmp/alignak-module-ws-error.log',
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

        time.sleep(1)

        # Check alive
        self.assertIsNotNone(my_module.process)
        self.assertTrue(my_module.process.is_alive())

        time.sleep(1)

        # ---
        # Prepare the backend content...
        self.endpoint = 'http://127.0.0.1:5000'

        headers = {'Content-Type': 'application/json'}
        params = {'username': 'admin', 'password': 'admin'}
        # get token
        response = requests.post(self.endpoint + '/login', json=params, headers=headers)
        resp = response.json()
        self.token = resp['token']
        self.auth = requests.auth.HTTPBasicAuth(self.token, '')

        # Get default realm
        response = requests.get(self.endpoint + '/realm', auth=self.auth)
        resp = response.json()
        self.realm_all = resp['_items'][0]['_id']
        # ---

        # -------------------------------------------
        # Add a check result for an host
        data = {
            "last_check": 1496332753,
            "host": self.rh[0]['_id'],
            "service": None,
            'acknowledged': False,
            'state_id': 0,
            'state': 'UP',
            'state_type': 'HARD',
            'last_state_id': 0,
            'last_state': 'UP',
            'last_state_type': 'HARD',
            'state_changed': False,
            'latency': 0,
            'execution_time': 0.12,
            'output': 'Check output',
            'long_output': 'Check long_output',
            'perf_data': 'perf_data',
            "_realm": self.realm_all
        }
        response = requests.post(
            self.endpoint + '/logcheckresult', json=data, headers=headers, auth=self.auth
        )
        resp = response.json()
        self.assertEqual(resp['_status'], 'OK')

        # -------------------------------------------
        # Add a check result for a service
        data = {
            "last_check": 1496332754,
            "host": self.rh[0]['_id'],
            "service": self.rs[0]['_id'],
            'acknowledged': False,
            'state_id': 0,
            'state': 'UP',
            'state_type': 'HARD',
            'last_state_id': 0,
            'last_state': 'UP',
            'last_state_type': 'HARD',
            'state_changed': False,
            'latency': 0,
            'execution_time': 0.12,
            'output': 'Check output',
            'long_output': 'Check long_output',
            'perf_data': 'perf_data',
            "_realm": self.realm_all
        }
        response = requests.post(
            self.endpoint + '/logcheckresult', json=data, headers=headers, auth=self.auth
        )
        resp = response.json()
        self.assertEqual(resp['_status'], 'OK')
        # Add an history event
        data = {
            "host_name": "chazay",
            "service_name": "Processus",
            "user_name": "Alignak",
            "type": "check.result",
            "message": "OK[HARD] (False,False): All is ok",
            "_realm": self.realm_all,
            "_sub_realm": True
        }
        time.sleep(1)
        requests.post(self.endpoint + '/history', json=data, headers=headers, auth=self.auth)

        # Add an history event
        time.sleep(1)
        data = {
            "host_name": "denice",
            "service_name": "Zombies",
            "user_name": "Alignak",
            "type": "check.result",
            "message": "OK[HARD] (False,False): All is ok",
            "_realm": self.realm_all,
            "_sub_realm": True
        }
        requests.post(self.endpoint + '/history', json=data, headers=headers, auth=self.auth)

        # Add an history event
        time.sleep(1)
        data = {
            "host_name": "denice",
            "user_name": "Me",
            "type": "monitoring.alert",
            "message": "HOST ALERT ....",
            "_realm": self.realm_all,
            "_sub_realm": True
        }
        requests.post(self.endpoint + '/history', json=data, headers=headers, auth=self.auth)
        # ---

        # ---
        # Get history to confirm that backend is ready
        # ---
        response = requests.get(self.endpoint + '/history', auth=self.auth,
                                params={"sort": "-_id", "max_results": 25, "page": 1, 'embedded': json.dumps({"logcheckresult": 1})})
        resp = response.json()
        pprint(resp['_items'])
        self.assertEqual(len(resp['_items']), 5)

        # Backend real history
        # The commented fields are the one existing in the backend but filtered by the WS
        backend_real_history = [
            {
                u'_created': u'Thu, 01 Jun 2017 15:59:16 GMT',
                # u'_etag': u'9f07c7285b37bb3d336a96ede3d3fd2a774c4c4c',
                u'_id': u'593039d406fd4b3bf0e27d9f',
                # u'_links': {u'self': {u'href': u'history/593039d406fd4b3bf0e27d9f',
                #                       u'title': u'History'}},
                # u'_realm': u'593039cc06fd4b3bf0e27d88',
                # u'_sub_realm': True,
                # u'_updated': u'Thu, 01 Jun 2017 15:59:16 GMT',
                u'host_name': u'denice',
                u'message': u'HOST ALERT ....',
                u'type': u'monitoring.alert',
                u'user_name': u'Me'
            },
            {
                u'_created': u'Thu, 01 Jun 2017 15:59:15 GMT',
                # u'_etag': u'24cd486a1a28859a0177fbe15d1ead61f78f7b2c',
                u'_id': u'593039d306fd4b3bf0e27d9e',
                # u'_links': {u'self': {u'href': u'history/593039d306fd4b3bf0e27d9e',
                #                       u'title': u'History'}},
                # u'_realm': u'593039cc06fd4b3bf0e27d88',
                # u'_sub_realm': True,
                # u'_updated': u'Thu, 01 Jun 2017 15:59:15 GMT',
                u'host_name': u'denice',
                u'message': u'OK[HARD] (False,False): All is ok',
                u'service_name': u'Zombies',
                u'type': u'check.result',
                u'user_name': u'Alignak'
            },
            {
                u'_created': u'Thu, 01 Jun 2017 15:59:14 GMT',
                # u'_etag': u'4c4ee43a4fac0b91dcfddb011619007dedb1cd95',
                u'_id': u'593039d206fd4b3bf0e27d9d',
                # u'_links': {u'self': {u'href': u'history/593039d206fd4b3bf0e27d9d',
                #                       u'title': u'History'}},
                # u'_realm': u'593039cc06fd4b3bf0e27d88',
                # u'_sub_realm': True,
                # u'_updated': u'Thu, 01 Jun 2017 15:59:14 GMT',
                u'host_name': u'chazay',
                u'message': u'OK[HARD] (False,False): All is ok',
                u'service_name': u'Processus',
                u'type': u'check.result',
                u'user_name': u'Alignak'
            },
            {u'_created': u'Thu, 01 Jun 2017 15:59:13 GMT',
             # u'_etag': u'76dd35f575244848dd41f67ad3109cf6f1f9a33c',
             u'_id': u'593039d106fd4b3bf0e27d9c',
             # u'_links': {u'self': {u'href': u'history/593039d106fd4b3bf0e27d9c',
             #                       u'title': u'History'}},
             # u'_realm': u'593039cc06fd4b3bf0e27d88',
             # u'_sub_realm': True,
             # u'_updated': u'Thu, 01 Jun 2017 15:59:13 GMT',
             # u'host': u'593039cc06fd4b3bf0e27d90',
             u'host_name': u'srv001',
             u'logcheckresult': {
                 u'_created': u'Thu, 01 Jun 2017 15:59:13 GMT',
                 # u'_etag': u'10a3935b1158fe4c8f62962a14b1050fef32df4b',
                 # u'_id': u'593039d106fd4b3bf0e27d9b',
                 # u'_realm': u'593039cc06fd4b3bf0e27d88',
                 # u'_sub_realm': True,
                 # u'_updated': u'Thu, 01 Jun 2017 15:59:13 GMT',
                 u'acknowledged': False,
                 u'acknowledgement_type': 1,
                 u'downtimed': False,
                 u'execution_time': 0.12,
                 # u'host': u'593039cc06fd4b3bf0e27d90',
                 # u'host_name': u'srv001',
                 u'last_check': 1496332753,
                 u'last_state': u'UP',
                 u'last_state_changed': 0,
                 u'last_state_id': 0,
                 u'last_state_type': u'HARD',
                 u'latency': 0.0,
                 u'long_output': u'Check long_output',
                 u'output': u'Check output',
                 u'passive_check': False,
                 u'perf_data': u'perf_data',
                 # u'service': u'593039cf06fd4b3bf0e27d98',
                 # u'service_name': u'ping',
                 u'state': u'UP',
                 u'state_changed': False,
                 u'state_id': 0,
                 u'state_type': u'HARD'
             },
             u'message': u'UP[HARD] (False/False): Check output',
             # u'service': u'593039cf06fd4b3bf0e27d98',
             u'service_name': u'ping',
             u'type': u'check.result',
             # u'user': None,
             u'user_name': u'Alignak'
             },
            {u'_created': u'Thu, 01 Jun 2017 15:59:13 GMT',
             # u'_etag': u'c3cd29587ad328325dc48af677b3a36157361a84',
             u'_id': u'593039d106fd4b3bf0e27d9a',
             # u'_links': {u'self': {u'href': u'history/593039d106fd4b3bf0e27d9a',
             #                       u'title': u'History'}},
             # u'_realm': u'593039cc06fd4b3bf0e27d88',
             # u'_sub_realm': True,
             # u'_updated': u'Thu, 01 Jun 2017 15:59:13 GMT',
             # u'host': u'593039cc06fd4b3bf0e27d90',
             u'host_name': u'srv001',
             u'logcheckresult': {
                 u'_created': u'Thu, 01 Jun 2017 15:59:13 GMT',
                 # u'_etag': u'0ea4c16f1e651a02772aa2bfa83070b47e7f6531',
                 # u'_id': u'593039d106fd4b3bf0e27d99',
                 # u'_realm': u'593039cc06fd4b3bf0e27d88',
                 # u'_sub_realm': True,
                 # u'_updated': u'Thu, 01 Jun 2017 15:59:13 GMT',
                 u'acknowledged': False,
                 u'acknowledgement_type': 1,
                 u'downtimed': False,
                 u'execution_time': 0.12,
                 # u'host': u'593039cc06fd4b3bf0e27d90',
                 # u'host_name': u'srv001',
                 u'last_check': 1496332754,
                 u'last_state': u'UP',
                 u'last_state_changed': 0,
                 u'last_state_id': 0,
                 u'last_state_type': u'HARD',
                 u'latency': 0.0,
                 u'long_output': u'Check long_output',
                 u'output': u'Check output',
                 u'passive_check': False,
                 u'perf_data': u'perf_data',
                 # u'service': None,
                 # u'service_name': u'',
                 u'state': u'UP',
                 u'state_changed': False,
                 u'state_id': 0,
                 u'state_type': u'HARD'
             },
             u'message': u'UP[HARD] (False/False): Check output',
             # u'service': None,
             u'service_name': u'',
             u'type': u'check.result',
             # u'user': None,
             u'user_name': u'Alignak'
             }
        ]
        # ---

        # ---
        # # Directly call the module function
        # search = {
        #     'page': 1,
        #     'max_results': 25
        # }
        # result = my_module.getBackendHistory(search)
        # print(result)
        # print("Page: %d, got: %d items" % (search["page"], len(result['items'])))
        # for item in result['items']:
        #     print(item)
        # assert len(result['items']) == 5

        # ---
        # Do not allow GET request on /alignak_logs - not yet authorized!
        response = requests.get('http://127.0.0.1:8888/alignak_logs')
        self.assertEqual(response.status_code, 401)

        session = requests.Session()

        # Login with username/password (real backend login)
        headers = {'Content-Type': 'application/json'}
        params = {'username': username, 'password': password}
        response = session.post('http://127.0.0.1:8888/login', json=params, headers=headers)
        assert response.status_code == 200
        resp = response.json()

        # ---
        # Get the alignak default history
        response = session.get('http://127.0.0.1:8888/alignak_logs')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        # Remove fields that will obviously be different!
        for item in result['items']:
            del(item['_id'])
            del(item['_created'])
            # if 'logcheckresult' in item:
            #     del (item['logcheckresult']['_created'])
        for item in backend_real_history:
            del(item['_id'])
            del(item['_created'])
            if 'logcheckresult' in item:
                del (item['logcheckresult']['_created'])
        self.assertEqual(len(result['items']), 5)
        # Too complex comparison!!!
        # self.assertEqual(backend_real_history, result['items'])
        # assert cmp(backend_real_history, result['items']) == 0
        # ---

        # ---
        # Get the alignak default history, filter to get only check.result
        response = session.get('http://127.0.0.1:8888/alignak_logs?search=type:check.result')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        for item in result['items']:
            print(item)
        self.assertEqual(len(result['items']), 4)
        # ---

        # ---
        # Get the alignak default history, filter to get only for a user
        response = session.get('http://127.0.0.1:8888/alignak_logs?search=user_name:Alignak')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        for item in result['items']:
            print(item)
        self.assertEqual(len(result['items']), 4)
        response = session.get('http://127.0.0.1:8888/alignak_logs?search=user_name:Me')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        for item in result['items']:
            print(item)
        self.assertEqual(len(result['items']), 1)
        # ---

        # ---
        # Get the alignak default history, filter to get only for an host
        response = session.get('http://127.0.0.1:8888/alignak_logs?search=host_name:chazay')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(len(result['items']), 1)
        # Implicit host_name
        response = session.get('http://127.0.0.1:8888/alignak_logs?search=chazay')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(len(result['items']), 1)
        # Unknown search field
        response = session.get('http://127.0.0.1:8888/alignak_logs?search=name:chazay')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        # All history items because name is not aknown search field! So we get all items...
        self.assertEqual(len(result['items']), 5)

        # Some other hosts...
        response = session.get('http://127.0.0.1:8888/alignak_logs?search=host_name:denice')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(len(result['items']), 2)
        response = session.get('http://127.0.0.1:8888/alignak_logs?search=host_name:srv001')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(len(result['items']), 2)

        # Several hosts...
        response = session.get('http://127.0.0.1:8888/alignak_logs?search=host_name:denice host_name:srv001')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(len(result['items']), 4)   # 2 for each host

        # Not an host...
        # TODO: looks that ths criteria is not correctly implemented :(
        # response = session.get('http://127.0.0.1:8888/alignak_logs?search=host_name:!denice')
        # self.assertEqual(response.status_code, 200)
        # result = response.json()
        # self.assertEqual(len(result['items']), 3)
        # ---

        # ---
        # Get the alignak default history, NOT for an host
        # todo: temporarily skipped
        # response = requests.get('http://127.0.0.1:8888/alignak_logs?search=host_name:!Chazay')
        # self.assertEqual(response.status_code, 200)
        # result = response.json()
        # for item in result['items']:
        #     print(item)
        # self.assertEqual(len(result['items']), 2)
        # ---

        # ---
        # Get the alignak default history, only for a service
        response = session.get('http://127.0.0.1:8888/alignak_logs?search=service_name:Processus')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        for item in result['items']:
            print(item)
        self.assertEqual(len(result['items']), 1)
        # ---

        # ---
        # Get the alignak default history, for an host and a service
        # todo multi search query to be improved!
        # response = session.get('http://127.0.0.1:8888/alignak_logs?search="host_name:chazay service_name=Processus"')
        # self.assertEqual(response.status_code, 200)
        # result = response.json()
        # for item in result['items']:
        #     print(item)
        # self.assertEqual(len(result['items']), 3)
        # ---

        # ---
        # Get the alignak default history, unknown event type
        response = session.get('http://127.0.0.1:8888/alignak_logs?search=type:XXX')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        for item in result['items']:
            print(item)
        self.assertEqual(len(result['items']), 0)
        # ---

        # ---
        # Get the alignak default history, page count
        response = session.get('http://127.0.0.1:8888/alignak_logs?start=0&count=1')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        for item in result['items']:
            print(item)
        self.assertEqual(len(result['items']), 1)
        response = session.get('http://127.0.0.1:8888/alignak_logs?start=1&count=1')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        for item in result['items']:
            print(item)
        self.assertEqual(len(result['items']), 1)
        response = session.get('http://127.0.0.1:8888/alignak_logs?start=2&count=1')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        for item in result['items']:
            print(item)
        self.assertEqual(len(result['items']), 1)
        response = session.get('http://127.0.0.1:8888/alignak_logs?start=3&count=1')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        for item in result['items']:
            print(item)
        self.assertEqual(len(result['items']), 1)
        response = session.get('http://127.0.0.1:8888/alignak_logs?start=4&count=1')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        for item in result['items']:
            print(item)
        self.assertEqual(len(result['items']), 1)
        # Over the limits !
        response = session.get('http://127.0.0.1:8888/alignak_logs?start=5&count=1')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        for item in result['items']:
            print(item)
        self.assertEqual(len(result['items']), 0)
        response = session.get('http://127.0.0.1:8888/alignak_logs?start=50&count=50')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        for item in result['items']:
            print(item)
        self.assertEqual(len(result['items']), 0)
        # ---

        # ---
        # Get the alignak history, page count greater than the number of items
        response = session.get('http://127.0.0.1:8888/alignak_logs?start=1&count=25')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        pprint(result)
        self.assertEqual(len(result['items']), 5)   # Got 5 items
        self.assertEqual(result['_meta']['max_results'], 25)
        self.assertEqual(result['_meta']['page'], 1)
        self.assertEqual(result['_meta']['total'], 5)

        response = session.get('http://127.0.0.1:8888/alignak_logs?start=0&count=50')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        pprint(result)
        self.assertEqual(len(result['items']), 5)   # Got 5 items
        self.assertEqual(result['_meta']['max_results'], 50)
        self.assertEqual(result['_meta']['page'], 1)
        self.assertEqual(result['_meta']['total'], 5)

        # ---

        # Logout
        response = session.get('http://127.0.0.1:8888/logout')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result['_status'], 'OK')
        self.assertEqual(result['_result'], 'Logged out')

    @pytest.mark.skip("Internal function to get from an existing backend")
    def _get_from_backend(self, backend_url='http://127.0.01:5000',
                          host_name='test', file_name='history.json'):
        """Get the all history for an host in an existing backend.
        Dumps the resulting information as a JSON array to a file

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
            # Set Arbiter address as empty to not poll the Arbiter else the test will fail!
            'alignak_host': '',
            'alignak_port': 7770,
            # Alignak backend URL
            'alignak_backend': backend_url,
            'username': 'admin',
            'password': 'admin',
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

        time.sleep(2)

        # Check alive
        self.assertIsNotNone(my_module.process)
        self.assertTrue(my_module.process.is_alive())

        time.sleep(1)

        # ---

        # Start with first page ... max_results=3
        page = 1
        count = 25
        items = []
        search = {
            'page': page,
            'max_results': count
        }
        where = Helper.decode_search(host_name)
        if where:
            search.update({'where': json.dumps(where)})

        while count > 0:
            result = my_module.getBackendHistory(search)
            count = len(result['items'])
            print("Page: %d, got: %d items" % (search["page"], count))
            for item in result['items']:
                sys.stdout.write('.')
                # print(item)
            items.extend(result['items'])
            search["page"] += 1
        print("Got: %d items" % len(items))

        self.folder = '/tmp'
        self.file_dump(items, file_name)