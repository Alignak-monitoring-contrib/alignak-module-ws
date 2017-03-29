#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (c) 2015-2017:
#   Frederic Mohier, frederic.mohier@alignak.net
#
# This file is part of (WebUI).
#
# (WebUI) is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# (WebUI) is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with (WebUI).  If not, see <http://www.gnu.org/licenses/>.

"""
    This module contains the cherrypy features to handle the WS authorization and the WS interface.
"""

import json
import logging
import inspect
import cherrypy
from cherrypy.lib import httpauth

from alignak.external_command import ExternalCommand
from alignak_module_ws.utils.helper import Helper

logger = logging.getLogger('alignak.module')  # pylint: disable=invalid-name

SESSION_KEY = 'alignak_web_services'


def protect(*args, **kwargs):
    # pylint: disable=unused-argument
    """Check user credentials from HTTP Authorization request header"""
    # logger.debug("Inside protect()...")

    authenticated = False
    conditions = cherrypy.request.config.get('auth.require', None)
    if conditions is not None:
        logger.debug("conditions: %s", conditions)
        # A condition is just a callable that returns true or false
        try:
            logger.debug("Checking session: %s", SESSION_KEY)
            # check if there is an active session
            # sessions are turned on so we just have to know if there is
            # something inside of cherrypy.session[SESSION_KEY]:
            this_session = cherrypy.session[SESSION_KEY]
            logger.debug("Session: %s", this_session)

            # Not sure if I need to do this myself or what
            cherrypy.session.regenerate()
            token = cherrypy.request.login = cherrypy.session[SESSION_KEY]
            authenticated = True
            logger.warning("Authenticated with session: %s", this_session)

        except KeyError:
            # If the session isn't set, it either was not existing or valid.
            # Now check if the request includes HTTP Authorization?
            authorization = cherrypy.request.headers.get('Authorization')
            logger.debug("Authorization: %s", authorization)
            if authorization:
                logger.warning("Got authorization header: %s", authorization)
                ah = httpauth.parseAuthorization(authorization)

                # Get module application from cherrypy request
                app = cherrypy.request.app.root.app
                logger.debug("Request backend login...")
                token = app.backendLogin(ah['username'], ah['password'])
                if token:

                    cherrypy.session.regenerate()

                    # This line of code is discussed in doc/sessions-and-auth.markdown
                    cherrypy.session[SESSION_KEY] = cherrypy.request.login = token
                    authenticated = True
                    logger.warning("Authenticated with backend")
                else:
                    logger.warning("Failed attempt to log in with authorization header.")
            else:
                logger.warning("Missing authorization header.")

        except:  # pylint: disable=bare-except
            logger.warning("Client has no valid session and did not provided "
                           "HTTP Authorization credentials.")

        if authenticated:
            for condition in conditions:
                if not condition():
                    logger.warning("Authentication succeeded but authorization failed.")
                    raise cherrypy.HTTPError("403 Forbidden")
        else:
            raise cherrypy.HTTPError("401 Unauthorized")
cherrypy.tools.wsauth = cherrypy.Tool('before_handler', protect)


def require(*conditions):
    """A decorator that appends conditions to the auth.require config
    variable."""
    def decorate(f):
        # pylint: disable=protected-access
        """Decorator function"""
        if not hasattr(f, '_cp_config'):
            f._cp_config = dict()
        if 'auth.require' not in f._cp_config:
            f._cp_config['auth.require'] = []
        f._cp_config['auth.require'].extend(conditions)
        return f
    return decorate


