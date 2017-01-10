from stetl.component import Config
from stetl.filter import Filter
from stetl.output import Output
from stetl.packet import FORMAT
from stetl.util import Util

import pandas as pd
import os
import matplotlib

matplotlib.use('Agg')
import seaborn as sns
from numpy import nan
from sklearn.metrics import explained_variance_score
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import RandomizedSearchCV
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from calibration_parameters import param_grid

log = Util.get_log('Calibration')


class MergeRivmJose(Filter):
    @Config(ptype=dict, required=True)
    def map_jose(self):
        """
        Mapping between Jose stations and "location id's"

        Required: True
        """

    @Config(ptype=dict, required=True)
    def map_rivm(self):
        """
        Mapping between RIVM stations and "location id's"

        Required: True
        """

    def __init__(self, configdict, section, consumes=FORMAT.record_array,
                 produces=FORMAT.record_array):
        Filter.__init__(self, configdict, section, consumes, produces)

    def invoke(self, packet):
        # Convert packet data to dataframes
        result_in = packet.data
        rivm = result_in['rivm']
        jose = result_in['jose']
        df_rivm = pd.DataFrame.from_records(rivm)
        df_jose = pd.DataFrame.from_records(jose)

        log.info('Received rivm data with shape (%d, %d)' % df_rivm.shape)
        log.info('Received jose data with shape (%d, %d)' % df_jose.shape)

        # Rename stations
        df_jose = df_jose.replace({'station': self.map_jose})
        df_rivm = df_rivm.replace({'station': self.map_rivm})

        # Set time as index
        df_rivm['time'] = pd.to_datetime(df_rivm['time'])
        df_jose['time'] = pd.to_datetime(df_jose['time'])

        # Interpolate RIVM to jose times
        jose_index = df_jose['time'].unique()
        jose_time = pd.DataFrame({'time': jose_index})
        df_rivm = jose_time.merge(df_rivm, 'outer').set_index('time')
        df_rivm = df_rivm.sort_index().interpolate().ffill().loc[jose_index]
        df_rivm = df_rivm.reset_index()

        # Pivot Jose
        df_jose = df_jose.pivot_table('value', ['station', 'time'],
                                      'component').reset_index()
        df_rivm = df_rivm.pivot_table('value', ['station', 'time'],
                                      'component').reset_index()

        # Concatenate RIVM and Jose
        df = pd.merge(df_rivm, df_jose, 'outer', ['time', 'station'])
        del df.index.name
        log.info('Merged RIVM and Jose data. New shape = (%d, %d).' % df.shape)

        df = df.dropna()
        log.info('Dropping NA values. New shape = (%d, %d).' % df.shape)

        packet.data = df.to_dict('records')
        log.info('Returning packet of length %d', len(packet.data))

        return packet


