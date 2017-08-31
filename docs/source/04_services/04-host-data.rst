.. raw:: LaTeX

    \newpage

.. _host_data:

Get host data
~~~~~~~~~~~~~
To get an Alignak host data, GET on the `host` endpoint:
::

    $ curl --request GET \
      --url http://demo.alignak.net:8888/host \
      --header 'authorization: Basic MTQ4NDU1ODM2NjkyMi1iY2Y3Y2NmMS03MjM4LTQ4N2ItYWJkOS0zMGNlZDdlNDI2ZmI6' \
      --header 'cache-control: no-cache' \
      --header 'content-type: application/json' \
      --data '
      {
        "name": "passive-01",
      }'

    OR:
    $ curl --request GET \
      --url http://demo.alignak.net:8888/host/passive-01 \
      --header 'authorization: Basic MTQ4NDU1ODM2NjkyMi1iY2Y3Y2NmMS03MjM4LTQ4N2ItYWJkOS0zMGNlZDdlNDI2ZmI6' \
      --header 'cache-control: no-cache' \
      --header 'content-type: application/json'


    # JSON result
    {
      "_status": "OK",
      "_result": [
        {u'ls_grafana': False, u'business_impact_modulations': [], u'labels': [], u'action_url': u'', u'low_flap_threshold': 25, u'process_perf_data': True, u'icon_image': u'', u'ls_last_time_down': 0, u'_realm': u'592fd61006fd4b73b7434ee0', u'display_name': u'', u'notification_interval': 60, u'ls_execution_time': 0.0, u'failure_prediction_enabled': False, u'retry_interval': 0, u'snapshot_enabled': False, u'event_handler_enabled': False, u'3d_coords': u'', u'parents': [], u'location': {u'type': u'Point', u'coordinates': [46.3613628, 6.5394704]}, u'_template_fields': {}, u'notifications_enabled': True, u'address6': u'', u'freshness_threshold': 0, u'alias': u'', u'time_to_orphanage': 300, u'name': u'new_host_0', u'notes': u'', u'ls_last_notification': 0, u'custom_views': [], u'active_checks_enabled': True, u'ls_max_attempts': 0, u'service_includes': [], u'reactionner_tag': u'', u'notes_url': u'', u'ls_last_state': u'OK', u'ls_last_time_unknown': 0, u'usergroups': [], u'resultmodulations': [], u'business_rule_downtime_as_ack': False, u'stalking_options': [], u'_sub_realm': True, u'ls_long_output': u'', u'macromodulations': [], u'ls_state_id': 3, u'business_rule_host_notification_options': [u'd', u'u', u'r', u'f', u's'], u'high_flap_threshold': 50, u'_is_template': False, u'definition_order': 100, u'tags': [], u'snapshot_criteria': [u'd', u'x'], u'vrml_image': u'', u'ls_latency': 0.0, u'ls_downtimed': False, u'ls_current_attempt': 0, u'2d_coords': u'', u'ls_grafana_panelid': 0, u'icon_set': u'', u'business_impact': 2, u'max_check_attempts': 1, u'business_rule_service_notification_options': [u'w', u'u', u'c', u'r', u'f', u's'], u'statusmap_image': u'', u'address': u'', u'escalations': [], u'ls_next_check': 0, u'_templates_with_services': True, u'flap_detection_options': [u'o', u'd', u'x'], u'ls_last_check': 0, u'_overall_state_id': 3, u'ls_last_hard_state_changed': 0, u'_links': {u'self': {u'href': u'host/592fd61606fd4b73b7434f1a', u'title': u'Host'}}, u'trigger_broker_raise_enabled': False, u'first_notification_delay': 0, u'_templates': [], u'notification_options': [u'd', u'x', u'r', u'f', u's'], u'ls_acknowledged': False, u'event_handler_args': u'', u'event_handler': None, u'obsess_over_host': False, u'check_command_args': u'', u'ls_last_state_changed': 0, u'service_excludes': [], u'imported_from': u'unknown', u'initial_state': u'x', u'ls_state': u'UNREACHABLE', u'check_command': u'592fd61006fd4b73b7434ee6', u'ls_impact': False, u'check_interval': 5, u'_created': u'Thu, 01 Jun 2017 08:53:42 GMT', u'_etag': u'd8ba06e4a2b54f1604f5b152f800c8bbf0e22ead', u'check_freshness': False, u'snapshot_interval': 5, u'icon_image_alt': u'', u'ls_output': u'', u'ls_last_time_up': 0, u'ls_passive_check': False, u'ls_last_state_type': u'HARD', u'service_overrides': [], u'ls_perf_data': u'', u'passive_checks_enabled': True, u'freshness_state': u'x', u'trending_policies': [], u'flap_detection_enabled': True, u'users': [], u'business_rule_smart_notifications': False, u'ls_acknowledgement_type': 1, u'customs': {}, u'ls_attempt': 0, u'trigger_name': u'', u'_updated': u'Thu, 01 Jun 2017 08:53:42 GMT', u'checkmodulations': [], u'poller_tag': u'', u'ls_last_time_unreachable': 0, u'ls_state_type': u'HARD', u'_id': u'592fd61606fd4b73b7434f1a', u'business_rule_output_template': u''}
      ]
    }


The result is a JSON object containing a `_status` property that should be 'OK' and an `_result` array property that contain the hosts fetched in the backend. Each item in this array has the properties:
