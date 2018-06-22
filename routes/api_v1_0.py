from flask import Blueprint, Response, request, redirect, send_file, send_from_directory, jsonify
from flask_babel import gettext, format_date
import json
import datetime
from io import BytesIO
from PIL import Image
import io

from oceannavigator.dataset_config import (
    get_variable_name, get_datasets,
    get_dataset_url, get_dataset_climatology, get_variable_scale,
    is_variable_hidden, get_dataset_cache, get_dataset_help,
    get_dataset_name, get_dataset_quantum, get_dataset_attribution
)
from utils.errors import ErrorBase, ClientError, APIError
import utils.misc

from plotting.transect import TransectPlotter
from plotting.drifter import DrifterPlotter
from plotting.map import MapPlotter
from plotting.timeseries import TimeseriesPlotter
from plotting.ts import TemperatureSalinityPlotter
from plotting.sound import SoundSpeedPlotter
from plotting.profile import ProfilePlotter
from plotting.hovmoller import HovmollerPlotter
from plotting.observation import ObservationPlotter
from plotting.class4 import Class4Plotter
from plotting.stick import StickPlotter
from plotting.stats import stats as areastats
from plotting.scripter import constructScript
import plotting.colormap
import plotting.tile
import plotting.scale
import numpy as np
import re
import os
import netCDF4
import base64
import pytz
from data import open_dataset
from data.netcdf_data import NetCDFData
import routes.routes_impl

bp_v1_0 = Blueprint('api_v1_0', __name__) # Creates the blueprint for api queries

#~~~~~~~~~~~~~~~~~~~~~~~
# API INTERFACE 
#~~~~~~~~~~~~~~~~~~~~~~~

#
# Time Conversion Test Functions
#
@bp_v1_0.route('/api/v1.0/timestampconversion/')
def conversion():
  print(request.args.get('date'))
  with open_dataset(get_dataset_url(request.args.get('dataset'))) as dataset:
    date = dataset.convert_to_timestamp(request.args.get('date'))
    return json.dumps(date)

#
# Change to timestamp from v0.0
#
@bp_v1_0.route('/api/v1.0/range/<string:interp>/<int:radius>/<int:neighbours>/<string:dataset>/<string:projection>/<string:extent>/<string:depth>/<string:time>/<string:variable>.json')
def range_query_v1_0(interp, radius, neighbours, dataset, projection, extent, depth, time, variable):
  with open_dataset(get_dataset_url(dataset)) as ds:
    date = ds.convert_to_timestamp(time)
    return routes.routes_impl.range_query_impl(interp, radius, neighbours, dataset, projection, extent, variable, depth, date)


#
# Unchanged from v0.0
#
@bp_v1_0.route('/api/v1.0/')
def info_v1_0():
  return routes.routes_impl.info_impl()


#
# Unchanged from v0.0
#
@bp_v1_0.route('/api/v1.0/<string:q>/')
def query_v1_0(q):
  return routes.routes_impl.query_impl(q)


#
# Unchanged from v0.0
#
@bp_v1_0.route('/api/v1.0/<string:q>/<string:q_id>.json')
def query_id_v1_0(q, q_id):
  return routes.routes_impl.query_id_impl(q, q_id)


# Changes from v0.0:
# ~ Added timestamp conversion
# 
@bp_v1_0.route('/api/v1.0/data/<string:dataset>/<string:variable>/<string:time>/<string:depth>/<string:location>.json')
def get_data_v1_0(dataset, variable, time, depth, location):
  with open_dataset(get_dataset_url(dataset)) as ds:
    date = ds.convert_to_timestamp(time)
    print(date)
    return routes.routes_impl.get_data_impl(dataset, variable, date, depth, location)


#
# Unchanged from v0.0
#
@bp_v1_0.route('/api/v1.0/<string:q>/<stringLprojection>/<int:resolution>/<string:extent>/<string:file_id>.json')
def query_file_v1_0(q, projection, resolution, extent, file_id):
  return routes.routes_impl.query_file_impl(q, projection, resolution, extent, file_id)


#
# Unchanged from v0.0
#
@bp_v1_0.route('/api/v1.0/datasets/')
def query_datasets_v1_0():
  return routes.routes_impl.query_datasets_impl(request.args)


#
# Unchanged from v0.0
#
@bp_v1_0.route('/api/v1.0/colors/')
def colors_v1_0():
  return routes.routes_impl.colors_impl(request.args)


#
# Unchanged from v0.0
#
@bp_v1_0.route('/api/v1.0/colormaps/')
def colormaps_v1_0():
  return routes.routes_impl.colormaps_impl()


