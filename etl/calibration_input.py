import pickle

import Geohash
from stetl.component import Config
from stetl.inputs.dbinput import PostgresDbInput
from stetl.inputs.fileinput import FileInput
from stetl.packet import FORMAT
from stetl.util import Util

import pandas as pd

from running_mean import RunningMean
from sensordefs import SENSOR_DEFS

log = Util.get_log('Calibration input')


class CalibrationDataInput(FileInput):
    def __init__(self, configdict, section, produces=FORMAT.record):
        FileInput.__init__(self, configdict, section, produces)

    def read_file(self, file_path):
        log.debug("Reading data from file")
        df = pd.DataFrame.from_csv(file_path)
        df['time'] = pd.to_datetime(df['time'])
        return {'merged': df}


class CalibrationDbInput(PostgresDbInput):

    @Config(ptype=int, default=12, required=False)
    def geohash_precision(self):
        """
        Precision for the geohash. Number of characters to use in the
        geohash. When no precision is specified the precision of the
        coordinates are used.

        Default: 12 (the default of Geoahash.encode())

        Required: False
        """

    def after_invoke(self, packet):
        record_array = packet.data
        for record in record_array:
            # convert point to geohash
            if "lat" in record and "lon" in record:
                record['geohash'] = Geohash.encode(record['lat'], record['lon'], self.geohash_precision)
            else:
                record["geohash"] = None
            del record['lat']
            del record['lon']

        df = pd.DataFrame(record_array)
        df = df.pivot_table('value', ['geohash', 'time'], 'name').reset_index()

        packet.data = {'jose': df}
        return packet


class CalibrationModelInput(PostgresDbInput):
    """
    Get unpickled calibration model from the database
    """

    @Config(ptype=dict, default=dict(), required=False)
    def sensor_model_names(self):
        """
        The name of the sensor models in the database. Needed for linking
        the right model to the right gas.

        Default: dict()

        Required: False
        """

    @Config(ptype=str, required=True)
    def state_query(self):
        """
        Query for getting the state of a model. Should have a %s formatter
        for the process name and a %d formatter for filling in the model_id.

        Required: True
        """

    @Config(ptype=str, required=True)
    def process_name(self):
        """
        The name of the process in which this calibration model is used. The
        name is used to get the right state of the model.

        Required: True
        """

    def __init__(self, configdict, section):
        PostgresDbInput.__init__(self, configdict, section)
        self.ids = dict()
        self.parameters = dict()
        self.models = dict()
        self.state = dict()

    def query_parameters_and_model(self, name):
        query = self.query % name
        log.info('Getting calibration model with query: %s' % query)
        ret = self.raw_query(query)
        if len(ret) > 0:
            id, parameters, model = ret[0]
            return id, parameters, pickle.loads(model)
        else:
            log.warn("No model found for %s" % name)
            return None, {}, {}

    def query_state(self, model_id):
        query = self.state_query % (self.process_name, model_id)
        log.info('Getting calibration model state with query: %s' % query)
        ret = self.raw_query(query)
        if len(ret) > 0:
            return ret[0][0]
        else:
            log.warn("No state found for model_id=%d" % model_id)
            return {}

    def init(self):
        PostgresDbInput.init(self)

        if self.query is not None and len(self.sensor_model_names) > 0:
            log.info('Getting calibration models from database')
            for k, v in self.sensor_model_names.iteritems():
                id, param, model = self.query_parameters_and_model(v)
                self.ids[k] = id
                self.parameters[k] = param
                self.models[k] = model

                model_state = self.query_state(id)
                self.state[k] = model_state
        else:
            log.info('No query for fetching calibration models given or no '
                     'mapping for calibration models to gas components given.')

    def invoke(self, packet):
        for k, v in self.ids.iteritems():
            SENSOR_DEFS[k]['converter_model']['model_id'] = v
        for k, v in self.parameters.iteritems():
            SENSOR_DEFS[k]['converter_model']['running_mean_weights'] = v
        for k, v in self.models.iteritems():
            SENSOR_DEFS[k]['converter_model']['mlp_regressor'] = v
        for k, v in self.state.iteritems():
            for device_id, device_state in v.iteritems():
                for gas, state in device_state.iteritems():
                    v[device_id][gas] = RunningMean.from_dict(state)
            SENSOR_DEFS[k]['converter_model']['state'] = v

        return packet
