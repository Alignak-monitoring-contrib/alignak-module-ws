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


class TestModuleWsHostGet(AlignakTest):
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

    def test_module_zzz_host_get(self):
        """Test the module /host API - host creation and get information
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
            # Set Arbiter address as empty to not poll the Arbiter else the test will fail!
            'alignak_host': '',
            'alignak_port': 7770,
            # Allow host/service creation
            'allow_host_creation': '1',
            'allow_service_creation': '1',
            # Errors for unknown host/service
            'ignore_unknown_host': '0',
            'ignore_unknown_service': '0',
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

        # Do not allow GET request on /host - not yet authorized!
        response = requests.get('http://127.0.0.1:8888/host')
        self.assertEqual(response.status_code, 401)

        session = requests.Session()

        # Login with username/password (real backend login)
        headers = {'Content-Type': 'application/json'}
        params = {'username': 'test', 'password': 'test'}
        response = session.post('http://127.0.0.1:8888/login', json=params, headers=headers)
        assert response.status_code == 200
        resp = response.json()

        # -----
        # Get a non-existing host - 1st: use parameters in the request
        response = session.get('http://127.0.0.1:8888/host', auth=self.auth,
                                params={'name': 'new_host_2'})
        result = response.json()
        self.assertEqual(result, {
            u'_status': u'ERR',
            u'_result': [],
            u'_issues': [
                "Requested host 'new_host_2' does not exist"
            ]
        })

        # Get a non-existing host - 2nd: use host name in the URI
        response = session.get('http://127.0.0.1:8888/host/new_host_2', auth=self.auth)
        result = response.json()
        self.assertEqual(result, {
            u'_status': u'ERR',
            u'_result': [],
            u'_issues': [
                "Requested host 'new_host_2' does not exist"
            ]
        })

        # -----
        # Request to create an host - no provided data (default)
        headers = {'Content-Type': 'application/json'}
        data = {
            "name": "new_host_0",
        }
        self.assertEqual(my_module.received_commands, 0)
        response = session.patch('http://127.0.0.1:8888/host', json=data, headers=headers)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result, {
            u'_status': u'OK',
            u'_result': [
                u'new_host_0 is alive :)',
                u"Requested host 'new_host_0' does not exist.",
                u"Requested host 'new_host_0' created."],
            u'_feedback': {u'name': u'new_host_0'}
        })
        # Host created with default check_command and in default user realm

        # -----
        # Get new host to confirm creation - 1st: use parameters in the request
        response = session.get('http://127.0.0.1:8888/host', auth=self.auth,
                                params={'name': 'new_host_0'})
        result = response.json()
        self.assertEqual(result['_status'], 'OK')
        self.assertIsNot(result['_result'], {})
        self.assertEqual(result['_result'][0]['name'], 'new_host_0')

        # Get new host to confirm creation - 2nd: use host name in the URI
        response = session.get('http://127.0.0.1:8888/host/new_host_0', auth=self.auth)
        result = response.json()
        from pprint import pprint
        pprint(result['_result'])
        # [{u'2d_coords': u'',
        # u'3d_coords': u'',
        # u'_created': u'Thu, 01 Jun 2017 10:58:30 GMT',
        # u'_etag': u'691c3f4a7cc8996c1d047932421759c020d00857',
        # u'_id': u'592ff35606fd4b7eec395625',
        # u'_is_template': False,
        # u'_links': {u'self': {u'href': u'host/592ff35606fd4b7eec395625',
        #                       u'title': u'Host'}},
        # u'_overall_state_id': 3,
        # u'_realm': {u'_all_children': [],
        #             u'_children': [],
        #             u'_created': u'Thu, 01 Jun 2017 10:58:24 GMT',
        #             u'_etag': u'26b3830c017b4fca8553365246f21267aece46a7',
        #             u'_id': u'592ff35006fd4b7eec3955eb',
        #             u'_level': 0,
        #             u'_parent': None,
        #             u'_tree_parents': [],
        #             u'_updated': u'Thu, 01 Jun 2017 10:58:27 GMT',
        #             u'alias': u'',
        #             u'default': True,
        #             u'definition_order': 100,
        #             u'global_critical_threshold': 5,
        #             u'global_warning_threshold': 3,
        #             u'hosts_critical_threshold': 5,
        #             u'hosts_warning_threshold': 3,
        #             u'imported_from': u'unknown',
        #             u'name': u'All',
        #             u'notes': u'',
        #             u'services_critical_threshold': 5,
        #             u'services_warning_threshold': 3},
        # u'_sub_realm': True,
        # u'_template_fields': {},
        # u'_templates': [],
        # u'_templates_with_services': True,
        # u'_updated': u'Thu, 01 Jun 2017 10:58:30 GMT',
        # u'action_url': u'',
        # u'active_checks_enabled': True,
        # u'address': u'',
        # u'address6': u'',
        # u'alias': u'',
        # u'business_impact': 2,
        # u'business_impact_modulations': [],
        # u'business_rule_downtime_as_ack': False,
        # u'business_rule_host_notification_options': [u'd', u'u', u'r', u'f', u's'],
        # u'business_rule_output_template': u'',
        # u'business_rule_service_notification_options': [u'w',
        #                                                 u'u',
        #                                                 u'c',
        #                                                 u'r',
        #                                                 u'f',
        #                                                 u's'],
        # u'business_rule_smart_notifications': False,
        # u'check_command': {u'_created': u'Thu, 01 Jun 2017 10:58:24 GMT',
        #                    u'_etag': u'356d02479ca7dbebe85e22b9b43e95dc9d5d037c',
        #                    u'_id': u'592ff35006fd4b7eec3955f1',
        #                    u'_realm': u'592ff35006fd4b7eec3955eb',
        #                    u'_sub_realm': True,
        #                    u'_updated': u'Thu, 01 Jun 2017 10:58:24 GMT',
        #                    u'alias': u'Host/service is always UP/OK',
        #                    u'command_line': u'_internal_host_up',
        #                    u'definition_order': 100,
        #                    u'enable_environment_macros': False,
        #                    u'imported_from': u'unknown',
        #                    u'module_type': u'fork',
        #                    u'name': u'_internal_host_up',
        #                    u'notes': u'',
        #                    u'poller_tag': u'',
        #                    u'reactionner_tag': u'',
        #                    u'timeout': -1},
        # u'check_command_args': u'',
        # u'check_freshness': False,
        # u'check_interval': 5,
        # u'checkmodulations': [],
        # u'custom_views': [],
        # u'customs': {},
        # u'definition_order': 100,
        # u'display_name': u'',
        # u'escalations': [],
        # u'event_handler': None,
        # u'event_handler_args': u'',
        # u'event_handler_enabled': False,
        # u'failure_prediction_enabled': False,
        # u'first_notification_delay': 0,
        # u'flap_detection_enabled': True,
        # u'flap_detection_options': [u'o', u'd', u'x'],
        # u'freshness_state': u'x',
        # u'freshness_threshold': 0,
        # u'high_flap_threshold': 50,
        # u'icon_image': u'',
        # u'icon_image_alt': u'',
        # u'icon_set': u'',
        # u'imported_from': u'unknown',
        # u'initial_state': u'x',
        # u'labels': [],
        # u'location': {u'coordinates': [48.858293, 2.294601], u'type': u'Point'},
        # u'low_flap_threshold': 25,
        # u'ls_acknowledged': False,
        # u'ls_acknowledgement_type': 1,
        # u'ls_attempt': 0,
        # u'ls_current_attempt': 0,
        # u'ls_downtimed': False,
        # u'ls_execution_time': 0.0,
        # u'ls_grafana': False,
        # u'ls_grafana_panelid': 0,
        # u'ls_impact': False,
        # u'ls_last_check': 0,
        # u'ls_last_hard_state_changed': 0,
        # u'ls_last_notification': 0,
        # u'ls_last_state': u'OK',
        # u'ls_last_state_changed': 0,
        # u'ls_last_state_type': u'HARD',
        # u'ls_last_time_down': 0,
        # u'ls_last_time_unknown': 0,
        # u'ls_last_time_unreachable': 0,
        # u'ls_last_time_up': 0,
        # u'ls_latency': 0.0,
        # u'ls_long_output': u'',
        # u'ls_max_attempts': 0,
        # u'ls_next_check': 0,
        # u'ls_output': u'',
        # u'ls_passive_check': False,
        # u'ls_perf_data': u'',
        # u'ls_state': u'UNREACHABLE',
        # u'ls_state_id': 3,
        # u'ls_state_type': u'HARD',
        # u'macromodulations': [],
        # u'max_check_attempts': 1,
        # u'name': u'new_host_0',
        # u'notes': u'',
        # u'notes_url': u'',
        # u'notification_interval': 60,
        # u'notification_options': [u'd', u'x', u'r', u'f', u's'],
        # u'notifications_enabled': True,
        # u'obsess_over_host': False,
        # u'parents': [],
        # u'passive_checks_enabled': True,
        # u'poller_tag': u'',
        # u'process_perf_data': True,
        # u'reactionner_tag': u'',
        # u'resultmodulations': [],
        # u'retry_interval': 0,
        # u'service_excludes': [],
        # u'service_includes': [],
        # u'service_overrides': [],
        # u'snapshot_criteria': [u'd', u'x'],
        # u'snapshot_enabled': False,
        # u'snapshot_interval': 5,
        # u'stalking_options': [],
        # u'statusmap_image': u'',
        # u'tags': [],
        # u'time_to_orphanage': 300,
        # u'trending_policies': [],
        # u'trigger_broker_raise_enabled': False,
        # u'trigger_name': u'',
        # u'usergroups': [],
        # u'users': [],
        # u'vrml_image': u''}]
        # 
        self.assertEqual(result['_status'], 'OK')
        self.assertIsNot(result['_result'], {})
        self.assertEqual(result['_result'][0]['name'], 'new_host_0')

        # -----
        # Logout
        response = session.get('http://127.0.0.1:8888/logout')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result['_status'], 'OK')
        self.assertEqual(result['_result'], 'Logged out')

        self.modulemanager.stop_all()