#
# Unchanged from v0.0
#
@bp_v1_0.route('/api/v1.0/colormaps.png')
def colormap_image_v1_0():
  return routes.routes_impl.colormap_image_impl()


#
# Unchanged from v0.0
#
@bp_v1_0.route('/api/v1.0/depth/')
def depth_v1():
  return routes.routes_impl.depth_impl(request.args)


#
# Unchanged from v0.0
#
@bp_v1_0.route('/api/v1.0/observationvariables/')
def obs_vars_query_v1():
  return routes.routes_impl.obs_vars_query_impl()


#
# Unchanged from v0.0
#
@bp_v1_0.route('/api/v1.0/variables/')
def vars_query_v1_0():
  return routes.routes_impl.vars_query_impl(request.args)


#
# Unchanged from v0.0
#
@bp_v1_0.route('/api/v1.0/timestamps/')
def time_query_v1_0():
  return routes.routes_impl.time_query_impl(request.args)


#
# Unchanged from v0.0
#
@bp_v1_0.route('/api/v1.0/timestamp/<string:old_dataset>/<int:date>/<string:new_dataset>')
def timestamp_for_date_v1_0(old_dataset, date, new_dataset):
  return routes.routes_impl.timestamp_for_date_impl(old_dataset, date, new_dataset)


#
# Unchanged from v0.0
#
@bp_v1_0.route('/api/v1.0/scale/<string:dataset>/<string:variable>/<string:scale>.png')
def scale_v1_0(dataset, variable, scale):
  return routes.routes_impl.scale_impl(dataset, variable, scale)

#
# Change to timestamp from v0.0
#
@bp_v1_0.route('/api/v1.0/tiles/<string:interp>/<int:radius>/<int:neighbours>/<string:projection>/<string:dataset>/<string:variable>/<string:time>/<string:depth>/<string:scale>/<int:zoom>/<int:x>/<int:y>.png')
def tile_v1_0(projection, interp, radius, neighbours, dataset, variable, time, depth, scale, zoom, x, y):
  with open_dataset(get_dataset_url(dataset)) as ds:
    date = ds.convert_to_timestamp(time)
    return routes.routes_impl.tile_impl(projection, interp, radius, neighbours, dataset, variable, date, depth, scale, zoom, x, y)


#
# Unchanged from v0.0
#
@bp_v1_0.route('/api/v1.0/tiles/topo/<string:projection>/<int:zoom>/<int:x>/<int:y>.png')
def topo_v1_0(projection, zoom, x, y):
  return routes.routes_impl.topo_impl(projection, zoom, x, y)


#
# Unchanged from v0.0
#
@bp_v1_0.route('/api/v1.0/tiles/bath/<string:projection>/<int:zoom>/<int:x>/<int:y>.png')
def bathymetry_v1_0(projection, zoom, x, y):
  return routes.routes_impl.bathymetry_impl(projection, zoom, x, y)


#
# Unchanged from v0.0
#
@bp_v1_0.route('/api/v1.0/drifters/<string:q>/<string:drifter_id>')
def drifter_query_v1_0(q, drifter_id):
  return routes.routes_impl.drifter_query_impl(q, drifter_id)


#
# Unchanged from v0.0
#
@bp_v1_0.route('/api/v1.0/class4/<string:q>/<string:class4_id>/<string:index>')
def class4_query_v1_0(q, class4_id, index):
    return routes.routes_impl.class4_query_impl(q, class4_id, index)


#
# Unchanged from v0.0
#
@bp_v1_0.route('/api/v1.0/subset/')
def subset_query_v1_0():
    return routes.routes_impl.subset_query_impl(request.args)


#
# Change to timestamp from v0.0
#
@bp_v1_0.route('/api/v1.0/plot/', methods=['GET', 'POST'])
def plot_v1_0():

  if request.method == 'GET':
    args = request.args
  else:
    args = request.form
  query = json.loads(args.get('query'))

  with open_dataset(get_dataset_url(query.get('dataset'))) as dataset:
    date = dataset.convert_to_timestamp(query.get('time'))
    date = {'time' : date}
    query.update(date)

    return routes.routes_impl.plot_impl(args, query)

#
# Change to timestamp from v0.0
#
@bp_v1_0.route('/api/v1.0/stats/', methods=['GET', 'POST'])
def stats_v1_0():

  if request.method == 'GET':
    args = request.args
  else:
    args = request.form
  query = json.loads(args.get('query'))

  with open_dataset(get_dataset_url(query.get('dataset'))) as dataset:
    date = dataset.convert_to_timestamp(query.get('time'))
    date = {'time' : date}
    query.update(date)

    return routes.routes_impl.stats_impl(args, query)






