# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2018: Alignak team, see AUTHORS.txt file for contributors
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
#
# This file incorporates work covered by the following copyright and
# permission notice:
#
"""This module provide the HTTP daemon for Alignak inter daemon communication.
It is mostly based on Cherrypy
"""
# import os
import socket
import logging

import cherrypy
# We need this to keep default processors in cherrypy
from cherrypy._cpreqbody import process_urlencoded, process_multipart, process_multipart_form_data
# load global helper objects for logs and stats computation
from alignak.http.cherrypy_extend import zlib_processor
# todo: daemonize the process thanks to CherryPy plugin
# from cherrypy.process.plugins import Daemonizer


# Check if PyOpenSSL is installed
# pylint: disable=unused-import
PYOPENSSL = True
try:
    from OpenSSL import SSL
    from OpenSSL import crypto
except ImportError:
    PYOPENSSL = False


logger = logging.getLogger(__name__)  # pylint: disable=C0103


class PortNotFree(Exception):
    """Exception raised when port is already used by another application"""
    pass


class HTTPDaemon(object):
    """HTTP Server class. Mostly based on Cherrypy
    """
    def __init__(self, module, http_interface):
        """
        Initialize HTTP daemon

        :param module: the Alignak module
        :param http_interface: the exposed application base class
        """
        self.uri = '%s://%s:%s' % ('https' if module.use_ssl else 'http', module.host, module.port)
        logger.info("Configured HTTP server on %s", self.uri)

        # This application config overrides the default processors
        # so we put them back in case we need them
        config = {
            '/': {
                'request.body.processors': {'application/x-www-form-urlencoded': process_urlencoded,
                                            'multipart/form-data': process_multipart_form_data,
                                            'multipart': process_multipart,
                                            'application/zlib': zlib_processor},
                'tools.gzip.on': True,
                'tools.gzip.mime_types': ['text/*', 'application/json']
            }
        }

        # Configure HTTP server
        # from cherrypy._cpserver import Server
        # self.server = Server()
        # self.server.thread_pool = module.daemon_thread_pool_size
        # self.server.socket_host = module.host
        # self.server.socket_port = module.port
        # self.server.subscribe()
        # cherrypy.config.update({'engine.autoreload.on': False,
        #                         'server.thread_pool': module.daemon_thread_pool_size,
        #                         'server.socket_host': module.host,
        #                         'server.socket_port': module.port})

        # # Default is to disable CherryPy logging
        # cherrypy.config.update({'log.screen': False,
        #                         'log.access_file': '',
        #                         'log.error_file': ''})
        # # My own HTTP interface...
        # cherrypy.config.update({"tools.wsauth.on": module.authorization})
        # cherrypy.config.update({"tools.sessions.on": True,
        #                         "tools.sessions.name": getattr(module, 'name',
        #                                                        getattr(module, 'alias'))})
        #
        # if module.log_error:
        #     cherrypy.config.update({'log.screen': True,
        #                             'log.error_file': str(module.log_error)})
        #     cherrypy.log.error_log.setLevel(logging.DEBUG)
        # if module.log_access:
        #     cherrypy.config.update({'log.screen': True,
        #                             'log.access_file': str(module.log_access)})
        #     cherrypy.log.access_log.setLevel(logging.DEBUG)
        #
        # if module.use_ssl:
        #     # Configure SSL server certificate and private key
        #     cherrypy.config.update({'server.ssl_certificate': module.ssl_cert,
        #                             'server.ssl_private_key': module.ssl_key})
        #     cherrypy.log("Using PyOpenSSL: %s" % (PYOPENSSL))
        #     if not PYOPENSSL:
        #         # Use CherryPy built-in module if PyOpenSSL is not installed
        #         cherrypy.config.update({'server.ssl_module': 'builtin'})
        #     cherrypy.log("Using SSL certificate: %s" % (module.ssl_cert))
        #     cherrypy.log("Using SSL private key: %s" % (module.ssl_key))
        #     if module.ca_cert:
        #         cherrypy.config.update({'server.ssl_certificate_chain': module.ca_cert})
        #         cherrypy.log("Using SSL CA certificate: %s" % module.ca_cert)

        cherrypy.log("Serving application: %s" % http_interface)

        # todo: daemonize the process thanks to CherryPy plugin
        # Daemonizer(cherrypy.engine).subscribe()

        # Mount the main application (an Alignak daemon interface)
        cherrypy.tree.mount(http_interface, '/ws', config)

    def run(self):
        """Wrapper to start the CherryPy server

        This function throws a PortNotFree exception if any socket error is raised.

        :return: None
        """
        return
        def _started_callback():
            """Callback function when Cherrypy Engine is started"""
            cherrypy.log("CherryPy engine started and listening...")

        self.cherrypy_thread = None
        try:
            cherrypy.log("Starting CherryPy engine on %s" % (self.uri))
            self.cherrypy_thread = cherrypy.engine.start_with_callback(_started_callback)
            cherrypy.engine.block()
            cherrypy.log("Exited from the engine block")
        except socket.error as exp:
            raise PortNotFree("Error: Sorry, the HTTP server did not started correctly: error: %s"
                              % (str(exp)))

    def stop(self):  # pylint: disable=no-self-use
        """Wrapper to stop the CherryPy server

        :return: None
        """
        cherrypy.log("Stopping CherryPy engine (current state: %s)..." % cherrypy.engine.state)
        return
        try:
            cherrypy.engine.exit()
        except RuntimeWarning:
            pass
        except SystemExit:
            cherrypy.log('SystemExit raised: shutting down bus')
        cherrypy.log("Stopped")



