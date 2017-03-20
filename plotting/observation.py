from netCDF4 import Dataset, netcdftime
import matplotlib.pyplot as plt
import numpy as np
import utils
from textwrap import wrap
import pint
from oceannavigator.util import get_dataset_url
import re
import dateutil.parser
import pytz
import point
import numbers
from flask.ext.babel import gettext, format_datetime
from data import open_dataset


class ObservationPlotter(point.PointPlotter):

    def __init__(self, dataset_name, query, format):
        self.plottype = "observation"
        super(ObservationPlotter, self).__init__(dataset_name, query, format)

    def load_data(self):
        if isinstance(self.observation[0], numbers.Number):
            self.observation_variable_names = []
            self.observation_variable_units = []
            with Dataset(
                'http://127.0.0.1:8080/thredds/dodsC/misc/observations/aggregated.ncml',
                'r'
            ) as ds:
                t = netcdftime.utime(ds['time'].units)
                for idx, o in enumerate(self.observation):
                    observation = {}
                    ts = t.num2date(ds['time'][o]).replace(tzinfo=pytz.UTC)
                    observation['time'] = ts.isoformat()
                    observation['longitude'] = ds['lon'][o]
                    observation['latitude'] = ds['lat'][o]

                    observation['depth'] = ds['z'][:]
                    observation['depthunit'] = ds['z'].units

                    observation['datatypes'] = []
                    data = []
                    for v in sorted(ds.variables):
                        if v in ['z', 'lat', 'lon', 'profile', 'time']:
                            continue
                        var = ds[v]
                        if var.datatype == '|S1':
                            continue

                        observation['datatypes'].append("%s [%s]" % (
                            var.long_name,
                            var.units
                        ))
                        data.append(var[o, :])

                        if idx == 0:
                            self.observation_variable_names.append(
                                var.long_name)
                            self.observation_variable_units.append(var.units)

                    observation['data'] = np.ma.array(data).transpose()
                    self.observation[idx] = observation

                self.points = map(lambda o: [o['latitude'], o['longitude']],
                                  self.observation)

        with open_dataset(get_dataset_url(self.dataset_name)) as dataset:
            ts = dataset.timestamps

            observation_times = []
            timestamps = []
            for o in self.observation:
                observation_time = dateutil.parser.parse(o['time'])
                observation_times.append(observation_time)

                deltas = [
                    (x.replace(tzinfo=pytz.UTC) -
                     observation_time).total_seconds()
                    for x in ts]

                time = np.abs(deltas).argmin()
                timestamp = ts[time]
                timestamps.append(timestamp)

            self.load_misc(dataset, self.variables)

            point_data, self.depths = self.get_data(
                dataset, self.variables, time)
            point_data = np.ma.array(point_data)

            self.variable_units, point_data = self.kelvin_to_celsius(
                self.variable_units,
                point_data
            )

        self.data = self.subtract_climatology(point_data, timestamp)
        self.observation_time = observation_time
        self.observation_times = observation_times
        self.timestamps = timestamps
        self.timestamp = timestamp

    def parse_query(self, query):
        super(ObservationPlotter, self).parse_query(query)

        observation_variable = map(int, query.get("observation_variable"))
        observation = query.get("observation")
        if not isinstance(observation[0], numbers.Number):
            observation_variable_names = map(
                lambda x: re.sub(r" \[.*\]", "", x),
                observation[0]['datatypes'])
            observation_variable_units = map(
                lambda x: re.match(r".*\[(.*)\]", x).group(1),
                observation[0]['datatypes'])

            self.parse_names_points(
                [str(o.get('station')) for o in observation],
                [[o.get('latitude'), o.get('longitude')] for o in observation]
            )

            self.observation_variable_names = observation_variable_names
            self.observation_variable_units = observation_variable_units

        self.observation = observation
        self.observation_variable = observation_variable

    def plot(self):
        v = set([])
        for idx in self.observation_variable:
            v.add(self.observation_variable_names[idx])
        for n in self.variable_names:
            v.add(n)

        numplots = len(v)

        fig, ax = self.setup_subplots(numplots)

        data = []
        for o in self.observation:
            d = np.ma.MaskedArray(o['data'])
            d[np.where(d == '')] = np.ma.masked
            d = np.ma.masked_invalid(d.filled(np.nan).astype(np.float32))
            data.append(d)

        ureg = pint.UnitRegistry()
        ax_idx = -1
        udepth = ureg.parse_expression(self.observation[0]['depthunit'])
        axis_map = {}
        unit_map = {}
        for idx in self.observation_variable:
            ax_idx += 1
            for d in data:
                ax[ax_idx].plot(
                    d[:, idx],
                    self.observation[0]['depth'] * udepth.to(ureg.meter)
                )
            ax[ax_idx].xaxis.set_label_position('top')
            ax[ax_idx].xaxis.set_ticks_position('top')
            ax[ax_idx].set_xlabel("%s (%s)" % (
                self.observation_variable_names[idx],
                utils.mathtext(self.observation_variable_units[idx]),
            ))
            axis_map[self.observation_variable_names[idx]] = ax[ax_idx]

            try:
                if "_" in self.observation_variable_units[idx]:
                    u = self.observation_variable_units[idx].lower().split(
                        "_",
                        1
                    )[1]
                else:
                    u = self.observation_variable_units[idx].lower()
                unit_map[
                    self.observation_variable_names[idx]] = ureg.parse_units(u)

            except:
                unit_map[
                    self.observation_variable_names[idx]] = ureg.dimensionless

        for k, v in unit_map.iteritems():
            if v == ureg.speed_of_light:
                unit_map[k] = ureg.celsius

        for idx, var in enumerate(self.variables):
            if axis_map.get(self.variable_names[idx]) is not None:
                axis = axis_map.get(self.variable_names[idx])
                showlegend = True
                destunit = unit_map.get(self.variable_names[idx])
            else:
                ax_idx += 1
                axis = ax[ax_idx]
                showlegend = False
                try:
                    destunit = ureg.parse_units(
                        self.variable_units[idx].lower())
                    if destunit == ureg.speed_of_light:
                        destunit = ureg.celsius

                except:
                    destunit = ureg.dimensionless

            for j in range(0, self.data.shape[0]):
                try:
                    u = ureg.parse_units(self.variable_units[idx].lower())
                    if u == ureg.speed_of_light:
                        u = ureg.celsius

                    quan = ureg.Quantity(self.data[j, idx, :], u)
                except:
                    quan = ureg.Quantity(
                        self.data[j, idx, :], ureg.dimensionless)

                axis.plot(quan.to(destunit).magnitude, self.depths[j, idx, :])

            showlegend = showlegend or len(self.observation) > 1
            if not showlegend:
                axis.xaxis.set_label_position('top')
                axis.xaxis.set_ticks_position('top')
                axis.set_xlabel("%s (%s)" % (
                    self.variable_names[idx],
                    utils.mathtext(self.variable_units[idx]),
                ))
            else:
                l = []
                for j in [
                    (gettext("Observed"), self.observation_times),
                    (gettext("Modelled"), self.timestamps)
                ]:
                    for i, name in enumerate(self.names):
                        if len(self.names) == 1:
                            name = ""
                        else:
                            name = name + " "

                        l.append("%s%s (%s)" % (
                            name,
                            j[0],
                            format_datetime(j[1][i])
                        ))

                leg = axis.legend(l, loc='best')

                for legobj in leg.legendHandles:
                    legobj.set_linewidth(4.0)

        ax[0].invert_yaxis()
        ax[0].set_ylabel(gettext("Depth (m)"))

        if len(self.variables) > 0:
            plt.suptitle("\n".join(
                wrap(
                    gettext("Profile for %s, Observed at %s, Modelled at %s")
                    % (
                        ", ".join(self.names),
                        format_datetime(self.observation_time),
                        format_datetime(self.timestamp)
                    ), 80)
            ))
        else:
            plt.suptitle("\n".join(
                wrap(
                    gettext("Profile for %s (%s)") % (
                        ", ".join(self.names),
                        format_datetime(self.observation_time)
                    ), 80)
            ))

        fig.tight_layout()
        fig.subplots_adjust(top=0.88)

        return super(ObservationPlotter, self).plot()