class Calibrator(Filter):
    @Config(ptype=int, default=.01, required=False)
    def inverse_sample_fraction(self):
        """
        Inverse fraction of Jose data to use for calibration. E.g. 10 means
        1/10=0.1.

        Default: 0.01

        Required: True
        """

    @Config(ptype=float, default=.01, required=False)
    def filter_alpha(self):
        """
        Control for low-pass filter, higher alpha is more emphasis on new data

        Default: 0.01

        Required: False
        """

    @Config(ptype=str, required=True)
    def target(self):
        """
        The column to predict, all the other columns will be used for the
        prediction

        Required: True
        """

    @Config(ptype=int, default=100, required=False)
    def random_search_iterations(self):
        """
        The number of random parameter settings to try before choosing the
        best one.

        Default: 100

        Required: False
        """

    @Config(ptype=int, default=10, required=False)
    def cv_k(self):
        """
        The number of cross-validations to perform

        Default: 10

        Required: False
        """

    @Config(ptype=int, default=-2, required=False)
    def n_jobs(self):
        """
        The number of parallel processes to use. Negative values are
        equivalent to total_cores + 1 - njobs

        Default: -2 (all cores - 1)

        Required: False
        """

    def __init__(self, configdict, section, consumes=FORMAT.record_array,
                 produces=FORMAT.record):
        Filter.__init__(self, configdict, section, consumes, produces)
        self.pipeline = None

    def init(self):
        ss = StandardScaler()
        mlp = MLPRegressor(solver='lbfgs')
        steps = [('scale', ss), ('mlp', mlp)]
        self.pipeline = Pipeline(steps)

    def invoke(self, packet):

        log.info('Receiving packet of size %d' % len(packet.data))

        result_out = dict()

        df = pd.DataFrame.from_records(packet.data)
        log.info('Created data frame with shape (%d, %d)' % df.shape)

        # Fitler data
        df = Calibrator.filter_data(df, [self.target, 'time'],
                                         self.filter_alpha)

        # Sample to prevent over fitting
        df_sample = df.sample(frac=1 / float(self.inverse_sample_fraction))
        del df_sample['station']
        del df_sample['time']
        log.info('Sample dataframe, keeping 1 out of every %d rows. New '
                 'shape (%d, %d)' %
                 (self.inverse_sample_fraction, df_sample.shape[0],
                  df_sample.shape[1]))

        # Split into label and data
        x, y = Calibrator.split_data_label(df_sample, self.target)
        log.info('Starting randomized cross validated search to find best '
                 'parameters. Running %d iterations with %d cross '
                 'validations of %d cores' %
                 (self.random_search_iterations,  self.cv_k, self.n_jobs))
        log.info('Finding relation from %s to %s' %
                 (str(x.columns.values), self.target))
        gs = RandomizedSearchCV(self.pipeline, param_grid,
                                self.random_search_iterations,
                                n_jobs=self.n_jobs, cv=self.cv_k,
                                error_score=nan)
        gs.fit(x, y)
        log.info('Best result from randomized search: %.2f' % gs.best_score_)
        log.info('Best parameters from randomized search: %s' % str(gs.best_params_))

        for gs_keys in ['cv_results_', 'best_estimator_', 'best_score_',
                        'best_params_', 'best_index_', 'scorer_', 'n_splits_']:
            result_out[gs_keys] = getattr(gs, gs_keys)
        result_out['target'] = self.target
        result_out['data'] = df

        packet.data = result_out
        log.info('Returning result of %d length, with keys %s.' % (
            len(packet.data), packet.data.keys()))

        return packet

    @staticmethod
    def split_data_label(df, label):
        y = df[label]
        x = df.drop(label, axis=1)
        return x, y

    @staticmethod
    def filter_data(df, target, alpha):
        # todo use rolling mean for time series data (i.e. also account for
        # longer gaps in the data)
        if type(target) is not list:
            target = [target]
        cols = [df_col for df_col in df.columns if df_col not in target]
        for col in cols:
            df[col] = Calibrator.running_mean(df[col], alpha)
        return df

    @staticmethod
    def running_mean(x, alpha, start=None):
        """
        Filters a series of observations by a running mean
        new mean = obs * alpha + `previous mean` * (1 - alpha)
        """
        if start is not None:
            val = start
        else:
            val = x[0]
        new_x = []
        for (i, elem) in enumerate(x):
            val = elem * alpha + val * (1.0 - alpha)
            new_x.append(val)
        return pd.Series(new_x)


class Visualization(Output):

    @Config(ptype=str, required=True)
    def file_path(self):
        """
        The path where to save the visualization images. Should contain a %s that is replaced by the image name.

        Required: True
        """

    @Config(ptype=bool, default=False, required=True)
    def clear_output_folder(self):
        """
        If the results folder should be cleared before putting the new
        results in.

        Default: False

        Required: False
        """

    def __init__(self, configdict, section):
        Output.__init__(self, configdict, section, consumes=FORMAT.record)
        self.model = None
        self.oob = None
        self.df = None
        self.cv_results_ = None
        self.target = None

    def write(self, packet):
        record_in = packet.data

        self.model = record_in['best_estimator_']
        self.df = record_in['data']
        self.cv_results_ = record_in['cv_results_']
        self.target = record_in['target']

        if self.clear_output_folder:
            Visualization.create_empty_folder(os.path.dirname(self.file_path))
        self.visualization()

        return packet

    def visualization(self):
        pass
    
    def save_fig(self, file_name, file_extension='png'):
        file_path = self.file_path % ("%s.%s" %(file_name, file_extension))
        sns.plt.savefig(file_path)
        log.info('Saved figure to %s' % file_path)

    @staticmethod
    def close_plot():
        sns.plt.close()

    @staticmethod
    def create_empty_folder(folder):
        # Create folder and delete content if exist
        if not os.path.exists(folder):
            log.info('Creating dir %s' % folder)
            os.makedirs(folder)
        for the_file in os.listdir(folder):
            file_path = os.path.join(folder, the_file)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                log.info("Error while deleting file: %s" % str(e))


