# -*- coding: utf-8 -*-
#
# Filter to consume a raw record of Smart Emission data (one hour for one
# device), and extract these, producing records.
#
# Author: Pieter Marsman - 2016

import sys
import traceback
from stetl.component import Config
from stetl.filter import Filter
from stetl.inputs.dbinput import PostgresDbInput
from stetl.packet import FORMAT
from stetl.util import Util

from dateutil import parser

from sensordefs import *

log = Util.get_log("Extractor")


class ExtractFilter(Filter):
    """
    Filter to consume single raw record with sensor (single hour) timeseries values and extract these for each component.
    Input is a single timeseries record for a single hour with all sensorvalues for a single device within that hour.
    """

    @Config(ptype=list, default=[], required=True)
    def sensor_names(self):
        """
        The output sensor names to extract.

        Required: True

        Default: []
        """
        pass

    @Config(ptype=list, default=[], required=True)
    def device_ids(self):
        """
        The device ids to extract

        Required: True

        Default: []
        """
        pass

    def __init__(self, configdict, section):
        Filter.__init__(self, configdict, section, consumes=FORMAT.record,
                        produces=FORMAT.record_array)
        self.current_record = None
        self.last_id = None

    def invoke(self, packet):
        if packet.data is None or packet.is_end_of_doc() or packet.is_end_of_stream():
            return packet

        # The TS input record: single device with json-field with list of dict for values
        record_in = packet.data

        # Start list of output records
        records_out = []

        # ts_list (timeseries list) is an array of dict, each dict containing raw sensor values
        device_id = record_in['device_id']
        unique_id = record_in['unique_id']
        gid = record_in['gid']
        day = record_in['day']
        hour = record_in['hour']
        validate_errs = 0

        ts_list = record_in['data']['timeseries']
        log.info('processing unique_id=%s gid=%d ts_count=%d' % (
            unique_id, gid, len(ts_list)))

        if str(device_id) not in self.device_ids:
            log.info("Device id %d not in selected device ids %s", device_id,
                     str(self.device_ids))
        else:

            record = dict()
            record['device_id'] = device_id
            record['gid'] = gid

            for sensor_vals in ts_list:
                # log.debug(str(sensor_vals))

                if 'time' not in sensor_vals:
                    log.warn('Sensor values without time are of no use')
                    continue

                record['time'] = parser.parse(sensor_vals['time'])

                # Go through all the configured sensor outputs we need to calc values for
                for sensor_name in self.sensor_names:

                    sensor_record = dict(record)

                    try:
                        # get raw input value(s)
                        # i.e. in some cases multiple inputs are required (e.g. audio bands)
                        valid, reason = check_value(sensor_name, sensor_vals)
                        if not valid:
                            # log.warn(
                            #     'id=%d-%d-%d-%s gid=%d: invalid input for %s: detail=%s' % (
                            #         device_id, day, hour, sensor_name, gid,
                            #         sensor_name, reason))
                            validate_errs += 1
                            continue

                        # value should be available
                        value_raw, _ = get_raw_value(sensor_name, sensor_vals)
                        if value_raw is None:
                            # No use to proceed without raw input value(s)
                            log.warn('Value raw is None for %s' % sensor_name)
                            validate_errs += 1
                            continue

                        if 's_longitude' in sensor_vals and 's_latitude' in sensor_vals:
                            lon = SENSOR_DEFS['longitude']['converter'](sensor_vals['s_longitude'])
                            lat = SENSOR_DEFS['latitude']['converter'](sensor_vals['s_latitude'])

                            valid, reason = check_value('latitude', sensor_vals, value=lat)
                            if not valid:
                                validate_errs += 1
                                continue

                            valid, reason = check_value('longitude', sensor_vals, value=lon)
                            if not valid:
                                validate_errs += 1
                                continue

                            # Both lat and lon are valid!
                            # record['point'] = 'SRID=4326;POINT(%f %f)' % (lon, lat)
                            sensor_record['lat'] = lat
                            sensor_record['lon'] = lon

                        # No 'point' proceeding without a location
                        if 'lat' not in sensor_record or \
                                        'lon' not in sensor_record:
                            validate_errs += 1
                            continue

                        # sensor name should be in sensor defs
                        sensor_record['name'] = sensor_name
                        sensor_record['value'] = value_raw

                    except Exception, e:
                        log.error('Exception extracting gid=%d dev=%d, '
                                  'err=%s' % (gid, device_id, str(e)))
                        traceback.print_exc(file=sys.stdout)
                    else:
                        # Only save results when measuring something
                        records_out.append(sensor_record)

        packet.data = records_out
        log.info('Result unique_id=%s gid=%d record_count=%d val_errs=%d' % (
            unique_id, gid, len(records_out), validate_errs))

        return packet


class LastIdFilter(PostgresDbInput):
    @Config(ptype=str, required=True)
    def progress_update(self):
        """
        Query to update progress

        Required: True

        Default: ""
        """
        pass

    @Config(ptype=str, required=True)
    def id_key(self):
        """
        Key to select id from record array

        Required: True
        """

    @Config(ptype=str, default=None, required=False)
    def name_key(self):
        """
        Key to select name from record array

        Required: True
        """

    def __init__(self, configdict, section):
        PostgresDbInput.__init__(self, configdict, section)
        self.last_id = None

    def invoke(self, packet):
        self.last_id = dict()

        if packet.data is None or packet.is_end_of_doc() or packet.is_end_of_stream():
            log.info("No packet data or end of doc/stream")
            return packet

        record_in = packet.data
        if type(record_in) is not list:
            record_in = [record_in]
        for record in record_in:
            if self.name_key is not None:
                name = record[self.name_key]
            else:
                name = "all"
            if len(record) > 0:
                new = record[self.id_key]
                self.last_id[name] = max(self.last_id.get(name, -1), new)

        log.info("Maximum gids are %s", str(self.last_id))

        return packet

    def after_chain_invoke(self, packet):
        """
        Called right after entire Component Chain invoke.
        Used to update last id of processed file record.
        """
        for name, progress in self.last_id.iteritems():
            param = (progress, name)
            log.info('Updating progress table with (id=%d, name=%s)' % param)
            self.db.execute(self.progress_update % param)
            self.db.commit(close=False)
            log.info('Update progress table ok')
        else:
            log.info('No update for progress table')
        return True