if __name__ == '__main__':
    print("Starting...")
    # Simulate Alignak receiver daemon
    class ReceiverItf(object):
        @cherrypy.expose
        def index(self):
            return "I am the Receiver daemon!"
    from alignak.http.daemon import HTTPDaemon as AlignakDaemon
    http_daemon1 = AlignakDaemon('0.0.0.0', 7773, ReceiverItf(),
                                 False, None, None, None, None, 10, '/tmp/alignak-cherrypy.log')
    def run_http_1():
        print("Thread !")
        http_daemon1.run()
    import threading
    http_thread1 = threading.Thread(target=run_http_1, name='http_thread_1')
    # http_thread1.daemon = True
    http_thread1.start()
    print("Thread started")

    print(cherrypy.server)

    # from cherrypy._cpserver import Server
    # server = Server()
    # server.thread_pool = 8
    # server.socket_host = '0.0.0.0'
    # server.socket_port = 7773
    # server.subscribe()
    #
    # cherrypy.quickstart(ReceiverItf())

    from alignak.objects import Module
    mod = Module({
        'module_alias': 'web-services',
        'module_types': 'web-services',
        'python_name': 'alignak_module_ws',
        # Activate CherryPy file logs
        'log_access': '/tmp/alignak-module-ws-access.log',
        'log_error': '/tmp/alignak-module-ws-error.log',
        # Alignak backend
        'alignak_backend': 'http://127.0.0.1:5000',
        'username': 'admin',
        'password': 'admin',
        # Set Arbiter address as empty to not poll the Arbiter else the test will fail!
        'alignak_host': '',
        'alignak_port': 7770,
        # Set module to listen on all interfaces
        'host': '0.0.0.0',
        'port': 7773,
        # Enable authorization
        'authorization': 1
    })
    from alignak_module_ws.ws import AlignakWebServices
    module = AlignakWebServices(mod)

    # module.alias = 'WS'
    module.host = '0.0.0.0'
    module.port = 8888

    from alignak_module_ws.utils.ws_server import WSInterface

    # cherrypy.engine.stop()
    http_daemon2 = HTTPDaemon(module, WSInterface(module))
    # http_daemon2.run()
