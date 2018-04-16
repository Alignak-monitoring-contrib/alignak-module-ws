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

import pytest

import shlex
import subprocess

import logging

import requests

from alignak_test import AlignakTest
from alignak.daemons.receiverdaemon import Receiver
from alignak.modulesmanager import ModulesManager
from alignak.objects.module import Module
from alignak.basemodule import BaseModule

# Set environment variable to ask code Coverage collection
os.environ['COVERAGE_PROCESS_START'] = '.coveragerc'

import alignak_module_ws


class TestModuleWs(AlignakTest):
    """This class contains the tests for the module"""

    @classmethod
    def setUpClass(cls):

        # Simulate an Alignak receiver daemon
        cls.ws_endpoint = 'http://127.0.0.1:7773/ws'
        import cherrypy
        class ReceiverItf(object):
            @cherrypy.expose
            def index(self):
                return "I am the Receiver daemon!"
        from alignak.http.daemon import HTTPDaemon as AlignakDaemon
        http_daemon1 = AlignakDaemon('0.0.0.0', 7773, ReceiverItf(),
                                     False, None, None, None, None, 10, '/tmp/alignak-cherrypy.log')
        def run_http_server():
            http_daemon1.run()
        import threading
        cls.http_thread1 = threading.Thread(target=run_http_server, name='http_server_receiver')
        cls.http_thread1.daemon = True
        cls.http_thread1.start()
        print("Thread started")

        # # Simulate an Alignak arbiter daemon
        # class ArbiterItf(object):
        #     @cherrypy.expose
        #     def index(self):
        #         return "I am the Arbiter daemon!"
        # http_daemon2 = AlignakDaemon('0.0.0.0', 7770, ArbiterItf(),
        #                              False, None, None, None, None, 10, '/tmp/alignak-cherrypy2.log')
        # def run_http_server2():
        #     http_daemon2.run()
        # import threading
        # cls.http_thread2 = threading.Thread(target=run_http_server2, name='http_server_arbiter')
        # cls.http_thread2.daemon = True
        # cls.http_thread2.start()
        # print("Thread 2 started")

        # Set test mode for alignak backend
        os.environ['TEST_ALIGNAK_BACKEND'] = '1'
        os.environ['ALIGNAK_BACKEND_MONGO_DBNAME'] = 'alignak-module-ws'

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
            shlex.split('alignak-backend-import --delete -u admin -p admin %s/cfg/cfg_default.cfg' % test_dir),
            # stdout=fnull, stderr=fnull
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
        super(TestModuleWs, self).setUp()

    def tearDown(self):
        super(TestModuleWs, self).tearDown()

    def test_module_loading(self):
        """
        Test arbiter, broker, ... auto-generated modules

        Alignak module loading

        :return:
        """
        self.setup_with_file('./cfg/cfg_default.cfg')
        self.assertTrue(self.conf_is_correct)
        self.show_configuration_logs()

        # No arbiter modules created
        modules = [m.module_alias for m in self._arbiter.link_to_myself.modules]
        self.assertListEqual(modules, [])

        # The only existing broker module is logs declared in the configuration
        modules = [m.module_alias for m in self._broker_daemon.modules]
        self.assertListEqual(modules, [])

        # No scheduler modules
        modules = [m.module_alias for m in self._scheduler_daemon.modules]
        self.assertListEqual(modules, [])

        # A receiver module
        modules = [m.module_alias for m in self._receiver_daemon.modules]
        self.assertListEqual(modules, ['web-services'])

    def test_module_manager(self):
        """
        Test if the module manager manages correctly all the modules
        :return:
        """
        self.setup_with_file('cfg/cfg_default.cfg')
        self.assertTrue(self.conf_is_correct)
        self.clear_logs()

        # Create an Alignak module
        mod = Module({
            'module_alias': 'web-services',
            'module_types': 'web-services',
            'python_name': 'alignak_module_ws'
        })

        # Create the modules manager for a daemon type
        self.modulemanager = ModulesManager(self._receiver_daemon)

        # Load and initialize the modules:
        #  - load python module
        #  - get module properties and instances
        self.modulemanager.load_and_init([mod])

        # Loading module logs
        self.assert_any_log_match(re.escape(
            "Importing Python module 'alignak_module_ws' for web-services..."
        ))
        self.assert_any_log_match(re.escape(
            "Module properties: {'daemons': ['receiver'], 'phases': ['running'], "
            "'type': 'web-services', 'external': True}"
        ))
        self.assert_any_log_match(re.escape(
            "Imported 'alignak_module_ws' for web-services"
        ))
        self.assert_any_log_match(re.escape(
            "Loaded Python module 'alignak_module_ws' (web-services)"
        ))
        # self.assert_any_log_match(re.escape(
        #     "Give an instance of alignak_module_ws for alias: web-services"
        # ))

        my_module = self.modulemanager.instances[0]

        # Get list of not external modules
        self.assertListEqual([], self.modulemanager.get_internal_instances())
        for phase in ['configuration', 'late_configuration', 'running', 'retention']:
            self.assertListEqual([], self.modulemanager.get_internal_instances(phase))

        # Get list of external modules
        self.assertListEqual([my_module], self.modulemanager.get_external_instances())
        for phase in ['configuration', 'late_configuration', 'retention']:
            self.assertListEqual([], self.modulemanager.get_external_instances(phase))
        for phase in ['running']:
            self.assertListEqual([my_module], self.modulemanager.get_external_instances(phase))

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

        # Clear logs
        self.clear_logs()

        # Kill the external module (normal stop is .stop_process)
        my_module.kill()
        time.sleep(0.1)
        self.assert_log_match("Killing external module", 0)
        self.assert_log_match("External module killed", 1)

        # Should be dead (not normally stopped...) but we still know a process for this module!
        self.assertIsNotNone(my_module.process)

        # Nothing special ...
        self.modulemanager.check_alive_instances()
        self.assert_log_match("The external module web-services died unexpectedly!", 2)
        self.assert_log_match("Setting the module web-services to restart", 3)

        # Try to restart the dead modules
        self.modulemanager.try_to_restart_deads()
        self.assert_log_match("Trying to initialize module: web-services", 4)

        # In fact it's too early, so it won't do it
        # The module instance is still dead
        self.assertFalse(my_module.process.is_alive())

        # So we lie, on the restart tries ...
        my_module.last_init_try = -5
        self.modulemanager.check_alive_instances()
        self.modulemanager.try_to_restart_deads()
        self.assert_log_match("Trying to initialize module: web-services", 5)

        # The module instance is now alive again
        self.assertTrue(my_module.process.is_alive())
        self.assert_log_match("I'm stopping module 'web-services'", 6)
        self.assert_log_match("Starting external process for module web-services", 7)
        self.assert_log_match("web-services is now started", 8)

        # There is nothing else to restart in the module manager
        self.assertEqual([], self.modulemanager.to_restart)

        # Clear logs
        self.clear_logs()

        # Now we look for time restart so we kill it again
        my_module.kill()
        time.sleep(0.2)
        self.assertFalse(my_module.process.is_alive())
        self.assert_log_match("Killing external module", 0)
        self.assert_log_match("External module killed", 1)

        # Should be too early
        self.modulemanager.check_alive_instances()
        self.assert_log_match("The external module web-services died unexpectedly!", 2)
        self.assert_log_match("Setting the module web-services to restart", 3)

        self.modulemanager.try_to_restart_deads()
        self.assert_log_match("Trying to initialize module: web-services", 4)

        # In fact it's too early, so it won't do it
        # The module instance is still dead
        self.assertFalse(my_module.process.is_alive())

        # So we lie, on the restart tries ...
        my_module.last_init_try = -5
        self.modulemanager.check_alive_instances()
        self.modulemanager.try_to_restart_deads()
        self.assert_log_match("Trying to initialize module: web-services", 5)

        # The module instance is now alive again
        self.assertTrue(my_module.process.is_alive())
        self.assert_log_match("I'm stopping module 'web-services'", 6)
        self.assert_log_match("Starting external process for module web-services", 7)
        self.assert_log_match("web-services is now started", 8)

        # Clear logs
        self.clear_logs()

        # And we clear all now
        self.modulemanager.stop_all()
        # Stopping module logs

        self.assert_log_match("Shutting down modules...", 0)
        self.assert_log_match("Request external process to stop for web-services", 1)
        self.assert_log_match(re.escape("I'm stopping module 'web-services' (pid="), 2)
        self.assert_log_match(re.escape("'web-services' is still living after a normal kill, I help it to die"), 3)
        self.assert_log_match(re.escape("Killing external module (pid"), 4)
        self.assert_log_match(re.escape("External module killed"), 5)
        self.assert_log_match("External process stopped.", 6)

    def test_module_start_default(self):
        """
        Test the module initialization function, no parameters, using default
        :return:
        """
        # Obliged to call to get a self.logger...
        self.setup_with_file('cfg/cfg_default.cfg')
        self.assertTrue(self.conf_is_correct)

        # Clear logs
        self.clear_logs()

        # -----
        # Default initialization
        # -----
        # Create an Alignak module
        mod = Module({
            'module_alias': 'web-services',
            'module_types': 'web-services',
            'python_name': 'alignak_module_ws'
        })

        instance = alignak_module_ws.get_instance(mod)
        self.assertIsInstance(instance, BaseModule)
        # print(alignak_module_ws.mod_conf)

        idx = 0
        self.assert_log_match(
            re.escape("Give an instance of alignak_module_ws for "
                      "alias: web-services"), idx)
        idx += 1
        self.assert_log_match(
            re.escape("Alignak host creation allowed: True"), idx)
        idx += 1
        self.assert_log_match(
            re.escape("Alignak unknown host is ignored: False"), idx)
        idx += 1
        self.assert_log_match(
            re.escape("Alignak service creation allowed: False"), idx)
        idx += 1
        self.assert_log_match(
            re.escape("Alignak unknown service is ignored: True"), idx)
        idx += 1
        self.assert_log_match(
            re.escape("Alignak realm case:"), idx)
        idx += 1
        self.assert_log_match(
            re.escape("Alignak external commands, set timestamp: True"), idx)
        idx += 1
        self.assert_log_match(
            re.escape("Alignak update, set give_feedback: 1"), idx)
        idx += 1
        self.assert_log_match(
            re.escape("Alignak host feedback list: ['']"), idx)
        idx += 1
        self.assert_log_match(
            re.escape("Alignak service feedback list: ['']"), idx)
        idx += 1
        self.assert_log_match(
            re.escape("Alignak update, set give_result: False"), idx)
        idx += 1
        self.assert_log_match(
            re.escape("Alignak Backend is not configured. "
                      "Some module features will not be available."), idx)
        idx += 1
        self.assert_log_match(
            re.escape("Alignak backend endpoint:"), idx)
        idx += 1
        self.assert_log_match(
            re.escape("Number of processes used by backend client: 1"), idx)
        idx += 1
        self.assert_log_match(
            re.escape("No Alignak backend credentials configured (empty username/token). "
                      "The backend connection will use the WS user credentials."), idx)
        idx += 1
        self.assert_log_match(
            re.escape("Alignak Arbiter configuration: 127.0.0.1:7770"), idx)
        idx += 1
        self.assert_log_match(
            re.escape("Alignak Arbiter polling period: 5"), idx)
        idx += 1
        self.assert_log_match(
            re.escape("Alignak daemons get status period: 10"), idx)
        idx += 1
        self.assert_log_match(
            re.escape("StatsD configuration: localhost:8125, prefix: alignak, enabled: False"), idx)
        # idx += 1
        # self.assert_log_match(
        #     re.escape("Sending web-services daemon statistics to: localhost:8125, prefix: alignak"), idx)
        # idx += 1
        # self.assert_log_match(
        #     re.escape("Trying to contact StatsD server..."), idx)
        # idx += 1
        # self.assert_log_match(
        #     re.escape("StatsD server contacted"), idx)
        # idx += 1
        # self.assert_log_match(
        #     re.escape("Alignak internal statistics are sent to StatsD."), idx)
        # idx += 1

    def test_module_start_parameters(self):
        """
        Test the module initialization function, no parameters, provide parameters
        :return:
        """
        # Obliged to call to get a self.logger...
        self.setup_with_file('cfg/cfg_default.cfg')
        self.assertTrue(self.conf_is_correct)

        # Clear logs
        self.clear_logs()

        # Create an Alignak module
        mod = Module({
            'module_alias': 'web-services',
            'module_types': 'web-services',
            'python_name': 'alignak_module_ws',
            'use_ssl': 1,
            'alignak_host': 'my_host',
            'alignak_port': 80,
            # Do not set a timestamp in the built external commands
            'set_timestamp': 0,
            # Do not give feedback data
            'give_feedback': 0,
            # Give result data
            'give_result': 1,
            # Errors for unknown host/service
            'allow_host_creation': '1',
            'allow_service_creation': '1',
            # Errors for unknown host/service
            'ignore_unknown_host': '1',
            'ignore_unknown_service': '1',
            'statsd_enabled': '1',
            'statsd_host': '127.0.0.1',
            'statsd_port': '8888',
            'statsd_prefix': 'test'
        })

        instance = alignak_module_ws.get_instance(mod)
        self.assertIsInstance(instance, BaseModule)

        idx = 0
        self.assert_log_match(
            re.escape("Give an instance of alignak_module_ws for "
                      "alias: web-services"), idx)
        idx += 1
        self.assert_log_match(
            re.escape("Alignak host creation allowed: True"), idx)
        idx += 1
        self.assert_log_match(
            re.escape("Alignak unknown host is ignored: True"), idx)
        idx += 1
        self.assert_log_match(
            re.escape("Alignak service creation allowed: True"), idx)
        idx += 1
        self.assert_log_match(
            re.escape("Alignak unknown service is ignored: True"), idx)
        idx += 1
        self.assert_log_match(
            re.escape("Alignak realm case:"), idx)
        idx += 1
        self.assert_log_match(
            re.escape("Alignak external commands, set timestamp: False"), idx)
        idx += 1
        self.assert_log_match(
            re.escape("Alignak update, set give_feedback: 0"), idx)
        idx += 1
        self.assert_log_match(
            re.escape("Alignak host feedback list: ['']"), idx)
        idx += 1
        self.assert_log_match(
            re.escape("Alignak service feedback list: ['']"), idx)
        idx += 1
        self.assert_log_match(
            re.escape("Alignak update, set give_result: False"), idx)
        idx += 1
        self.assert_log_match(
            re.escape("Alignak Backend is not configured. "
                      "Some module features will not be available."), idx)
        idx += 1
        self.assert_log_match(
            re.escape("Alignak backend endpoint:"), idx)
        idx += 1
        self.assert_log_match(
            re.escape("Number of processes used by backend client: 1"), idx)
        idx += 1
        self.assert_log_match(
            re.escape("No Alignak backend credentials configured (empty username/token). "
                      "The backend connection will use the WS user credentials."), idx)
        idx += 1
        self.assert_log_match(
            re.escape("Alignak Arbiter configuration: my_host:80"), idx)
        idx += 1
        self.assert_log_match(
            re.escape("Alignak Arbiter polling period: 5"), idx)
        idx += 1
        self.assert_log_match(
            re.escape("Alignak daemons get status period: 10"), idx)
        idx += 1
        self.assert_log_match(
            re.escape("StatsD configuration: 127.0.0.1:8888, prefix: test, enabled: True"), idx)
        idx += 1
        self.assert_log_match(
            re.escape("Sending web-services statistics to: 127.0.0.1:8888, prefix: test"), idx)
        idx += 1
        self.assert_log_match(
            re.escape("Trying to contact StatsD server..."), idx)
        idx += 1
        self.assert_log_match(
            re.escape("StatsD server contacted"), idx)
        idx += 1
        self.assert_log_match(
            re.escape("Alignak internal statistics are sent to StatsD."), idx)
        idx += 1

    def test_module_zzz_basic_ws(self):
        """Test the module basic API - authorization enabled

        :return:
        """
        # Create an Alignak module
        mod = Module({
            'module_alias': 'web-services',
            'module_types': 'web-services',
            'python_name': 'alignak_module_ws',
            # Alignak backend
            'alignak_backend': 'http://127.0.0.1:5000',
            'username': 'admin',
            'password': 'admin',
            # Set Arbiter address as empty to not poll the Arbiter else the test will fail!
            'alignak_host': '',
            'alignak_port': 7770,
            # Enable authorization
            'authorization': '1'
        })

        # Create a receiver daemon
        args = {'env_file': '', 'daemon_name': 'receiver-master'}
        self._receiver_daemon = Receiver(**args)

        # Create the modules manager for the daemon
        self.modulemanager = ModulesManager(self._receiver_daemon)

        # Load an initialize the modules:
        #  - load python module
        #  - get module properties and instances
        self.modulemanager.load_and_init([mod])

        # Clear logs
        self.clear_logs()

        my_module = self.modulemanager.instances[0]

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

        # Get the WS root endpoint
        # Unauthorized because no authentication!
        response = requests.get(self.ws_endpoint)
        print("Response: %s" % response)
        print("Response: %s" % response.__dict__)
        assert response.status_code == 401

        auth = requests.auth.HTTPBasicAuth('admin', 'admin')
        response = requests.get(self.ws_endpoint, auth=auth)
        print("Response: %s" % response)
        assert response.status_code == 200
        resp = response.json()
        print("Response json: %s" % resp)
        assert resp ==  [
            u'alignak_logs', u'alignak_map', u'api', u'api_full', u'are_you_alive', u'command',
            u'event', u'host', u'hostgroup', u'index', u'login', u'logout'
        ]

        # Login refused because of missing credentials
        print("- Login refused")
        headers = {'Content-Type': 'application/json'}
        params = {}
        response = requests.post(self.ws_endpoint + '/login', json=params, headers=headers)
        assert response.status_code == 200
        resp = response.json()
        print("Response json: %s" % resp)
        assert resp == {'_status': 'ERR', '_issues': ['You must POST parameters on this endpoint.']}
        params = {'username': None, 'password': None}
        response = requests.post(self.ws_endpoint + '/login', json=params, headers=headers)
        assert response.status_code == 200
        resp = response.json()
        print("Response json: %s" % resp)
        assert resp == {'_status': 'ERR', '_issues': ['Missing username parameter.']}

        # # Login refused because of bad username/password (real backend login)
        # params = {'username': 'admin', 'password': 'fake'}
        # response = requests.post(self.ws_endpoint + '/login', json=params, headers=headers)
        # assert response.status_code == 200
        # resp = response.json()
        # print("Response json: %s" % resp)
        # assert resp == {'_status': 'ERR', '_issues': ['Access denied.']}

        # Login with username/password (real backend login)
        print("- Login accepted")
        params = {'username': 'admin', 'password': 'admin'}
        response = requests.post(self.ws_endpoint + '/login', json=params, headers=headers)
        assert response.status_code == 200
        resp = response.json()
        print("Response json: %s" % resp)
        assert '_result' in resp
        token = resp['_result'][0]

        # Login with existing token as a username
        params = {'username': token, 'password': None}
        response = requests.post(self.ws_endpoint + '/login', json=params, headers=headers)
        print("Response: %s" % response)
        assert response.status_code == 200
        resp = response.json()
        print("Response json: %s" % resp)
        assert resp == {'_status': 'OK', '_result': [token]}

        # Login with basic authentication
        print("- Login with basic authentication")
        headers = {'Content-Type': 'application/json'}
        params = {}
        auth = requests.auth.HTTPBasicAuth('admin', 'admin')
        response = requests.post(self.ws_endpoint + '/login', json=params, headers=headers, auth=auth)
        print("Response: %s" % response)
        assert response.status_code == 200
        resp = response.json()
        print("Response json: %s" % resp)
        assert resp == {'_status': 'OK', '_result': [token]}
        params = {}
        auth = requests.auth.HTTPBasicAuth(token, '')
        response = requests.post(self.ws_endpoint + '/login', json=params, headers=headers, auth=auth)
        print("Response: %s" % response)
        assert response.status_code == 200
        resp = response.json()
        print("Response json: %s" % resp)
        assert resp == {'_status': 'OK', '_result': [token]}

        # Get the module API list and request on each endpoint
        auth = requests.auth.HTTPBasicAuth('admin', 'admin')
        response = requests.get(self.ws_endpoint, auth=auth)
        print("Response: %s" % response)
        assert response.status_code == 200
        api_list = response.json()
        for endpoint in api_list:
            print("Trying %s" % (endpoint))
            response = requests.get(self.ws_endpoint + '/' + endpoint, auth=auth)
            print("Response %d: %s" % (response.status_code, response.content))
            self.assertEqual(response.status_code, 200)
            if response.status_code == 200:
                print("Got %s: %s" % (endpoint, response.json()))
            else:
                print("Error %s: %s" % (response.status_code, response.content))

        self.modulemanager.stop_all()

    def test_module_zzz_unauthorized(self):
        """Test the module basic API - authorization disabled

        :return:
        """
        self.setup_with_file('./cfg/cfg_default.cfg')
        self.assertTrue(self.conf_is_correct)
        self.show_configuration_logs()

        # Create an Alignak module
        mod = Module({
            'module_alias': 'web-services',
            'module_types': 'web-services',
            'python_name': 'alignak_module_ws',
            # Alignak backend - not configured
            'alignak_backend': '',
            'username': '',
            'password': '',
            # Set Arbiter address as empty to not poll the Arbiter else the test will fail!
            'alignak_host': '',
            'alignak_port': 7770,
            # Disable authorization
            'authorization': '0'
        })

        # Create a receiver daemon
        args = {'env_file': '', 'daemon_name': 'receiver-master'}
        self._receiver_daemon = Receiver(**args)

        # Create the modules manager for the daemon
        self.modulemanager = ModulesManager(self._receiver_daemon)

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

        # Get the module API list and request on each endpoint
        response = requests.get(self.ws_endpoint)
        print("Response: %s" % response)
        assert response.status_code == 200
        api_list = response.json()
        for endpoint in api_list:
            print("Trying %s" % (endpoint))
            response = requests.get(self.ws_endpoint + '/' + endpoint)
            print("Response %d: %s" % (response.status_code, response.content))
            self.assertEqual(response.status_code, 200)
            if response.status_code == 200:
                print("Got %s: %s" % (endpoint, response.json()))
            else:
                print("Error %s: %s" % (response.status_code, response.content))

        self.modulemanager.stop_all()

    def test_module_zzz_authorization(self):
        """Test the module basic API - authorization login logout

        :return:
        """
        # Create an Alignak module
        mod = Module({
            'module_alias': 'web-services',
            'module_types': 'web-services',
            'python_name': 'alignak_module_ws',
            # Alignak backend
            'alignak_backend': 'http://127.0.0.1:5000',
            'username': 'admin',
            'password': 'admin',
            # Set Arbiter address as empty to not poll the Arbiter else the test will fail!
            'alignak_host': '',
            'alignak_port': 7770
        })

        # Create a receiver daemon
        args = {'env_file': '', 'daemon_name': 'receiver-master'}
        self._receiver_daemon = Receiver(**args)

        # Create the modules manager for the daemon
        self.modulemanager = ModulesManager(self._receiver_daemon)

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

        # Login with username/password - bad credentials
        headers = {'Content-Type': 'application/json'}
        params = {'username': 'fake', 'password': 'fake'}
        self.show_logs()
        response = requests.post(self.ws_endpoint + '/login', json=params, headers=headers)
        assert response.status_code == 200
        result = response.json()
        assert result == {u'_status': u'ERR', u'_issues': [u'Access denied.']}

        # Login with username/password (real backend login)
        headers = {'Content-Type': 'application/json'}
        params = {'username': 'admin', 'password': 'admin'}
        response = requests.post(self.ws_endpoint + '/login', json=params, headers=headers)
        assert response.status_code == 200
        result = response.json()
        self.assertEqual(result['_status'], 'OK')
        self.assertEqual(result['_result'], [self.user_admin['token']])

        # Logout
        response = requests.get(self.ws_endpoint + '/logout')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result['_status'], 'OK')
        self.assertEqual(result['_result'], 'Logged out')

        # Login with token (real backend login)
        headers = {'Content-Type': 'application/json'}
        params = {'username': self.user_admin['token']}
        response = requests.post(self.ws_endpoint + '/login', json=params, headers=headers)
        assert response.status_code == 200
        result = response.json()
        self.assertEqual(result['_status'], 'OK')
        self.assertEqual(result['_result'], [self.user_admin['token']])

        # Logout
        response = requests.get(self.ws_endpoint + '/logout')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result['_status'], 'OK')
        self.assertEqual(result['_result'], 'Logged out')

        self.modulemanager.stop_all()

    def test_module_zzz_unauthorization(self):
        """Test the module basic API - authorization login logout

        :return:
        """
        # Create an Alignak module
        mod = Module({
            'module_alias': 'web-services',
            'module_types': 'web-services',
            'python_name': 'alignak_module_ws',
            # Alignak backend
            'alignak_backend': 'http://127.0.0.1:5000',
            'username': 'admin',
            'password': 'admin',
            # Set Arbiter address as empty to not poll the Arbiter else the test will fail!
            'alignak_host': '',
            'alignak_port': 7770,
            # Ensable authorization
            'authorization': '1'
        })

        # Create a receiver daemon
        args = {'env_file': '', 'daemon_name': 'receiver-master'}
        self._receiver_daemon = Receiver(**args)

        # Create the modules manager for the daemon
        self.modulemanager = ModulesManager(self._receiver_daemon)

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

        # Request to create/update an host - bad credentials
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
        auth = requests.auth.HTTPBasicAuth('bad-token', '')
        response = requests.patch(self.ws_endpoint + '/host', json=data, headers=headers, auth=auth)
        result = response.json()
        self.assertEqual(response.status_code, 401)
        print(result)
        self.assertEqual(result, {
            u'_status': u'ERR',
            u'_issues': [
                u'Alignak backend error. Exception, updateHost: BackendException raised '
                u'with code 401 and message: 401 Client Error: UNAUTHORIZED for url:'
                u' http://127.0.0.1:5000/host?where=%7B%22name%22%3A+%22new_host_1%22%7D'
                u' - <Response [401]>',
                u'Alignak backend error. Response: <Response [401]>'
                # u'Alignak backend error. Response: <Response [401]>'
            ],
            u'_result': [
                u'new_host_1 is alive :)',
            ]
        })
        # Host created, even if check_command does not exist, it uses the default check_command!

        self.modulemanager.stop_all()

    def test_module_zzz_authorized(self):
        """Test the module basic API - authorization enabled,
        some backend credentials are configured

        :return:
        """
        # Create an Alignak module
        mod = Module({
            'module_alias': 'web-services',
            'module_types': 'web-services',
            'python_name': 'alignak_module_ws',
            # Alignak backend
            'alignak_backend': 'http://127.0.0.1:5000',
            'username': 'admin',
            'password': 'admin',
            # Set Arbiter address as empty to not poll the Arbiter else the test will fail!
            'alignak_host': '',
            'alignak_port': 7770,
            # Ensable authorization
            'authorization': '1',
        })

        # Create a receiver daemon
        args = {'env_file': '', 'daemon_name': 'receiver-master'}
        self._receiver_daemon = Receiver(**args)

        # Create the modules manager for the daemon
        self.modulemanager = ModulesManager(self._receiver_daemon)

        # Load an initialize the modules:
        #  - load python module
        #  - get module properties and instances
        self.modulemanager.load_and_init([mod])

        my_module = self.modulemanager.instances[0]

        # Clear logs
        self.clear_logs()

        # Start external modules
        self.modulemanager.start_external_instances()

        # Starting external module WS
        self.assert_log_match("Trying to initialize module: web-services", 0)
        self.assert_log_match("Starting external module web-services", 1)
        self.assert_log_match("Starting external process for module web-services", 2)
        self.assert_log_match("web-services is now started", 3)

        # Check alive
        self.assertIsNotNone(my_module.process)
        self.assertTrue(my_module.process.is_alive())

        time.sleep(1)

        session = requests.Session()

        # Login with username/password (Admin login)
        headers = {'Content-Type': 'application/json'}
        params = {'username': 'admin', 'password': 'admin'}
        response = session.post(self.ws_endpoint + '/login', json=params, headers=headers)
        assert response.status_code == 200
        resp = response.json()

        # Get the module API list and request on each endpoint
        response = session.get(self.ws_endpoint)
        print("Response: %s" % response)
        assert response.status_code == 200
        api_list = response.json()
        for endpoint in api_list:
            print("Trying %s" % (endpoint))
            response = session.get(self.ws_endpoint + '/' + endpoint)
            print("Response %d: %s" % (response.status_code, response.content))
            self.assertEqual(response.status_code, 200)
            if response.status_code == 200:
                print("Got %s: %s" % (endpoint, response.json()))
            else:
                print("Error %s: %s" % (response.status_code, response.content))

        # Logout
        response = session.get(self.ws_endpoint + '/logout')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result['_status'], 'OK')
        self.assertEqual(result['_result'], 'Logged out')

        # Login with username/password (Test login)
        headers = {'Content-Type': 'application/json'}
        params = {'username': 'admin', 'password': 'admin'}
        response = session.post(self.ws_endpoint + '/login', json=params, headers=headers)
        assert response.status_code == 200
        resp = response.json()

        # Get the module API list and request on each endpoint
        response = session.get(self.ws_endpoint)
        print("Response: %s" % response)
        assert response.status_code == 200
        api_list = response.json()
        for endpoint in api_list:
            print("Trying %s" % (endpoint))
            response = session.get(self.ws_endpoint + '/' + endpoint)
            print("Response %d: %s" % (response.status_code, response.content))
            self.assertEqual(response.status_code, 200)
            if response.status_code == 200:
                print("Got %s: %s" % (endpoint, response.json()))
            else:
                print("Error %s: %s" % (response.status_code, response.content))

        # Logout
        response = session.get(self.ws_endpoint + '/logout')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result['_status'], 'OK')
        self.assertEqual(result['_result'], 'Logged out')

        self.modulemanager.stop_all()

    def test_module_zzz_authorized_bis(self):
        """Test the module basic API - authorization enabled even if no credentials are configured

        :return:
        """
        # Create an Alignak module
        mod = Module({
            'module_alias': 'web-services',
            'module_types': 'web-services',
            'python_name': 'alignak_module_ws',
            # Alignak backend
            'alignak_backend': 'http://127.0.0.1:5000',
            # No credentials nor token configured !
            # 'username': 'admin',
            # 'password': 'admin',
            # Set Arbiter address as empty to not poll the Arbiter else the test will fail!
            'alignak_host': '',
            'alignak_port': 7770,
            # Ensable authorization
            'authorization': '1',
        })

        # Create a receiver daemon
        args = {'env_file': '', 'daemon_name': 'receiver-master'}
        self._receiver_daemon = Receiver(**args)

        # Create the modules manager for the daemon
        self.modulemanager = ModulesManager(self._receiver_daemon)

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

        session = requests.Session()

        # Login with username/password (real backend login)
        headers = {'Content-Type': 'application/json'}
        params = {'username': 'admin', 'password': 'admin'}
        response = session.post(self.ws_endpoint + '/login', json=params, headers=headers)
        assert response.status_code == 200

        # Get the module API list and request on each endpoint
        response = session.get(self.ws_endpoint)
        print("Response: %s" % response)
        assert response.status_code == 200
        api_list = response.json()
        for endpoint in api_list:
            print("Trying %s" % (endpoint))
            response = session.get(self.ws_endpoint + '/' + endpoint)
            print("Response %d: %s" % (response.status_code, response.content))
            self.assertEqual(response.status_code, 200)
            if response.status_code == 200:
                print("Got %s: %s" % (endpoint, response.json()))
            else:
                print("Error %s: %s" % (response.status_code, response.content))

        # Logout
        response = session.get(self.ws_endpoint + '/logout')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result['_status'], 'OK')
        self.assertEqual(result['_result'], 'Logged out')

        self.modulemanager.stop_all()
