#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Output classes for ETL.
#
# Author: Just van den Broecke
#
from os import sys, path
from stetl.outputs.httpoutput import HttpOutput
from stetl.util import Util
from stetl.packet import FORMAT
from stetl.component import Config
log = Util.get_log('sosoutput')

class SOSTOutput(HttpOutput):
    """
    Output via SOS-T protocol over plain HTTP.

    consumes=FORMAT.record_array
    """

    @Config(ptype=str, default='application/json;charset=UTF-8', required=True)
    def content_type(self):
        """
        The content type (for template).

        Required: True

        Default: application/json;charset=UTF-8
        """
        pass

    @Config(ptype=str, default='sostemplates', required=False)
    def template_file_root(self):
        """
        SOS template file root: where SOS request and procedure template-files are stored.

        Required: False

        Default: sostemplates
        """
        pass

    def __init__(self, configdict, section):
        HttpOutput.__init__(self, configdict, section, consumes=FORMAT.record_array)

        # Template file, to be used as POST body with substituted values
        self.insert_sensor_templ_path = '%s/insert-sensor.json' % self.template_file_root
        self.insert_obs_templ_path ='%s/insert-observation.json' % self.template_file_root
        self.proc_desc_templ_path = '%s/procedure-desc.xml' % self.template_file_root
        self.insert_sensor_templ_str = None
        self.insert_obs_templ_str = None

    def init(self):
        # read the insert_observation template once
        log.info('Init: read template file: %s' % self.insert_obs_templ_path)
        with open(self.insert_obs_templ_path, 'r') as f:
            self.insert_obs_templ_str = f.read()

        # For insert-sensor we need the Procedure SML (XML) and escape/insert this into
        # the JSON insert-sensor string.
        log.info('Init: read template file: %s' % self.proc_desc_templ_path)
        with open(self.proc_desc_templ_path, 'r') as f:
            proc_desc = f.read()
            proc_desc = proc_desc.replace('"', '\\"').replace('\n', '')

            log.info('Init: read template file: %s' % self.insert_sensor_templ_path)
            with open(self.insert_sensor_templ_path, 'r') as f:
                insert_sensor_str = f.read()
                self.insert_sensor_templ_str = insert_sensor_str.replace('{procedure-desc.xml}', proc_desc)

    def post(self, packet, payload):
        record = packet.data
        device_id = record['device_id']
        component = record['name']
        gid = record['gid']
        id = '%s-%s-%s' % (device_id, component, gid)
        log.info('====START InsertObservation id=%s' % id)
        log.info('POSTing InsertObservation! try 1 - payload=%s' % payload)
        statuscode, statusmessage, res = HttpOutput.post(self, packet, payload)

        # InsertObservation may fail when Sensor not in SOS
        # Try to do an InsertSensor and try InsertObservation again
        if statuscode == 400:
            log.info('No sensor for station: res=%s, will insert' % res)
            insert_sensor_payload = self.create_insert_sensor_payload(packet)
            log.info('POSTing InsertSensor! - payload=%s' % insert_sensor_payload)
            statuscode, statusmessage, res = HttpOutput.post(self, packet, insert_sensor_payload)
            if statuscode != 200:
                log.warn('FAIL InsertSensor for station: rec=%s res=%s' % (str(packet.data), res))
            else:
                log.info('YES InsertSensor OK! id=%s POSTing InsertObservation! try 2' % id)
                statuscode, statusmessage, res = HttpOutput.post(self, packet, payload)
                if statuscode == 200:
                    log.info('YES InsertObservation! try 2 OK!! %s' % id)
                else:
                    log.warn('FAIL InsertObservation payload=%s res=%s' % (payload, res))
        elif statuscode == 200:
            log.info('YES inserted Observation! try 1 id=%s' % id)

        log.info('====END InsertObservation id=%s' % id)

        return statuscode, statusmessage, res

    def create_insert_sensor_payload(self, packet):
        # String substitution based on Python String.format()
        # <local_id>STA-NL00807</local_id>
        # <natl_station_code>807</natl_station_code>
        # <eu_station_code>NL00807</eu_station_code>
        # <name>Hellendoorn-Luttenbergerweg</name>
        # <municipality>Hellendoorn</municipality>
        # <altitude>7</altitude>
        # <altitude_unit>m</altitude_unit>
        # <area_classification>http://dd.eionet.europa.eu/vocabulary/aq/areaclassification/rural</area_classification>
        # <activity_begin>1976-04-02T00:00:00+01:00</activity_begin>
        # <activity_end></activity_end>
        # <version></version>
        # <belongs_to></belongs_to>
        # <lon></lon>
        # <lat></lat>
        record = packet.data
        format_args = dict()
        format_args['station_id'] = record['device_id']
        format_args['station_name'] = record['device_id']
        format_args['station_altitude'] = record['altitude']
        format_args['station_lon'] = record['lon']
        format_args['station_lat'] = record['lat']

        payload = self.insert_sensor_templ_str.format(**format_args)
        return payload

    def create_payload(self, packet):
        record = packet.data
        format_args = dict()
        # need station_id, unique_id (sample_id?),
        # component, municipality(may be null), station_lat, station_lon,
        # sample_time, sample_value
        format_args['component'] = record['name']
        format_args['station_id'] = record['device_id']

        # See issue: somehow the unique_id ends up in the capabilities doc!
        format_args['unique_id'] = '%s-%s' % (record['device_id'], record['gid'])

        # Time format: "yyyy-MM-dd'T'HH:mm+0N00"  e.g. 2013-09-29T18:46:19+0100
        t = record['time']
        t_offset = t.tzinfo._offset.seconds / 3600
        format_args['sample_time'] = t.strftime('%Y-%m-%dT%H:%M:%S' + '+0%d00' % t_offset)
        format_args['station_lon'] = record['lon']
        format_args['station_lat'] = record['lat']
        format_args['sample_value'] = record['value']
        format_args['unit'] = record['unit']

        # TODO use Jinja2 formatting
        payload = self.insert_obs_templ_str.format(**format_args)

        # if self.sos_request == 'insert-sensor':
        #
        #     # String substitution based on Python String.format()
        #     # <local_id>STA-NL00807</local_id>
        #     # <natl_station_code>807</natl_station_code>
        #     # <eu_station_code>NL00807</eu_station_code>
        #     # <name>Hellendoorn-Luttenbergerweg</name>
        #     # <municipality>Hellendoorn</municipality>
        #     # <altitude>7</altitude>
        #     # <altitude_unit>m</altitude_unit>
        #     # <area_classification>http://dd.eionet.europa.eu/vocabulary/aq/areaclassification/rural</area_classification>
        #     # <activity_begin>1976-04-02T00:00:00+01:00</activity_begin>
        #     # <activity_end></activity_end>
        #     # <version></version>
        #     # <belongs_to></belongs_to>
        #     # <lon></lon>
        #     # <lat></lat>
        #     format_args = dict()
        #     format_args['station_id'] = record['natl_station_code']
        #     format_args['station_name'] = record['name']
        #     # if record['municipality'] is not None and len(record['municipality']) > 0:
        #     #     format_args['name'] += ' - ' + record['municipality']
        #     format_args['station_altitude'] = record['altitude']
        #     format_args['station_lon'] = record['lon']
        #     format_args['station_lat'] = record['lat']
        #
        #     payload = self.insert_sensor_templ_str.format(**format_args)
        #     # print payload
        # else:
        #     if self.sos_request == 'insert-observation':
        #         # with open('/etc/hosts') as f:
        #         #     print f.read()

        return payload
