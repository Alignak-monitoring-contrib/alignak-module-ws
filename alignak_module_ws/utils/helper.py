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
    This module contains helper functions used in HTML application templates.

    An ``helper`` object linked to the application is created by this module to be used in all
    the application.
"""
import re
import time
from logging import getLogger

# pylint: disable=invalid-name
logger = getLogger(__name__)


class Helper(object):
    # pylint: disable=too-few-public-methods
    """Helper functions"""

    @staticmethod
    def decode_search(query, data_model=None):
        # Not possible to do it clearly with simplification...
        # pylint: disable=too-many-nested-blocks, too-many-locals, redefined-variable-type
        """Decode a search string:

        Convert string from:
            isnot:0 isnot:ack isnot:"downtime fred" name:"vm fred"
        to a backend search query expression.

        Search string is documented in the `modal_search_help.tpl` file

        :param query: search string
        :param data_model: table data model as built by the DataTable class

        :return: query to be provided to the data manager search objects function
        """
        logger.info("decode_search, search string: %s", query)

        # Search patterns like: isnot:0 isnot:ack isnot:"downtime test" name "vm test"
        regex = re.compile(
            r"""
                                    # 1/ Search a key:value pattern.
                (?P<key>\w+):       # Key consists of only a word followed by a colon
                (?P<quote2>["']?)   # Optional quote character.
                (?P<value>.*?)      # Value is a non greedy match
                (?P=quote2)         # Closing quote equals the first.
                ($|\s)              # Entry ends with whitespace or end of string
                |                   # OR
                                    # 2/ Search a single string quoted or not
                (?P<quote>["']?)    # Optional quote character.
                (?P<name>.*?)       # Name is a non greedy match
                (?P=quote)          # Closing quote equals the opening one.
                ($|\s)              # Entry ends with whitespace or end of string
            """,
            re.VERBOSE
        )

        qualifiers = {}
        for match in regex.finditer(query):
            if match.group('name'):
                if 'name' not in qualifiers:
                    qualifiers['name'] = []
                qualifiers['name'].append(match.group('name'))
            elif match.group('key'):
                field = match.group('key')
                if field not in qualifiers:
                    qualifiers[field] = []
                qualifiers[field].append(match.group('value'))
        logger.debug("decode_search, search patterns: %s", qualifiers)

        if not data_model:
            data_model = {
                'host_name': {
                    'searchable': True, 'type': 'string', 'regex': True,
                    'title': 'Host name'
                },
                'service_name': {
                    'searchable': True, 'type': 'string', 'regex': True,
                    'title': 'Service name'
                },
                'user_name': {
                    'searchable': True, 'type': 'string', 'regex': True,
                    'title': 'User name'
                },
                'type': {
                    'searchable': True, 'type': 'string', 'regex': True,
                    'title': 'Event type',
                    'allowed': 'webui.comment,check.result,check.request,check.requested,'
                               'ack.add,ack.processed,ack.delete,'
                               'downtime.add,downtime.processed,downtime.delete,'
                               'monitoring.timeperiod_transition,'
                               'monitoring.alert,monitoring.event_handler,'
                               'monitoring.flapping_start,monitoring.flapping_stop,'
                               'monitoring.downtime_start,monitoring.downtime_cancelled,'
                               'monitoring.downtime_end,'
                               'monitoring.acknowledge,'
                               'monitoring.notification'
                },
                'message': {
                    'searchable': True, 'type': 'string', 'regex': True,
                    'title': 'Event message'
                }
            }

        parameters = {}
        try:
            for field in qualifiers:
                search_state = False
                field = field.lower()
                patterns = qualifiers[field]
                logger.debug("decode_search, searching for '%s' '%s'", field, patterns)

                # Get the column definition for the searched field
                if field not in data_model:
                    if 'ls_' + field not in data_model:
                        logger.warning("decode_search, unknown column '%s' in table fields", field)
                        continue
                    # live state fields
                    field = 'ls_' + field

                c_def = data_model[field]
                logger.debug("decode_search, found column: %s", c_def)

                # Column is defined as searchable?
                if c_def.get('searchable', None) is not None and not c_def.get('searchable', True):
                    logger.warning("decode_search, field '%s' is not searchable", field)
                    continue

                field_type = c_def.get('type', 'string')
                if search_state or field_type in ['integer', 'float', 'boolean']:
                    regex = False
                else:
                    regex = c_def.get('regex', True)

                for pattern in patterns:
                    logger.info("decode_search, pattern: %s", pattern)
                    not_value = pattern.startswith('!')
                    if not_value:
                        pattern = pattern[1:]

                    if search_state:
                        allowed_values = c_def.get('allowed', '').split(',')
                        logger.debug("decode_search, allowed values: %s", allowed_values)
                        if pattern.lower() not in allowed_values:
                            logger.warning("decode_search, ignoring unallowed "
                                           "search pattern: %s = %s", field, pattern)
                            continue
                        field = '_overall_state_id'
                        pattern = allowed_values.index(pattern.lower())
                    else:
                        try:
                            # Specific field type
                            if field_type == 'integer':
                                pattern = int(pattern)
                            if field_type == 'float':
                                pattern = float(pattern)
                            if field_type == 'boolean':
                                if pattern in ['0', 'no', 'No', 'false', 'False']:
                                    pattern = False
                                else:
                                    pattern = True
                        except Exception as exp:
                            logger.warning("decode_search, invalid "
                                           "search pattern: %s = %s", field, pattern)
                            continue

                    if field in parameters:
                        # We already have a field search pattern, let's build a list...
                        if not isinstance(parameters[field]['pattern'], list):
                            if regex:
                                parameters[field]['type'] = "$or"
                            else:
                                parameters[field]['type'] = "$in"
                            parameters[field]['pattern'] = [parameters[field]['pattern']]

                        if regex:
                            if not_value:
                                parameters[field]['pattern'].append(
                                    {"$regex": "/^((?!%s).)*$/" % pattern})
                            else:
                                parameters[field]['pattern'].append(
                                    {"$regex": ".*%s.*" % pattern})
                        else:
                            if not_value:
                                pattern = {"$ne": pattern}
                            parameters[field]['pattern'].append(pattern)
                        continue

                    if regex:
                        if not_value:
                            parameters.update(
                                {field: {'type': 'simple',
                                         'pattern': {"$regex": "/^((?!%s).)*$/" % pattern}}})
                        else:
                            parameters.update(
                                {field: {'type': 'simple',
                                         'pattern': {"$regex": ".*%s.*" % pattern}}})
                    else:
                        if not_value:
                            pattern = {"$ne": pattern}
                        parameters.update({field: {'type': 'simple', 'pattern': pattern}})

                    logger.info("decode_search, - parameters: %s", parameters)
        except Exception as exp:
            logger.exception("Exception: %s", exp)

        query = {}
        for field, search_type in parameters.iteritems():
            logger.debug("decode_search, build query: %s - %s", field, search_type)
            if search_type['type'] == 'simple':
                query.update({field: search_type['pattern']})
            elif search_type['type'] == '$or':
                logger.debug("decode_search, - $or query: %s", search_type['pattern'])
                patterns = []
                for pattern in search_type['pattern']:
                    patterns.append({field: pattern})
                query.update({'$or': patterns})
            elif search_type['type'] == '$in':
                logger.debug("decode_search, - $in query: %s", search_type['pattern'])
                included = []
                excluded = []
                for pattern in search_type['pattern']:
                    if isinstance(pattern, dict):
                        if '$ne' in pattern:
                            excluded.append(pattern['$ne'])
                    else:
                        included.append(pattern)
                if included and excluded:
                    query.update({field: {'$in': included, '$nin': excluded}})
                else:
                    if included:
                        query.update({field: {'$in': included}})
                    if excluded:
                        query.update({field: {'$nin': excluded}})
            elif search_type['type'] == '$ne':
                logger.debug("decode_search, - $ne query: %s", search_type['pattern'])
                query.update({field: {'$ne': search_type['pattern']}})

        logger.debug("decode_search, result query: %s", query)
        return query
