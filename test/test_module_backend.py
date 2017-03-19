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
import time
import shlex
import subprocess

import logging

import requests

from alignak_test import AlignakTest
from alignak.modulesmanager import ModulesManager
from alignak.objects.module import Module
from alignak.basemodule import BaseModule
from alignak.brok import Brok

from alignak_backend_client.client import Backend

# Set environment variable to ask code Coverage collection
os.environ['COVERAGE_PROCESS_START'] = '.coveragerc'

from alignak_module_ws.ws import get_instance

# # Activate debug logs for the alignak backend client library
# logging.getLogger("alignak_backend_client.client").setLevel(logging.DEBUG)
#
# # Activate debug logs for the module
# logging.getLogger("alignak.module.web-services").setLevel(logging.DEBUG)


class TestModuleConnection(AlignakTest):

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

        endpoint = 'http://127.0.0.1:5000'

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

    @classmethod
    def tearDownClass(cls):
        cls.p.kill()

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

    def test_module_zzz_get_ws(self):
        """
        Test the module log collection functions
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
            'alignak_backend': 'http://127.0.0.1:5000',
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
        rsp = requests.post(self.endpoint + '/history', json=data, headers=headers, auth=self.auth)
        print(rsp.json())

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
        rsp = requests.post(self.endpoint + '/history', json=data, headers=headers, auth=self.auth)
        print(rsp.json)()

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
        rsp = requests.post(self.endpoint + '/history', json=data, headers=headers, auth=self.auth)
        print(rsp.json)()
        # ---

        # Get history to confirm that backend is ready
        # ---
        response = requests.get(self.endpoint + '/history', auth=self.auth,
                                params={"sort": "-_id", "max_results": 25, "page": 1})
        resp = response.json()
        print("Response: %s" % resp)
        self.assertEqual(len(resp['_items']), 3)
        # ---

        # time.sleep(3600)
        search = {
            'page': 1,
            'max_results': 25
        }
        my_module.getBackendHistory(search)

        # Do not allow GET request on /alignak_logs - not yet authorized
        response = requests.get('http://127.0.0.1:8888/alignak_logs')
        self.assertEqual(response.status_code, 401)

        session = requests.Session()

        # Login with username/password (real backend login)
        headers = {'Content-Type': 'application/json'}
        params = {'username': 'admin', 'password': 'admin'}
        response = session.post('http://127.0.0.1:8888/login', json=params, headers=headers)
        assert response.status_code == 200
        resp = response.json()

        # ---
        # Get the alignak default history
        response = session.get('http://127.0.0.1:8888/alignak_logs')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        for item in result['items']:
            print(item)
        self.assertEqual(len(result['items']), 3)
        # {u'_created': u'Fri, 17 Mar 2017 17:54:51 GMT', u'message': u'HOST ALERT ....',
        # u'user_name': u'Alignak', u'host_name': u'denice', u'type': u'monitoring.alert'}
        # {u'service_name': u'Zombies', u'host_name': u'denice', u'type': u'check.result',
        # u'_created': u'Fri, 17 Mar 2017 17:54:50 GMT',
        # u'message': u'OK[HARD] (False,False): All is ok', u'user_name': u'Alignak'}
        # {u'service_name': u'Processus', u'host_name': u'chazay', u'type': u'check.result',
        # u'_created': u'Fri, 17 Mar 2017 17:54:49 GMT',
        # u'message': u'OK[HARD] (False,False): All is ok', u'user_name': u'Me'}
        # ---

        # ---
        # Get the alignak default history, only check.result
        response = session.get('http://127.0.0.1:8888/alignak_logs?search=type:check.result')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        for item in result['items']:
            print(item)
        self.assertEqual(len(result['items']), 2)
        # ---

        # ---
        # Get the alignak default history, only for a user
        response = session.get('http://127.0.0.1:8888/alignak_logs?search=user_name:Alignak')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        for item in result['items']:
            print(item)
        self.assertEqual(len(result['items']), 2)
        response = session.get('http://127.0.0.1:8888/alignak_logs?search=user_name:Me')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        for item in result['items']:
            print(item)
        self.assertEqual(len(result['items']), 1)
        # ---

        # ---
        # Get the alignak default history, only for an host
        response = session.get('http://127.0.0.1:8888/alignak_logs?search=host_name:chazay')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(len(result['items']), 1)
        response = session.get('http://127.0.0.1:8888/alignak_logs?search=host_name:denice')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(len(result['items']), 2)
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
        response = session.get('http://127.0.0.1:8888/alignak_logs?search="host_name:chazay service_name=Processus"')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        for item in result['items']:
            print(item)
        self.assertEqual(len(result['items']), 3)
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
        self.assertEqual(len(result['items']), 0)
        # ---

        # Logout
        response = session.get('http://127.0.0.1:8888/logout')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result['_status'], 'OK')
        self.assertEqual(result['_result'], 'Logged out')

        # Let the module run for the backend availability to be checked ...
        time.sleep(30)
        self.modulemanager.stop_all()

