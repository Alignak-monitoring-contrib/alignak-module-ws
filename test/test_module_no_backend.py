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


class TestModuleNoBackend(AlignakTest):
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

        cls.modulemanager = None

    def setUp(self):
        super(TestModuleNoBackend, self).setUp()

    def tearDown(self):
        """Delete resources in backend

        :return: None
        """
        super(TestModuleNoBackend, self).tearDown()
        if self.modulemanager:
            self.modulemanager.stop_all()

    def test_module_host_livestate_unauthorized(self):
        """Test the module /host API - host livestate - unauthorized access
        :return:
        """
        # Create an Alignak module
        mod = Module({
            'module_alias': 'web-services',
            'module_types': 'web-services',
            'python_name': 'alignak_module_ws',
            # Alignak backend
            'alignak_backend': '',
            'username': '',
            'password': '',
            # Do not set a timestamp in the built external commands
            'set_timestamp': '0',
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
            'allow_service_creation': '1',
            # Force Alignak backend update by the module (default is not force!)
            'alignak_backend_livestate_update': '0',

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

        session = requests.Session()

        headers = {'Content-Type': 'application/json'}
        params = {'username': 'admin', 'password': 'admin'}
        response = session.post(self.ws_endpoint + '/login', json=params, headers=headers)
        assert response.status_code == 200
        resp = response.json()

        # -----
        # Update an host with an host livestate (heartbeat / host is alive): livestate
        # Because there is no backend configured, only an external command is raised
        # to Alignak for the host
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
        print(response)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result, {
            u'_status': u'OK',
            u'_result': [
                u'new_host_0 is alive :)',
                u"PROCESS_HOST_CHECK_RESULT;new_host_0;0;Output...|'counter'=1\nLong output...",
            ]
        })
        # No errors - an extrenal command was raised for the host livestate

        # -----
        # Update an host with an host livestate (heartbeat / host is alive): livestate
        # Because there is no backend configured, only an external command is raised
        # to Alignak for the host
        data = {
            "name": "new_host_0",
            "livestate": {
                # No timestamp in the livestate
                "state": "UP",
                "output": "Output...",
                "long_output": "Long output...",
                "perf_data": "'counter'=1",
            },
            "services": [
                {
                    "name": "test_svc_0",
                    "livestate": {
                        "state": "OK",
                        "output": "Output...",
                        "long_output": "Long output...",
                        "perf_data": "'counter'=1",
                    }
                }
            ]
        }
        self.assertEqual(my_module.received_commands, 1)
        response = session.patch(self.ws_endpoint + '/host', json=data, headers=headers)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result, {
            u'_status': u'OK',
            u'_result': [
                u'new_host_0 is alive :)',
                u"PROCESS_HOST_CHECK_RESULT;new_host_0;0;Output...|'counter'=1\nLong output...",
                u"PROCESS_SERVICE_CHECK_RESULT;new_host_0;test_svc_0;0;Output...|'counter'=1\nLong output..."
            ]
        })
        # No errors - an extrenal command was raised for the host livestate

        self.modulemanager.stop_all()
