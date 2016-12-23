from stetl.component import Config
from stetl.inputs.dbinput import DbInput
from stetl.packet import FORMAT
from stetl.util import Util

from influxdb import DataFrameClient
from influxdb import InfluxDBClient

log = Util.get_log("InfluxDbInput")


class InfluxDbInput(DbInput):
    # Start attribute config meta
    @Config(ptype=str, required=False, default='localhost')
    def host(self):
        """
        host name or host IP-address, defaults to 'localhost'
        """
        pass

    @Config(ptype=str, required=False, default='5432')
    def port(self):
        """
        port for host, defaults to '5432'
        """
        pass

    @Config(ptype=str, required=False, default='postgres')
    def user(self):
        """
        User name, defaults to 'postgres'
        """
        pass

    @Config(ptype=str, required=False, default='postgres')
    def password(self):
        """
        User password, defaults to 'postgres'
        """
        pass

    @Config(ptype=str, required=True)
    def database(self):
        """
        The "database" is a db-like entity in an InfluxDB server instance.

        Required: True

        Default: N.A.
        """
        pass

    @Config(ptype=str, required=True)
    def query(self):
        """
        The query for the database

        Required: True
        """

    def __init__(self, configdict, section, produces=FORMAT.record_array):
        DbInput.__init__(self, configdict, section, produces)
        self.client = None

    def init(self):
        log.info("Setting up connection to influxdb %s:%s, database=%s" %
                 (self.host, self.port, self.database))
        self.client = InfluxDBClient(self.host, self.port, self.user,
                                     self.password, self.database)

    def query_db(self, query):
        log.info("Querying database: %s", query)
        result = self.client.query(query)

        if result.error is not None:
            log.warning("Error while querying influxdb: %s", result.error)
            result_out = list()

        else:
            result_out = list(result.get_points())

        log.info("Received %s results" % len(result_out))

        return result_out

    def read(self, packet):
        result_out = self.query_db(self.query)
        packet.data = result_out
        packet.set_end_of_stream()
        return packet


class CalibrationInfluxDbInput(InfluxDbInput):

    @Config(ptype=str, required=True)
    def query_jose(self):
        """
        The query for the database to get the Jose data

        Required: True
        """

    @Config(ptype=str, required=True)
    def query_rivm(self):
        """
        The query for the database to get the RIVM data

        Required: True
        """

    def __init__(self, configdict, section, produces=FORMAT.record):
        InfluxDbInput.__init__(self, configdict, section, produces)

    def read(self, packet):
        results_out = dict()
        results_out["jose"] = self.query_db(self.query_jose)
        results_out["rivm"] = self.query_db(self.query_rivm)

        packet.data = results_out
        packet.set_end_of_stream()

        return packet