class PerformanceVisualization(Visualization):

    def __init__(self, configdict, section):
        Visualization.__init__(self, configdict, section)
        self.df_meta = None
        self.r2 = None
        self.rmse = None

    def visualization(self):
        self.visualization_init()
        self.visualization_error_scatter()
        self.visualization_error_histogram()
        self.visualization_time_series('20150101', '20170101')

    def visualization_init(self):
        self.df_meta = self.df[['time', 'station', self.target]].copy()

        x = self.df.copy()
        del x['station']
        del x[self.target]
        del x['time']

        self.df_meta['Prediction'] = self.model.predict(x)
        self.df_meta['Error'] = self.df_meta['Prediction'] - self.df[self.target]
        self.df_meta['time'] = pd.to_datetime(self.df_meta['time'])

        target = self.df[self.target]
        prediction = self.df_meta['Prediction']
        self.r2 = explained_variance_score(target, prediction) * 100
        self.rmse = mean_squared_error(target, prediction) ** .5

    def visualization_error_scatter(self):
        log.info('Visualizing error as scatterplot')
        # Using relative and absolute performance measure
        title = 'Actual vs. Predicted\nRMSE=%.1f ug/m3, Explained ' \
                'var=%.0f%%' % (self.rmse, self.r2)

        g = sns.regplot('Prediction', self.target, self.df_meta)
        g.set_title(title)
        g.set_aspect('equal', 'box')

        self.save_fig('error_scatter')
        Visualization.close_plot()

    def visualization_error_histogram(self):
        log.info('Visualizing error as histogram')
        # Create title (use both explained variance and rmse to hava a scale
        # relative and absolute measurement of performance)
        title = 'Histogram of error\nRMSE=%.1f ug/m3, Explained var=%.0f%%' % \
                (self.rmse, self.r2)

        # Plot using seaborn
        g = sns.distplot(self.df_meta['Error'], 100)
        g.set_title(title)

        self.save_fig('error_histogram')
        self.close_plot()

    def visualization_time_series(self, start, end):
        log.info("Visualizing time series from %s to %s" % (start, end))
        start = pd.to_datetime(start)
        end = pd.to_datetime(end)

        time_series = self.df_meta.copy().sort_values('time')
        time_series = time_series[(time_series['time'] >= start) &
                                  (time_series['time'] <= end)]
        time_series['station'] = time_series['station'].astype(int).astype(str)

        sns.set_style('darkgrid')
        sns.plt.plot(time_series['time'], time_series[self.target])
        sns.plt.plot(time_series['time'], time_series['Prediction'])
        sns.plt.xlabel('Time')
        sns.plt.ylabel(self.target)
        sns.plt.legend(['Target', 'Prediction'])
        sns.plt.show()

        self.save_fig('time_series')
        Visualization.close_plot()


class ModelVisualization(Visualization):

    def visualization(self):
        for col in self.df.columns.values:
            if col not in ['time', 'station', self.target]:
                self.visualization_input_output_relation(col)

    def visualization_input_output_relation(self, col, n_val=100, n_sim=100):
        log.info('Visualizing input/output relation %s' % col)
        val = pd.np.linspace(self.df[col].min(), self.df[col].max(), n_val)
        df = self.df.sample(n_sim)
        df = pd.concat([df] * n_val)
        df[col] = pd.np.repeat(val, n_sim)

        for df_col in ['station', 'time', self.target]:
            del df[df_col]

        df['Prediction'] = self.model.predict(df)
        df['id'] = pd.np.tile(pd.np.arange(0, n_sim), n_val)

        sns.tsplot(df, col, 'id', value='Prediction', err_style='unit_traces')

        self.save_fig('effect_%s' % col)
        self.close_plot()


class DataVisualization(Visualization):
    
    def visualization(self):
        for col in self.df.columns.values:
            self.visualization_occurrence(col)

    def visualization_occurrence(self, col):
        log.info('Visualizing occurrence of %s' % col)
        title = 'Occurrence of %s' % col

        try:
            g = sns.distplot(self.df[col], 100)
            g.set_title(title)

            self.save_fig('histogram_%s' % col)

        except pd.np.linalg.LinAlgError, e:
            log.info('Could not plot histogram for %s because of: %s' %
                      (col, str(e)))
        except TypeError, e:
            log.info('Could not plot histogram for %s because of: %s' %
                     (col, str(e)))

        Visualization.close_plot()


class SearchVisualization(Visualization):

    def __init__(self, configdict, section):
        Visualization.__init__(self, configdict, section)
        self.param_perf = None

    def visualization(self):
        self.init_visualization()
        for col in param_grid.keys():
            self.visualize_search_parameter(col)

    def init_visualization(self):
        log.debug("\n%s" % self.cv_results_)
        self.param_perf = pd.DataFrame(self.cv_results_)
        log.debug("\n%s" % self.param_perf)
        log.debug("\n%s" % self.param_perf.dtypes)

    def visualize_search_parameter(self, param):
        log.info('Visualizing parameter performance of %s' % param)

        title = "Explained variances for different levels of %s" % param
        col = "param_%s" % param
        col_score = "mean_test_score"
        col_type = type(self.param_perf[col][0])

        log.debug(self.param_perf[col][0])
        log.debug(col_type)



        # try:
        if col_type is str or col_type is bool:
            g = sns.swarmplot(col, col_score, data=self.param_perf)
        else:
        # except Exception, e:
        #     log.debug('%s is not number' % param)
        #     log.debug(e)
            g = sns.residplot(col, col_score, self.param_perf)

        g.set(ylim=(0, 1))
        g.set_title(title)

        self.save_fig('parameter_%s' % param)
        self.close_plot()


# done time, station, target, prediction, error in different data frame
# done plot decorator
# done split viz into multiple classes
# done remove viz dir before inserting new viz
# todo save rivm in influx with station as station, without component
# todo check if viz can be smaller
# todo check time histogram (TypeError?)
# done visualize search