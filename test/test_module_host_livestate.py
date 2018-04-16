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
Test the module - host/service livestate
"""

import os
import time
import json

import shlex
import subprocess

import requests

import datetime
from freezegun import freeze_time

from alignak_test import AlignakTest
from alignak.modulesmanager import ModulesManager
from alignak.objects.module import Module
from alignak.basemodule import BaseModule
from alignak.daemons.receiverdaemon import Receiver

# Set an environment variable to print debug information for the backend
os.environ['ALIGNAK_BACKEND_PRINT'] = '1'

# Set environment variable to ask code Coverage collection
os.environ['COVERAGE_PROCESS_START'] = '.coveragerc'

import alignak_module_ws


class TestModuleWsHostLivestate(AlignakTest):
    """This class contains the tests for the module"""

    @classmethod
    def setUpClass(cls):
        cls.maxDiff = None

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

        # Set test mode for alignak backend
        os.environ['TEST_ALIGNAK_BACKEND'] = '1'
        os.environ['ALIGNAK_BACKEND_MONGO_DBNAME'] = 'alignak-module-ws-host-livestate'

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
                                 )
        time.sleep(3)

        endpoint = 'http://127.0.0.1:5000'

        test_dir = os.path.dirname(os.path.realpath(__file__))
        print("Current test directory: %s" % test_dir)

        print("Feeding Alignak backend...")
        print('alignak-backend-import --delete %s/cfg/cfg_default.cfg' % test_dir)
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

        cls.modulemanager = None

    @classmethod
    def tearDownClass(cls):
        """Delete resources in backend

        :return: None
        """
        cls.p.kill()

    def setUp(self):
        super(TestModuleWsHostLivestate, self).setUp()
        self.set_debug_log()

    def tearDown(self):
        """Delete resources in backend

        :return: None
        """
        super(TestModuleWsHostLivestate, self).tearDown()
        for resource in ['logcheckresult']:
            requests.delete('http://127.0.0.1:5000/' + resource, auth=self.auth)

        if self.modulemanager:
            self.modulemanager.stop_all()

    def test_module_host_livestate(self):
        """Test the module /host API - host creation and livestate
        :return:
        """

        """
        When module is really loaded in Alignak:
        [2018-03-31 11:43:42] DEBUG: [receiver-master.alignak.module.web-services] inner properties: {'init_try': 0, 'illegal_char': <_sre.SRE_Pattern object at 0x808e03d50>, 'phases': ['running'], 'is_external': True, 'myconf': <'Module' u'web-services', module: u'alignak_module_ws', type(s): u'web-services' />, 'to_q': None, 'process': None, 'from_q': None, 'interrupted': False, 'loaded_into': 'unknown', 'props': {'daemons': ['receiver'], 'phases': ['running'], 'type': 'web-services', 'external': True}, 'kill_delay': 60, 'module_monitoring_period': 10, 'module_monitoring': False, 'properties': {'daemons': ['receiver'], 'phases': ['running'], 'type': 'web-services', 'external': True}, 'name': u'web-services'}
        [2018-03-31 11:43:42] DEBUG: [receiver-master.alignak.module.web-services] received configuration: {'enable_problem_impacts_states_change': u'1', 'log_notifications': u'1', 'statsd_prefix': u'alignak-fdj.modules', 'statsd_host': u'localhost', 'daemons_initial_port': u'7800', 'log_initial_states': u'0', 'group': u'alignak', 'uuid': u'f0b02b5dfa7a4e1484166a4ef9b1cad3', 'alignak_polling_period': u'60', 'notification_timeout': u'30', 'execute_service_checks': u'1', 'disable_old_nagios_parameters_whining': u'1', 'log_external_commands': u'1', 'tick_update_retention': u'1800', 'password': u'ipm-France2017', 'idontcareaboutsecurity': u'0', 'python_name': u'alignak_module_ws', 'daemon': u'unset', 'tick_update_program_status': u'10', 'name': u'web-services', 'statsd_enabled': False, 'alignak_host': u'alignak1', 'alignak_launched': u'1', 'tick_clean_queues': u'10', 'daemons_stop_timeout': u'10', 'old_properties': {}, 'max_plugins_output_length': u'65536', 'downtimes': {}, 'tags': set([]), 'log_event_handlers': u'1', 'enable_notifications': u'1', 'do_replace': u'1', 'definition_order': 100, 'alignak_backend': u'http://alignak_backend1:5000', 'logger_configuration': u'/usr/local//etc/alignak/alignak-logger.json', 'use': [], 'check_host_freshness': u'1', 'spare': u'0', 'log_host_retries': u'1', 'properties': {'daemons': ['receiver'], 'phases': ['running'], 'type': 'web-services', 'external': True}, 'set_timestamp': u'1', 'max_service_check_spread': u'5', 'execute_host_checks': u'1', 'host_freshness_check_interval': u'1200', 'retention_update_interval': u'60', 'log_snapshots': u'1', 'accept_passive_service_checks': u'1', 'service_freshness_check_interval': u'1800', 'module_alias': u'web-services', 'module_types': [u''], 'alignak_name': u'alignak-fdj', 'max_queue_size': u'0', 'alignak_port': u'7770', 'type': u'web-services', 'authorization': u'1', 'logdir': u'/usr/local//var/log/alignak', 'username': u'admin', 'feedback_host': u'active_checks_enabled,check_interval,retry_interval,passive_checks_enabled,freshness_threshold', 'conf_is_correct': True, 'log_passive_checks': u'0', 'etcdir': u'/usr/local//etc/alignak', 'check_service_freshness': u'0', 'daemons_check_period': u'5', 'configuration_warnings': [], 'imported_from': 'unknown', 'max_host_check_spread': u'5', 'config_name': u'Alignak FdJ configuration', 'statsd_port': 8125, 'accept_passive_host_checks': u'1', 'log_active_checks': u'0', 'allow_host_creation': u'1', 'no_event_handlers_during_downtimes': u'1', 'log_service_retries': u'1', 'accept_passive_unknown_check_results': u'1', 'alignak_backend_timeshift': u'5', 'allow_service_creation': u'0', 'use_ssl': u'0', 'daemons_log_folder': u'/usr/local//var/log/alignak', 'realm': u'All', 'realm_case': u'upper', 'polling_interval': u'5', 'enable_environment_macros': u'0', 'workdir': u'/usr/local//var/run/alignak', 'log_flappings': u'1', 'customs': {}, 'user': u'alignak', 'log_level': u'DEBUG', 'configuration_errors': [], 'register': True, 'alias': u'web-services'}
        [2018-03-31 11:43:42] DEBUG: [receiver-master.alignak.module.web-services] loaded into: unknown

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
            # Do not set a timestamp in the built external commands
            'set_timestamp': '0',
            # Send a log_check_result to the alignak backend
            'alignak_backend_old_lcr': '1',
            'alignak_backend_get_lcr': '0',
            'alignak_backend_timeshift': '0',
            # Do not give feedback data
            'give_feedback': '0',
            'give_result': '1',
            # Set Arbiter address as empty to not poll the Arbiter else the test will fail!
            'alignak_host': '',
            'alignak_port': 7770,
            # Set module to listen on all interfaces
            'host': '0.0.0.0',
            'port': 8888,
            # Activate CherryPy file logs
            'log_access': '/tmp/alignak-module-ws-access.log',
            'log_error': '/tmp/alignak-module-ws-error.log',

            # Allow host/service creation
            'allow_host_creation': '1',
            'allow_service_creation': '1',
            # Force Alignak backend update by the module (default is not force!)
            'alignak_backend_livestate_update': '1'
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

        # Alignak backend
        # ---
        self.endpoint = 'http://127.0.0.1:5000'
        headers = {'Content-Type': 'application/json'}
        params = {'username': 'admin', 'password': 'admin'}
        # get token
        response = requests.post(self.endpoint + '/login', json=params, headers=headers)
        resp = response.json()
        self.token = resp['token']
        self.auth = requests.auth.HTTPBasicAuth(self.token, '')

        session = requests.Session()

        headers = {'Content-Type': 'application/json'}
        params = {'username': 'admin', 'password': 'admin'}
        response = session.post(self.ws_endpoint + '/login', json=params, headers=headers)
        assert response.status_code == 200
        resp = response.json()
        #
        # #
        # # # Freeze the time !
        # initial_datetime = datetime.datetime(2017, 12, 1, 12, 0, 0)
        # initial_datetime = datetime.datetime.now()
        # with freeze_time(initial_datetime) as frozen_datetime:
        #     assert frozen_datetime() == datetime.datetime.now()
        #     frozen_datetime.tick(delta=datetime.timedelta(seconds=10))

        # -----
        # Create a new host with an host livestate (heartbeat / host is alive): livestate
        data = {
            "name": "new_host_0",
            "livestate": {
                # No timestamp in the livestate
                "state": "UP",
                "output": "Output...",
                "long_output": "Long output...",
                "perf_data": "'counter'=1",
            }
        }
        self.assertEqual(my_module.received_commands, 0)
        response = session.patch(self.ws_endpoint + '/host', json=data, headers=headers)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result, {
            u'_status': u'OK',
            u'_result': [
                u'new_host_0 is alive :)',
                u"Requested host 'new_host_0' does not exist.",
                u"Requested host 'new_host_0' created.",
                u"PROCESS_HOST_CHECK_RESULT;new_host_0;0;Output...|'counter'=1\nLong output...",
                u"Host 'new_host_0' updated."
            ]
        })
        # No errors!

        # Get new host in the backend
        response = requests.get(self.endpoint + '/host', auth=self.auth, params={'where': json.dumps({'name': 'new_host_0'})})
        resp = response.json()
        new_host_0 = resp['_items'][0]
        self.assertEqual('new_host_0', new_host_0['name'])

        # Get backend check results - no check result sent to the backend
        response = requests.get(self.endpoint + '/logcheckresult', auth=self.auth)
        resp = response.json()
        rl = resp['_items']
        self.assertEqual(len(rl), 0)

        # -----
        # Send an host livestate
        # The former host livestate created an host last_check
        data = {
            "name": "new_host_0",
            "livestate": {
                # No timestamp in the livestate
                "state": "UP",
                "output": "Output...",
                "long_output": "Long output...",
                "perf_data": "'counter'=1",
            }
        }
        self.assertEqual(my_module.received_commands, 0)
        response = session.patch(self.ws_endpoint + '/host', json=data, headers=headers)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result, {
            u'_status': u'OK',
            u'_result': [
                u'new_host_0 is alive :)',
                u"PROCESS_HOST_CHECK_RESULT;new_host_0;0;Output...|'counter'=1\nLong output...",
                u"Host 'new_host_0' updated."
            ]
        })
        # No errors!

        # Get backend check results - no check result sent to the backend
        response = requests.get(self.endpoint + '/logcheckresult', auth=self.auth)
        resp = response.json()
        rl = resp['_items']
        self.assertEqual(len(rl), 0)


        # -----
        # Send an host livestate with a timestamp in the past
        now = int(time.time()) - 3600
        data = {
            "name": "new_host_0",
            "livestate": {
                # Timestamp in the past
                "timestamp": now,
                "state": "UP",
                "output": "Output...",
                "long_output": "Long output...",
                "perf_data": "'counter'=1",
            }
        }
        self.assertEqual(my_module.received_commands, 1)
        response = session.patch(self.ws_endpoint + '/host', json=data, headers=headers)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result, {
            u'_status': u'OK',
            u'_result': [
                u'new_host_0 is alive :)',
                u"[%d] PROCESS_HOST_CHECK_RESULT;new_host_0;0;Output...|'counter'=1\nLong output..." % now,
                u"Host 'new_host_0' updated."
            ]
        })
        # No errors!

        # Get backend check results - a check result was recorded in the backend
        response = requests.get(self.endpoint + '/logcheckresult', auth=self.auth)
        resp = response.json()
        rl = resp['_items']
        # A log check result was recorded...
        self.assertEqual(len(rl), 1)
        rl = resp['_items'][0]
        print("LCR: %s" % rl)
        # ...with the correct timestamp
        self.assertEqual(rl['host_name'], "new_host_0")
        self.assertEqual(rl['last_check'], now)

        # -----
        # Send an host livestate with a timestamp in the past but sooner than the former one
        now = now + 1800
        data = {
            "name": "new_host_0",
            "livestate": {
                # Timestamp in the past
                "timestamp": now,
                "state": "UP",
                "output": "Output...",
                "long_output": "Long output...",
                "perf_data": "'counter'=1",
            }
        }
        self.assertEqual(my_module.received_commands, 2)
        response = session.patch(self.ws_endpoint + '/host', json=data, headers=headers)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result, {
            u'_status': u'OK',
            u'_result': [
                u'new_host_0 is alive :)',
                u"[%d] PROCESS_HOST_CHECK_RESULT;new_host_0;0;Output...|'counter'=1\nLong output..." % now,
                u"Host 'new_host_0' updated."
            ]
        })
        # No errors!

        # Get backend check results - one more check result was recorded in the backend
        response = requests.get(self.endpoint + '/logcheckresult', auth=self.auth)
        resp = response.json()
        rl = resp['_items']
        # A log check result was recorded...
        self.assertEqual(len(rl), 2)
        # Get the second LCR
        rl = resp['_items'][1]
        print("LCR: %s" % rl)
        # ...with the correct timestamp
        self.assertEqual(rl['host_name'], "new_host_0")
        self.assertEqual(rl['last_check'], now)

        # Logout
        response = session.get(self.ws_endpoint + '/logout')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result['_status'], 'OK')
        self.assertEqual(result['_result'], 'Logged out')

        self.modulemanager.stop_all()

    def test_module_host_livestate_multiple(self):
        """Test the module /host API - host with multiple livestate
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
            # Do not set a timestamp in the built external commands
            'set_timestamp': '0',
            # Send a log_check_result to the alignak backend
            'alignak_backend_old_lcr': '1',
            'alignak_backend_get_lcr': '0',
            'alignak_backend_timeshift': '0',
            # Do not give feedback data
            'give_feedback': '0',
            'give_result': '1',
            # Set Arbiter address as empty to not poll the Arbiter else the test will fail!
            'alignak_host': '',
            'alignak_port': 7770,
            # Allow host/service creation
            'allow_host_creation': '1',
            'allow_service_creation': '1'
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

        # Alignak backend
        # ---
        self.endpoint = 'http://127.0.0.1:5000'
        headers = {'Content-Type': 'application/json'}
        params = {'username': 'admin', 'password': 'admin'}
        # get token
        response = requests.post(self.endpoint + '/login', json=params, headers=headers)
        resp = response.json()
        self.token = resp['token']
        self.auth = requests.auth.HTTPBasicAuth(self.token, '')

        session = requests.Session()

        headers = {'Content-Type': 'application/json'}
        params = {'username': 'admin', 'password': 'admin'}
        response = session.post(self.ws_endpoint + '/login', json=params, headers=headers)
        assert response.status_code == 200
        resp = response.json()

        # -----
        # Create a new host with an host livestate (heartbeat / host is alive): livestate
        data = {
            "name": "very_new_host_0",
            "livestate": {
                # No timestamp in the livestate
                "state": "UP",
                "output": "Output...",
                "long_output": "Long output...",
                "perf_data": "'counter'=1",
            }
        }
        self.assertEqual(my_module.received_commands, 0)
        response = session.patch(self.ws_endpoint + '/host', json=data, headers=headers)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result, {
            u'_status': u'OK',
            u'_result': [
                u'very_new_host_0 is alive :)',
                u"Requested host 'very_new_host_0' does not exist.",
                u"Requested host 'very_new_host_0' created.",
                u"PROCESS_HOST_CHECK_RESULT;very_new_host_0;0;Output...|'counter'=1\nLong output...",
                u"Host 'very_new_host_0' updated."
            ]
        })
        # No errors!

        # Get new host in the backend
        response = requests.get(self.endpoint + '/host', auth=self.auth,
                                params={'where': json.dumps({'name': 'very_new_host_0'})})
        resp = response.json()
        very_new_host_0 = resp['_items'][0]
        self.assertEqual('very_new_host_0', very_new_host_0['name'])

        # Get backend check results - no check result sent to the backend
        response = requests.get(self.endpoint + '/logcheckresult', auth=self.auth)
        resp = response.json()
        rl = resp['_items']
        self.assertEqual(len(rl), 0)


        # -----
        # Send an host multiple livestate with different timestamp
        now = int(time.time()) - 3600
        data = {
            "name": "very_new_host_0",
            "livestate": [
                {
                    "timestamp": now,
                    "state": "UP",
                    "output": "Output...",
                    "long_output": "Long output...",
                    "perf_data": "'counter'=1",
                },
                {
                    "timestamp": now + 1000,
                    "state": "UP",
                    "output": "Output...",
                    "long_output": "Long output...",
                    "perf_data": "'counter'=2",
                }
            ]
        }
        response = session.patch(self.ws_endpoint + '/host', json=data, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(my_module.received_commands, 2)
        result = response.json()
        self.assertEqual(result, {
            u'_status': u'OK',
            u'_result': [
                u'very_new_host_0 is alive :)',
                u"[%d] PROCESS_HOST_CHECK_RESULT;very_new_host_0;0;"
                u"Output...|'counter'=1\nLong output..." % now,
                u"[%d] PROCESS_HOST_CHECK_RESULT;very_new_host_0;0;"
                u"Output...|'counter'=2\nLong output..." % (now + 1000),
                # u"Host 'very_new_host_0' updated."
            ]
        })
        # No errors!

        # -----
        # Send an host multiple livestate with different timestamp (unordered!)
        now = int(time.time()) - 3600
        data = {
            "name": "very_new_host_0",
            "livestate": [
                {
                    "timestamp": now,
                    "state": "UP",
                    "output": "Output...",
                    "long_output": "Long output...",
                    "perf_data": "'counter'=1",
                },
                {
                    "timestamp": now - 1000,    # Older than the former one!
                    "state": "UP",
                    "output": "Output...",
                    "long_output": "Long output...",
                    "perf_data": "'counter'=2",
                }
            ]
        }
        response = session.patch(self.ws_endpoint + '/host', json=data, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(my_module.received_commands, 4)
        result = response.json()
        self.assertEqual(result, {
            u'_status': u'OK',
            u'_result': [
                u'very_new_host_0 is alive :)',
                u"[%d] PROCESS_HOST_CHECK_RESULT;very_new_host_0;0;"
                u"Output...|'counter'=1\nLong output..." % now,
                u"[%d] PROCESS_HOST_CHECK_RESULT;very_new_host_0;0;"
                u"Output...|'counter'=2\nLong output..." % (now - 1000),
                # u"Host 'very_new_host_0' updated."
            ]
        })
        # No errors!

        # Logout
        response = session.get(self.ws_endpoint + '/logout')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result['_status'], 'OK')
        self.assertEqual(result['_result'], 'Logged out')

        self.modulemanager.stop_all()

    def test_module_host_livestate_past(self):
        """Test the module /host API - host with multiple livestate in the past
        :return:
        """
        # Debug log level
        # self.set_debug_log()

        # Create an Alignak module
        mod = Module({
            'module_alias': 'web-services',
            'module_types': 'web-services',
            'python_name': 'alignak_module_ws',
            'log_level': 'DEBUG',
            # # Alignak backend
            'alignak_backend': 'http://127.0.0.1:5000',
            # 'username': 'admin',
            # 'password': 'admin',
            # Do not set a timestamp in the built external commands
            'set_timestamp': '0',
            # # Send a log_check_result to the alignak backend
            # 'alignak_backend_old_lcr': '1',
            # 'alignak_backend_get_lcr': '0',
            # 'alignak_backend_timeshift': '40000',
            # Do not give feedback data
            'give_feedback': '0',
            'give_result': '1',
            # # Set Arbiter address as empty to not poll the Arbiter else the test will fail!
            # 'alignak_host': '',
            # 'alignak_port': 7770,
            # # Allow host/service creation
            'allow_host_creation': '1',
            # 'allow_service_creation': '1'
        })

        # Create a receiver daemon
        args = {'env_file': './cfg/alignak.ini', 'daemon_name': 'receiver-master'}
        self._receiver_daemon = Receiver(**args)
        # Create the modules manager for the daemon
        self.modulemanager = ModulesManager(self._receiver_daemon)
        # Load an initialize the modules:
        #  - load python module
        #  - get module properties and instances
        self.modulemanager.load_and_init([mod])

        self.clear_logs()
        # Start external modules
        self.modulemanager.start_external_instances()

        # Starting external module logs
        self.show_logs()
        self.assert_log_match("Trying to initialize module: web-services", 0)
        self.assert_log_match("Starting external module web-services", 1)
        self.assert_log_match("Starting external process for module web-services", 2)
        self.assert_log_match("web-services is now started", 3)

        # Check alive
        my_module = self.modulemanager.instances[0]
        self.assertIsNotNone(my_module.process)
        self.assertTrue(my_module.process.is_alive())

        time.sleep(1)

        # Alignak backend connection
        # ---
        self.endpoint = 'http://127.0.0.1:5000'
        headers = {'Content-Type': 'application/json'}
        params = {'username': 'admin', 'password': 'admin'}
        response = requests.post(self.endpoint + '/login', json=params, headers=headers)
        resp = response.json()
        self.token = resp['token']
        self.auth = requests.auth.HTTPBasicAuth(self.token, '')

        # Alignak WS connection
        # ---
        headers = {'Content-Type': 'application/json'}
        params = {'username': 'admin', 'password': 'admin'}
        session = requests.Session()
        response = session.post(self.ws_endpoint + '/login', json=params, headers=headers)
        assert response.status_code == 200
        resp = response.json()
        self.token = resp['_result'][0]
        self.auth_ws = requests.auth.HTTPBasicAuth(self.token, '')

        # -----
        # Create a new host with an host livestate (heartbeat / host is alive): livestate
        data = {
            "name": "past_host_0",
            "livestate": {
                # No timestamp in the livestate
                "state": "UP",
                "output": "Output...",
                "long_output": "Long output...",
                "perf_data": "'counter'=0",
            }
        }
        self.assertEqual(my_module.received_commands, 0)
        response = session.patch(self.ws_endpoint + '/host', json=data, headers=headers,
                                 auth=self.auth_ws)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result, {
            u'_status': u'OK',
            u'_result': [
                u'past_host_0 is alive :)',
                u"Requested host 'past_host_0' does not exist.",
                u"Requested host 'past_host_0' created.",
                u"PROCESS_HOST_CHECK_RESULT;past_host_0;0;Output...|'counter'=0\nLong output...",
                u"Host 'past_host_0' updated."
            ]
        })
        # No errors!

        # Get new host in the backend
        response = requests.get(self.endpoint + '/host', auth=self.auth,
                                params={'where': json.dumps({'name': 'past_host_0'})})
        resp = response.json()
        past_host_0 = resp['_items'][0]
        self.assertEqual('past_host_0', past_host_0['name'])

        # Get backend check results - no check result sent to the backend
        response = requests.get(self.endpoint + '/logcheckresult', auth=self.auth)
        resp = response.json()
        rl = resp['_items']
        self.assertEqual(len(rl), 0)
        # No check result because the host just got created and
        # then the livestate command is not sent to Alignak. If it was sent,
        # the scheduler do not yet know the nely created host :(

        self.show_logs()
        self.clear_logs()

        # -----
        # Send an host multiple livestate with different timestamp in the past
        now = int(time.time()) - 3600
        data = {
            "name": "past_host_0",
            "livestate": [
                {
                    "timestamp": now,
                    "state": "UP",
                    "output": "Output...",
                    "long_output": "Long output...",
                    "perf_data": "'counter'=1",
                },
                {
                    "timestamp": now + 1000,
                    "state": "UP",
                    "output": "Output...",
                    "long_output": "Long output...",
                    "perf_data": "'counter'=2",
                }
            ]
        }
        self.assertEqual(my_module.received_commands, 0)
        response = session.patch(self.ws_endpoint + '/host', json=data, headers=headers,
                                 auth=self.auth_ws)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(my_module.received_commands, 2)
        result = response.json()
        self.assertEqual(result, {
            u'_status': u'OK',
            u'_result': [
                u'past_host_0 is alive :)',
                u"[%d] PROCESS_HOST_CHECK_RESULT;past_host_0;0;"
                u"Output...|'counter'=1\nLong output..." % now,
                u"[%d] PROCESS_HOST_CHECK_RESULT;past_host_0;0;"
                u"Output...|'counter'=2\nLong output..." % (now + 1000),
            ]
        })
        # No errors!

        self.show_logs()
        self.clear_logs()

        # -----
        # Send an host multiple livestate with different timestamp (unordered!)
        now = int(time.time()) - 3600
        data = {
            "name": "past_host_0",
            "livestate": [
                {
                    "timestamp": now,
                    "state": "UP",
                    "output": "Output...",
                    "long_output": "Long output...",
                    "perf_data": "'counter'=1",
                },
                {
                    "timestamp": now - 1000,    # Older than the former one!
                    "state": "UP",
                    "output": "Output...",
                    "long_output": "Long output...",
                    "perf_data": "'counter'=2",
                }
            ]
        }
        response = session.patch(self.ws_endpoint + '/host', json=data, headers=headers,
                                 auth=self.auth_ws)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(my_module.received_commands, 4)
        result = response.json()
        self.assertEqual(result, {
            u'_status': u'OK',
            u'_result': [
                u'past_host_0 is alive :)',
                u"[%d] PROCESS_HOST_CHECK_RESULT;past_host_0;0;"
                u"Output...|'counter'=1\nLong output..." % now,
                u"[%d] PROCESS_HOST_CHECK_RESULT;past_host_0;0;"
                u"Output...|'counter'=2\nLong output..." % (now - 1000),
            ]
        })
        # No errors!

        # Logout
        response = session.get(self.ws_endpoint + '/logout')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result['_status'], 'OK')
        self.assertEqual(result['_result'], 'Logged out')

        self.modulemanager.stop_all()

    def test_module_service_livestate(self):
        """Test the module /host API - service creation and livestate
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
            # Do not set a timestamp in the built external commands
            'set_timestamp': '0',
            # Send a log_check_result to the alignak backend
            'alignak_backend_old_lcr': '1',
            # Do not give feedback data
            'give_feedback': '0',
            'give_result': '1',
            # Set Arbiter address as empty to not poll the Arbiter else the test will fail!
            'alignak_host': '',
            'alignak_port': 7770,
            # Set module to listen on all interfaces
            'host': '0.0.0.0',
            'port': 8888,
            # Allow host/service creation
            'allow_host_creation': '1',
            'allow_service_creation': '1'
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

        # Alignak backend
        # ---
        self.endpoint = 'http://127.0.0.1:5000'
        headers = {'Content-Type': 'application/json'}
        params = {'username': 'admin', 'password': 'admin'}
        # get token
        response = requests.post(self.endpoint + '/login', json=params, headers=headers)
        resp = response.json()
        self.token = resp['token']
        self.auth = requests.auth.HTTPBasicAuth(self.token, '')

        # Do not allow GET request on /host - not authorized
        response = requests.get(self.ws_endpoint + '/host')
        self.assertEqual(response.status_code, 401)

        session = requests.Session()

        # Login with username/password (real backend login)
        headers = {'Content-Type': 'application/json'}
        params = {'username': 'admin', 'password': 'admin'}
        response = session.post(self.ws_endpoint + '/login', json=params, headers=headers)
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
        response = session.patch(self.ws_endpoint + '/host', json=data, headers=headers)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result, {
            u'_status': u'OK',
            u'_result': [
                u'new_host_for_services_0 is alive :)',
                u"Requested host 'new_host_for_services_0' does not exist.",
                u"Requested host 'new_host_for_services_0' created."
            ]
        })
        # No errors!

        # Get new host in the backend
        response = requests.get(self.endpoint + '/host', auth=self.auth, params={'where': json.dumps({'name': 'new_host_for_services_0'})})
        resp = response.json()
        new_host_for_services_0 = resp['_items'][0]
        self.assertEqual('new_host_for_services_0', new_host_for_services_0['name'])

        # Get backend check results - no check result sent to the backend
        response = requests.get(self.endpoint + '/logcheckresult', auth=self.auth)
        resp = response.json()
        rl = resp['_items']
        self.assertEqual(len(rl), 0)


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
        response = session.patch(self.ws_endpoint + '/host', json=data, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(my_module.received_commands, 1)
        result = response.json()
        self.assertEqual(result, {
            u'_status': u'OK',
            u'_result': [
                u'new_host_for_services_0 is alive :)',
                u"Requested service 'new_host_for_services_0/test_empty_0' does not exist.",
                u"Requested service 'new_host_for_services_0/test_empty_0' created.",
                u"PROCESS_SERVICE_CHECK_RESULT;new_host_for_services_0;test_empty_0;0;Output...|'counter'=1\nLong output...",
                u"Service 'new_host_for_services_0/test_empty_0' updated",
            ]
        })
        # No errors!

        # Get new host to confirm creation
        response = requests.get(self.endpoint + '/host', auth=self.auth,
                                params={'where': json.dumps({'name': 'new_host_for_services_0'})})
        resp = response.json()
        new_host_for_services_0 = resp['_items'][0]
        self.assertEqual('new_host_for_services_0', new_host_for_services_0['name'])
        # Default live state
        self.assertEqual(new_host_for_services_0['ls_state'], "UNREACHABLE")
        self.assertEqual(new_host_for_services_0['ls_state_id'], 3)
        self.assertEqual(new_host_for_services_0['ls_state_type'], "HARD")
        self.assertEqual(new_host_for_services_0['ls_output'], "")
        self.assertEqual(new_host_for_services_0['ls_long_output'], "")
        self.assertEqual(new_host_for_services_0['ls_perf_data'], "")

        # Get services data to confirm update
        response = requests.get(self.endpoint + '/service', auth=self.auth,
                                params={'where': json.dumps({'host': new_host_for_services_0['_id'],
                                                             'name': 'test_empty_0'})})
        resp = response.json()
        service = resp['_items'][0]
        expected = {
            u'_TEST3': 5.0, u'_TEST2': 1, u'_TEST1': u'string'
        }
        self.assertEqual(expected, service['customs'])


        # Send a service livestate, no timestamp
        headers = {'Content-Type': 'application/json'}
        data = {
            "name": "new_host_for_services_0",
            "services": [
                {
                    "name": "test_empty_0",
                    "livestate": {
                        # No timestamp in the livestate
                        "state": "OK",
                        "output": "Output...",
                        "long_output": "Long output...",
                        "perf_data": "'counter'=1",
                    }
                }
            ]
        }
        response = session.patch(self.ws_endpoint + '/host', json=data, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(my_module.received_commands, 2)
        result = response.json()
        self.assertEqual(result, {
            u'_status': u'OK',
            u'_result': [
                u'new_host_for_services_0 is alive :)',
                u"PROCESS_SERVICE_CHECK_RESULT;new_host_for_services_0;test_empty_0;0;Output...|'counter'=1\nLong output...",
                # u"Service 'new_host_for_services_0/test_empty_0' updated"
            ]
        })
        # No errors!

        # Get backend check results - no check result sent to the backend
        response = requests.get(self.endpoint + '/logcheckresult', auth=self.auth)
        resp = response.json()
        rl = resp['_items']
        self.assertEqual(len(rl), 0)


        # Send a service livestate, timestamp in the past
        # Example data for the backend:
        # a = {
        #     'ls_perf_data': '',
        #     'ls_output': u'Ok -  Microsoft Input Configuration Device (Microsoft Input Configuration Device) - Init',
        #     'ls_state': u'OK', 'ls_last_check': 1511952153, 'ls_long_output': '',
        #     u'passive_checks_enabled': False, 'ls_state_id': 0, 'ls_state_type': 'HARD'
        # }
        # b = {
        #     'ls_perf_data': '', 'ls_output': u'NearEmpty - Battery Power - Init',
        #     'ls_state': u'WARNING', 'ls_last_check': 1511977215,
        #     'customs': {u'_ID': u'Energy', u'_VERSION': u'3.9.10',
        #                 u'_DESCRIPTION': u'Energy Management'}, 'ls_long_output': '',
        #     u'passive_checks_enabled': False, 'ls_state_id': 1, 'ls_state_type': 'HARD'
        # }
        headers = {'Content-Type': 'application/json'}
        now = int(time.time()) - 3600
        data = {
            "name": "new_host_for_services_0",
            "services": [
                {
                    "name": "test_empty_0",
                    "livestate": {
                        # Timestamp in the past
                        "timestamp": now,
                        "state": "OK",
                        "output": "Output...",
                        "long_output": "Long output...",
                        "perf_data": "'counter'=1",
                    }
                }
            ]
        }
        response = session.patch(self.ws_endpoint + '/host', json=data, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(my_module.received_commands, 3)
        result = response.json()
        self.assertEqual(result, {
            u'_status': u'OK',
            u'_result': [
                u'new_host_for_services_0 is alive :)',
                u"[%d] PROCESS_SERVICE_CHECK_RESULT;new_host_for_services_0;test_empty_0;0;Output...|'counter'=1\nLong output..." % now,
                # u"Service 'new_host_for_services_0/test_empty_0' updated"
            ]
        })
        # No errors!

        # Get backend check results - a check result was recorded in the backend
        response = requests.get(self.endpoint + '/logcheckresult', auth=self.auth)
        resp = response.json()
        rl = resp['_items']
        # A log check result was recorded...
        self.assertEqual(len(rl), 1)
        rl = resp['_items'][0]
        print("LCR: %s" % rl)
        # ...with the correct timestamp
        self.assertEqual(rl['host_name'], "new_host_for_services_0")
        self.assertEqual(rl['service_name'], "test_empty_0")
        self.assertEqual(rl['last_check'], now)


        # Send a service livestate with a timestamp in the past but sooner than the former one
        now = now + 1800
        data = {
            "name": "new_host_for_services_0",
            "services": [
                {
                    "name": "test_empty_0",
                    "livestate": {
                        # Timestamp in the past
                        "timestamp": now,
                        "state": "OK",
                        "output": "Output...",
                        "long_output": "Long output...",
                        "perf_data": "'counter'=1",
                    }
                }
            ]
        }
        response = session.patch(self.ws_endpoint + '/host', json=data, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(my_module.received_commands, 4)
        result = response.json()
        self.assertEqual(result, {
            u'_status': u'OK',
            u'_result': [
                u'new_host_for_services_0 is alive :)',
                u"[%d] PROCESS_SERVICE_CHECK_RESULT;new_host_for_services_0;test_empty_0;0;Output...|'counter'=1\nLong output..." % now,
                # u"Service 'new_host_for_services_0/test_empty_0' updated"
            ]
        })
        # No errors!

        # Get backend check results - a check result was recorded in the backend
        response = requests.get(self.endpoint + '/logcheckresult', auth=self.auth)
        resp = response.json()
        rl = resp['_items']
        # A log check result was recorded...
        self.assertEqual(len(rl), 2)
        rl = resp['_items'][1]
        print("LCR: %s" % rl)
        # ...with the correct timestamp
        self.assertEqual(rl['host_name'], "new_host_for_services_0")
        self.assertEqual(rl['service_name'], "test_empty_0")
        self.assertEqual(rl['last_check'], now)


        # Logout
        response = session.get(self.ws_endpoint + '/logout')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result['_status'], 'OK')
        self.assertEqual(result['_result'], 'Logged out')

        self.modulemanager.stop_all()

    def test_module_service_livestate_multiple(self):
        """Test the module /host API - service with multiple livestate
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
            # Do not set a timestamp in the built external commands
            'set_timestamp': '0',
            # Send a log_check_result to the alignak backend
            'alignak_backend_old_lcr': '1',
            # Do not give feedback data
            'give_feedback': '0',
            'give_result': '1',
            # Set Arbiter address as empty to not poll the Arbiter else the test will fail!
            'alignak_host': '',
            'alignak_port': 7770,
            # Allow host/service creation
            'allow_host_creation': '1',
            'allow_service_creation': '1'
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

        # Alignak backend
        # ---
        self.endpoint = 'http://127.0.0.1:5000'
        headers = {'Content-Type': 'application/json'}
        params = {'username': 'admin', 'password': 'admin'}
        # get token
        response = requests.post(self.endpoint + '/login', json=params, headers=headers)
        resp = response.json()
        self.token = resp['token']
        self.auth = requests.auth.HTTPBasicAuth(self.token, '')

        # Do not allow GET request on /host - not authorized
        response = requests.get(self.ws_endpoint + '/host')
        self.assertEqual(response.status_code, 401)

        session = requests.Session()

        # Login with username/password (real backend login)
        headers = {'Content-Type': 'application/json'}
        params = {'username': 'admin', 'password': 'admin'}
        response = session.post(self.ws_endpoint + '/login', json=params, headers=headers)
        assert response.status_code == 200
        resp = response.json()

        # Request to create an host - create a new host
        headers = {'Content-Type': 'application/json'}
        data = {
            "name": "very_new_host_for_services_0",
            "template": {
                "_realm": 'All',
                "check_command": "_internal_host_up"
            }
        }
        self.assertEqual(my_module.received_commands, 0)
        response = session.patch(self.ws_endpoint + '/host', json=data, headers=headers)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result, {
            u'_status': u'OK',
            u'_result': [
                u'very_new_host_for_services_0 is alive :)',
                u"Requested host 'very_new_host_for_services_0' does not exist.",
                u"Requested host 'very_new_host_for_services_0' created."
            ]
        })
        # No errors!

        # Request to create an host - create a new service without any template data
        headers = {'Content-Type': 'application/json'}
        data = {
            "name": "very_new_host_for_services_0",
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
        response = session.patch(self.ws_endpoint + '/host', json=data, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(my_module.received_commands, 1)
        result = response.json()
        self.assertEqual(result, {
            u'_status': u'OK',
            u'_result': [
                u'very_new_host_for_services_0 is alive :)',
                u"Requested service 'very_new_host_for_services_0/test_empty_0' does not exist.",
                u"Requested service 'very_new_host_for_services_0/test_empty_0' created.",
                u"PROCESS_SERVICE_CHECK_RESULT;very_new_host_for_services_0;test_empty_0;0;"
                u"Output...|'counter'=1\nLong output...",
                u"Service 'very_new_host_for_services_0/test_empty_0' updated",
            ]
        })
        # No errors!

        # Send a service with multiple livestate, ordered timestamps
        headers = {'Content-Type': 'application/json'}
        now = int(time.time()) - 3600
        data = {
            "name": "very_new_host_for_services_0",
            "services": [
                {
                    "name": "test_empty_0",
                    "livestate": [
                        {
                            "timestamp": now,
                            "state": "OK",
                            "output": "Output...",
                            "long_output": "Long output...",
                            "perf_data": "'counter'=1",
                        },
                        {
                            "timestamp": now + 1000,
                            "state": "OK",
                            "output": "Output...",
                            "long_output": "Long output...",
                            "perf_data": "'counter'=2",
                        }
                    ]
                }
            ]
        }
        response = session.patch(self.ws_endpoint + '/host', json=data, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(my_module.received_commands, 3)
        result = response.json()
        self.assertEqual(result, {
            u'_status': u'OK',
            u'_result': [
                u'very_new_host_for_services_0 is alive :)',
                u"[%d] PROCESS_SERVICE_CHECK_RESULT;very_new_host_for_services_0;test_empty_0;0;"
                u"Output...|'counter'=1\nLong output..." % now,
                u"[%d] PROCESS_SERVICE_CHECK_RESULT;very_new_host_for_services_0;test_empty_0;0;"
                u"Output...|'counter'=2\nLong output..." % (now + 1000),
            ]
        })
        # No errors!

        # Send a service with multiple livestate, unordered timestamps
        headers = {'Content-Type': 'application/json'}
        now = int(time.time()) - 3600
        data = {
            "name": "very_new_host_for_services_0",
            "services": [
                {
                    "name": "test_empty_0",
                    "livestate": [
                        {
                            "timestamp": now,
                            "state": "OK",
                            "output": "Output...",
                            "long_output": "Long output...",
                            "perf_data": "'counter'=1",
                        },
                        {
                            "timestamp": now - 1000,    # Older than the former one!
                            "state": "OK",
                            "output": "Output...",
                            "long_output": "Long output...",
                            "perf_data": "'counter'=2",
                        }
                    ]
                }
            ]
        }
        response = session.patch(self.ws_endpoint + '/host', json=data, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(my_module.received_commands, 5)
        result = response.json()
        self.assertEqual(result, {
            u'_status': u'OK',
            u'_result': [
                u'very_new_host_for_services_0 is alive :)',
                u"[%d] PROCESS_SERVICE_CHECK_RESULT;very_new_host_for_services_0;test_empty_0;0;"
                u"Output...|'counter'=1\nLong output..." % now,
                u"[%d] PROCESS_SERVICE_CHECK_RESULT;very_new_host_for_services_0;test_empty_0;0;"
                u"Output...|'counter'=2\nLong output..." % (now - 1000),
            ]
        })
        # No errors!

        # Logout
        response = session.get(self.ws_endpoint + '/logout')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result['_status'], 'OK')
        self.assertEqual(result['_result'], 'Logged out')

        self.modulemanager.stop_all()