class WSInterface(object):
    """Interface for Alignak Web Services.

    """
    # _cp_config = {
    #     'tools.wsauth.on': True,
    #     'tools.sessions.on': True,
    #     'tools.sessions.name': 'alignak_ws',
    # }

    def __init__(self, app):
        self.app = app

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def login(self):
        """Validate user credentials"""
        if cherrypy.request.method != "POST":
            return {'_status': 'ERR', '_issues': ['You must only POST on this endpoint.']}

        username = cherrypy.request.json.get('username', None)
        password = cherrypy.request.json.get('password', None)

        # Get HTTP authentication
        authorization = cherrypy.request.headers.get('Authorization', None)
        if authorization:
            ah = httpauth.parseAuthorization(authorization)
            username = ah['username']
            password = ah['password']
        else:
            if cherrypy.request and not cherrypy.request.json:
                return {'_status': 'ERR', '_issues': ['You must POST parameters on this endpoint.']}

            if username is None:
                return {'_status': 'ERR', '_issues': ['Missing username parameter.']}

        token = self.app.backendLogin(username, password)
        if token is None:
            return {'_status': 'ERR', '_issues': ['Access denied.']}

        logger.debug("Backend login, token: %s", token)
        cherrypy.session[SESSION_KEY] = cherrypy.request.login = token
        return {'_status': 'OK', '_result': [token]}
    login.method = 'post'

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def logout(self):
        """Clean the cherrypy session"""
        cherrypy.session[SESSION_KEY] = cherrypy.request.login = None
        return {'_status': 'OK', '_result': 'Logged out'}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @require()
    def index(self):
        """Wrapper to call api from /

        :return: function list
        """
        return self.api()

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @require()
    def api(self):
        """List the methods available on the interface

        :return: a list of methods available
        :rtype: list
        """
        return [x[0]for x in inspect.getmembers(self, predicate=inspect.ismethod)
                if not x[0].startswith('__')]

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @require()
    def api_full(self):
        """List the api methods and their parameters

        :return: a list of methods and parameters
        :rtype: dict
        """
        full_api = {}
        for fun in self.api():
            full_api[fun] = {}
            full_api[fun][u"doc"] = getattr(self, fun).__doc__
            full_api[fun][u"args"] = {}

            spec = inspect.getargspec(getattr(self, fun))
            args = [a for a in spec.args if a != 'self']
            if spec.defaults:
                a_dict = dict(zip(args, spec.defaults))
            else:
                a_dict = dict(zip(args, (u"No default value",) * len(args)))

            full_api[fun][u"args"] = a_dict

        full_api[u"side_note"] = u"When posting data you have to serialize value. Example : " \
                                 u"POST /set_log_level " \
                                 u"{'loglevel' : serialize('INFO')}"

        return full_api

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @require()
    def are_you_alive(self):
        """Is the module alive

        :return: True if is alive, False otherwise
        :rtype: bool
        """
        return 'Yes I am :)'

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @require()
    def alignak_map(self):
        """Get the alignak internal map and state

        :return: A json array of the Alignak daemons state
        :rtype: list
        """
        return self.app.daemons_map

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    @require()
    def host(self, host_name=None):
        """ Declare an host and its data
        :return:
        """
        if cherrypy.request.method != "PATCH":
            return {'_status': 'ERR', '_error': 'You must only PATCH on this endpoint.'}

        if cherrypy.request and not cherrypy.request.json:
            return {'_status': 'ERR', '_error': 'You must send parameters on this endpoint.'}

        if host_name and cherrypy.request.json.get('name', None) is not None:
            host_name = cherrypy.request.json.get('name', None)

        if not host_name:
            host_name = cherrypy.request.json.get('name', None)

        if not host_name:
            return {'_status': 'ERR', '_result': '', '_issues': ['Missing targeted element.']}

        data = {
            'active_checks_enabled': cherrypy.request.json.get('active_checks_enabled', None),
            'passive_checks_enabled': cherrypy.request.json.get('passive_checks_enabled', None),
            'template': cherrypy.request.json.get('template', None),
            'livestate': cherrypy.request.json.get('livestate', None),
            'variables': cherrypy.request.json.get('variables', None),
            'services': cherrypy.request.json.get('services', None)
        }

        return self.app.updateHost(host_name, data)
    host.method = 'patch'

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    @require()
    def event(self):
        """ Notify an event
        :return:
        """
        if cherrypy.request.method != "POST":
            return {'_status': 'ERR', '_issues': ['You must only POST on this endpoint.']}

        if cherrypy.request and not cherrypy.request.json:
            return {'_status': 'ERR', '_issues': ['You must POST parameters on this endpoint.']}

        timestamp = cherrypy.request.json.get('timestamp', None)
        host = cherrypy.request.json.get('host', None)
        service = cherrypy.request.json.get('service', None)
        author = cherrypy.request.json.get('author', 'Alignak WS')
        comment = cherrypy.request.json.get('comment', None)

        if not host and not service:
            return {'_status': 'ERR', '_issues': ['Missing host and/or service parameter.']}

        if not comment:
            return {'_status': 'ERR', '_issues': ['Missing comment. If you do not have any '
                                                  'comment, do not comment ;)']}

        return self.app.buildPostComment(host, service, author, comment, timestamp)
    event.method = 'post'

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    @require()
    def command(self):
        """ Request to execute an external command
        :return:
        """
        if cherrypy.request.method != "POST":
            return {'_status': 'ERR', '_error': 'You must only POST on this endpoint.'}

        if cherrypy.request and not cherrypy.request.json:
            return {'_status': 'ERR', '_error': 'You must POST parameters on this endpoint.'}

        command = cherrypy.request.json.get('command', None)
        timestamp = cherrypy.request.json.get('timestamp', None)
        element = cherrypy.request.json.get('element', None)
        host = cherrypy.request.json.get('host', None)
        service = cherrypy.request.json.get('service', None)
        user = cherrypy.request.json.get('user', None)
        parameters = cherrypy.request.json.get('parameters', None)

        if not command:
            return {'_status': 'ERR', '_error': 'Missing command parameter'}

        command_line = command.upper()
        if timestamp:
            command_line = '[%d] %s' % (timestamp, command)

        if host or service or user:
            if host:
                command_line = '%s;%s' % (command_line, host)
            if service:
                command_line = '%s;%s' % (command_line, service)
            if user:
                command_line = '%s;%s' % (command_line, user)
        elif element:
            if '/' in element:
                # Replace only the first /
                element = element.replace('/', ';', 1)
            command_line = '%s;%s' % (command_line, element)

        if parameters:
            command_line = '%s;%s' % (command_line, parameters)

        # Add a command to get managed
        self.app.to_q.put(ExternalCommand(command_line))

        return {'_status': 'OK', '_command': command_line}
    command.method = 'post'

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @require()
    def alignak_logs(self, start=0, count=25, search=''):
        """Get the alignak logs

        :return: True if is alive, False otherwise
        :rtype: dict
        """
        start = int(cherrypy.request.params.get('start', '0'))
        count = int(cherrypy.request.params.get('count', '25'))
        where = Helper.decode_search(cherrypy.request.params.get('search', ''), None)
        search = {
            'page': (start // count) + 1,
            'max_results': count,
        }
        if where:
            search.update({'where': json.dumps(where)})

        return self.app.getBackendHistory(search)
