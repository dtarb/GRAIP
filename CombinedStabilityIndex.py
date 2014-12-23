__author__ = 'Pabitra'
from osgeo import ogr, gdal, osr
from gdalconst import *
import numpy as np
import pyodbc
import sys
import click
import os
import math
import subprocess
import utils

# TODO: Need to find out how to catch gdal exceptions

gdal.UseExceptions()

@click.command()
@click.option('--params', default=r"E:\Graip\GRAIPPythonTools\demo\demo_CSI\csi_inputs.txt", type=click.Path(exists=True))
def main(params):
    params_dict = _get_initialized_parameters_dict()
    if not _validate_args(params, params_dict):
        sys.exit(1)

    base_raster_file = params_dict[ParameterNames.dinf_slope_file]
    if params_dict[ParameterNames.dinf_sca_min_file] and params_dict[ParameterNames.dinf_sca_max_file]:
        temp_raster_file_weight_min = os.path.join(os.path.dirname(params_dict[ParameterNames.dinf_slope_file]), 'weightmin.tif')
        temp_raster_file_weight_max = os.path.join(os.path.dirname(params_dict[ParameterNames.dinf_slope_file]), 'weightmax.tif')
        utils.initialize_output_raster_file(base_raster_file, temp_raster_file_weight_min)
        utils.initialize_output_raster_file(base_raster_file, temp_raster_file_weight_max)
        _create_weight_grids_from_points(temp_raster_file_weight_min, temp_raster_file_weight_max, params_dict)
        # generate catchment areas
        _taudem_area_dinf(temp_raster_file_weight_min, params_dict[ParameterNames.demang_file], params_dict[ParameterNames.dinf_sca_min_file])
        _taudem_area_dinf(temp_raster_file_weight_max, params_dict[ParameterNames.demang_file], params_dict[ParameterNames.dinf_sca_max_file])

    messages = _generate_combined_stability_index_grid(params_dict)
    for msg in messages:
        print(msg + '\n')

    _sindex_drain_points(params_dict)

    print("done....")


def _get_initialized_parameters_dict():
    params = {}
    params[ParameterNames.mdb] = None
    params[ParameterNames.drain_points_file] = None
    params[ParameterNames.dinf_slope_file] = None
    params[ParameterNames.demang_file] = None
    params[ParameterNames.dinf_sca_file] = None
    params[ParameterNames.dinf_sca_min_file] = None
    params[ParameterNames.dinf_sca_max_file] = None
    params[ParameterNames.cal_csv_file] = None
    params[ParameterNames.cal_grid_file] = None
    params[ParameterNames.csi_grid_file] = None
    params[ParameterNames.sat_grid_file] = None
    params[ParameterNames.road_impact] = None
    params[ParameterNames.dpt_broad_base_dip] = None
    params[ParameterNames.dpt_diffuse_drain] = None
    params[ParameterNames.dpt_ditch_relief] = None
    params[ParameterNames.dpt_lead_off] = None
    params[ParameterNames.dpt_non_engineered] = None
    params[ParameterNames.dpt_stream_crossing] = None
    params[ParameterNames.dpt_sump] = None
    params[ParameterNames.dpt_water_bar] = None
    params[ParameterNames.dpt_excavated_stream_crossing] = None
    params[ParameterNames.road_width] = None
    params[ParameterNames.min_terrain_recharge] = None
    params[ParameterNames.max_terrain_recharge] = None
    params[ParameterNames.min_additional_runoff] = None
    params[ParameterNames.max_additional_runoff] = None
    params[ParameterNames.gravity] = None
    params[ParameterNames.rhow] = None
    return params

class ParameterNames(object):
    mdb = 'mdb'
    drain_points_file = 'drainpoints'
    dinf_slope_file = 'slp'
    demang_file = 'ang'
    dinf_sca_file = 'sca'
    dinf_sca_min_file = 'scamin'
    dinf_sca_max_file = 'scamax'
    cal_csv_file = 'calpar'
    cal_grid_file = 'cal'
    csi_grid_file = 'si'
    sat_grid_file = 'sat'
    road_impact = 'roadimpact'
    dpt_broad_base_dip = 'broadbasedip'
    dpt_diffuse_drain = 'diffusedrain'
    dpt_ditch_relief = 'ditchrelief'
    dpt_lead_off = 'leadoff'
    dpt_non_engineered = 'nonengineered'
    dpt_stream_crossing = 'streamcrossing'
    dpt_sump = 'sump'
    dpt_water_bar = 'waterbar'
    dpt_excavated_stream_crossing = 'excavatedstreamcrossing'
    road_width = 'roadwidth'
    min_terrain_recharge = 'minimumterrainrecharge'
    max_terrain_recharge = 'maximumterrainrecharge'
    min_additional_runoff = 'minimumadditionalroadsurfacerunoff'
    max_additional_runoff = 'maximumadditionalroadsurfacerunoff'
    gravity = 'g'
    rhow = 'rhow'


def _validate_args(params, params_dict):
    driver = ogr.GetDriverByName(utils.GDALFileDriver.ShapeFile())
    with open(params, 'r') as file_obj:
        for line in file_obj:
            line = line.strip(' ')
            line = line.strip('\n')
            if len(line) > 0:
                if not line.startswith('#'):
                    try:
                        key, value = line.split('=')
                        if key not in params_dict:
                            print("Invalid parameter name in the input file (%s)." % params)
                            return False
                        else:
                            params_dict[key] = value.rstrip('\n')
                    except:
                        print "Input file (%s) has invalid data format." % params
                        return False

    if params_dict[ParameterNames.dinf_sca_min_file] and not params_dict[ParameterNames.dinf_sca_max_file]:
        print "Input file (%s) has invalid data format." % params
        return False

    if not params_dict[ParameterNames.dinf_sca_min_file] and params_dict[ParameterNames.dinf_sca_max_file]:
        print "Input file (%s) has invalid data format." % params
        return False

    for key in params_dict:
        if not params_dict[key]:
            if key not in (ParameterNames.demang_file, ParameterNames.dinf_sca_min_file, ParameterNames.dinf_sca_max_file):
                print("Invalid input file (%s). Value for one or more parameters is missing." % params)
                return False

        if key in (ParameterNames.dpt_broad_base_dip, ParameterNames.dpt_diffuse_drain, ParameterNames.dpt_ditch_relief,
                   ParameterNames.dpt_lead_off, ParameterNames.dpt_non_engineered, ParameterNames.dpt_stream_crossing,
                   ParameterNames.dpt_sump, ParameterNames.dpt_water_bar, ParameterNames.dpt_excavated_stream_crossing):
            if not params_dict[key] in ('On', 'Off'):
                print("Invalid input file (%s). Data provided for drain point type parameter is invalid." % params)
                return False

        if key in (ParameterNames.road_width, ParameterNames.min_terrain_recharge, ParameterNames.max_terrain_recharge,
                   ParameterNames.min_additional_runoff, ParameterNames.max_additional_runoff, ParameterNames.gravity, ParameterNames.rhow):
            try:
                float(params_dict[key])
            except:
                print("Invalid input file (%s). Parameter (%s) needs to have a numeric value." % (params, key))
                return False

        # check that certain parameters that have file path values, that those file exists
        if key in (ParameterNames.drain_points_file, ParameterNames.demang_file, ParameterNames.cal_csv_file,
                   ParameterNames.dinf_sca_file, ParameterNames.dinf_slope_file, ParameterNames.cal_grid_file):
            if key == ParameterNames.demang_file:
                if not params_dict[key]:
                    continue

            input_file = params_dict[key]
            if not os.path.dirname(input_file):
                input_file = os.path.join(os.getcwd(), params_dict[key])

            if not os.path.isfile(input_file):
                print("Invalid input file (%s). %s file can't be found." % (params, params_dict[key]))
                return False

        # Test that the drainpoints file is a shapefile
        if key == ParameterNames.drain_points_file:
            try:
                dataSource = driver.Open(params_dict[key], 1)
                if not dataSource:
                    #raise Exception("Not a valid shape file (%s)" % rd)
                    print("Invalid input file (%s). Not a valid shape file (%s) provided for parameter (%s)."
                          % (params, params_dict[key], key))
                    return False
                else:
                    dataSource.Destroy()
            except Exception as e:
                print(e.message)
                return False

        # check that all other input grid files can be opened.
        if key in (ParameterNames.demang_file, ParameterNames.dinf_sca_file, ParameterNames.dinf_slope_file,
                   ParameterNames.cal_grid_file):

            input_file = params_dict[key]
            if not input_file:
                # check if it is one of the optional input files
                if key in (ParameterNames.demang_file, ParameterNames.dinf_sca_min_file, ParameterNames.dinf_sca_max_file):
                    continue

            if not os.path.dirname(input_file):
                input_file = os.path.join(os.getcwd(), params_dict[key])
            try:
                dem = gdal.Open(input_file)
                dem = None
            except Exception as e:
                print(e.message)
                return False

        # check that the output grid file path exists
        if key in (ParameterNames.csi_grid_file, ParameterNames.sat_grid_file, ParameterNames.dinf_sca_min_file, ParameterNames.dinf_sca_max_file):
            if params_dict[key]:
                grid_file_dir = os.path.dirname(os.path.abspath(params_dict[key]))
                if not os.path.exists(grid_file_dir):
                    print ("Invalid output file (%s). File path (%s) for grid output file does not exist. "
                           "Invalid parameter (%s) value." % (params, grid_file_dir, key))
                    return False

    # check that the graip database file exists and can be opened
    try:
        if not os.path.dirname(params_dict[ParameterNames.mdb]):
            mdb = os.path.join(os.getcwd(), params_dict[ParameterNames.mdb])
        conn = pyodbc.connect(utils.MS_ACCESS_CONNECTION % params_dict[ParameterNames.mdb])
        conn.close()
    except pyodbc.Error as e:
        print(e)
        return False

    return True


def _create_weight_grids_from_points(weight_min_raster_file, weight_max_raster_file, params_dict):
    # Reference: c++ function: createweightgridfrompoints

    """
    Creates the temporary weight grids (min adn max) to be used with TauDEM areadinf function
    :param weight_min_raster_file:
    :param weight_max_raster_file:
    :param params_dict:
    :return:
    """
    driver = ogr.GetDriverByName(utils.GDALFileDriver.ShapeFile())
    data_source = driver.Open(params_dict[ParameterNames.drain_points_file], 1)
    layer = data_source.GetLayer()
    layer_defn = layer.GetLayerDefn()
    try:
        layer_defn.GetFieldIndex('GRAIPDID')
    except:
        print ("Invalid drain points shape file. Attribute 'GRAIPDID' is missing.")
        sys.exit(1)

    try:
        conn = pyodbc.connect(utils.MS_ACCESS_CONNECTION % params_dict[ParameterNames.mdb])
        cursor = conn.cursor()
        dp_rows = cursor.execute("SELECT * FROM DrainPoints ORDER BY GRAIPDID ASC").fetchall()
        dp_type_rows = cursor.execute("SELECT * FROM DrainTypeDefinitions").fetchall()

        accum_rmax = {}
        accum_rmin = {}

        for row in dp_rows:
            accum_area = 0
            matching_dp_type_row = [dpt_row for dpt_row in dp_type_rows if dpt_row.DrainTypeID == row.DrainTypeID][0]
            drain_type_name = matching_dp_type_row.DrainTypeName.lower().replace('_', '').replace('-', '').replace(' ', '')
            if drain_type_name not in params_dict:
                if matching_dp_type_row.CCSI:
                    accum_area = row.ELength * float(params_dict[ParameterNames.road_width])

            elif params_dict[drain_type_name] == "On":
                accum_area = row.ELength * float(params_dict[ParameterNames.road_width])

            accum_rmin[row.GRAIPDID] = accum_area * float(params_dict[ParameterNames.min_additional_runoff])
            accum_rmax[row.GRAIPDID] = accum_area * float(params_dict[ParameterNames.max_additional_runoff])

        # open the output temp weight grid files to write data to it
        weight_min_grid_file = gdal.Open(weight_min_raster_file, GA_Update)
        weight_max_grid_file = gdal.Open(weight_max_raster_file, GA_Update)

        # for each drain point in shape file
        for dp in layer:
            geom = dp.GetGeometryRef()

            # find weight grid row and col corresponding to drain point
            row, col = utils.get_coordinate_to_grid_row_col(geom.GetX(0), geom.GetY(0), weight_min_grid_file)
            geom = None
            # get the id of the drain point from shape file
            graipdid = dp.GetField('GRAIPDID')

            def _write_weight_to_grid(grid_file, weight_values):
                # create a 2D array to store weight data
                weight_array = np.zeros((1, 1), dtype=np.float32)
                grid_file_band = grid_file.GetRasterBand(1)
                # get current grid cell data
                current_cell_data = grid_file_band.ReadAsArray(xoff=col, yoff=row, win_xsize=1, win_ysize=1)
                if current_cell_data[0][0] != utils.NO_DATA_VALUE:
                    weight_array[0][0] = weight_values[graipdid]

                # here we are writing to a specific cell of the grid
                grid_file_band.WriteArray(weight_array, xoff=col, yoff=row)

            _write_weight_to_grid(weight_min_grid_file, accum_rmin)
            _write_weight_to_grid(weight_max_grid_file, accum_rmax)

        grid_file_band = weight_min_grid_file.GetRasterBand(1)
        grid_file_band.FlushCache()
        grid_file_band = weight_max_grid_file.GetRasterBand(1)
        grid_file_band.FlushCache()

    except:
        raise
    finally:
        if data_source:
            data_source.Destroy()

        if conn:
            conn.close()

        weight_min_grid_file = None
        weight_max_grid_file = None


def _taudem_area_dinf(weight_grid_file, demang_grid_file, output_sca_file):

    # mpiexec -n 4 Areadinf -ang demang.tif -wg demdpsi.tif -sca demsac.tif
    #taudem_funtion_to_run = 'mpiexec -n 4 Areadinf'
    taudem_function_to_run = 'Areadinf'
    cmd = taudem_function_to_run + \
          ' -ang ' + demang_grid_file + \
          ' -wg ' + weight_grid_file + \
          ' -sca ' + output_sca_file

    # Capture the contents of shell command and print it to the arcgis dialog box
    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    taudem_messages = []
    # Submit command to operating system
    os.system(cmd)
    for line in process.stdout.readlines():
        taudem_messages.append(line)
    return taudem_messages


def _generate_combined_stability_index_grid(params_dict):

    # TauDEMm SinmapSI calling format
    # mpiexec -n 4 SinmapSI -slp demslp.tif -sca demsca.tif -calpar demcalp.txt -cal demcal.tif -si demsi.tif -sat demsat.tif -par 0.0009 0.00135 9.81 1000 -scamin scamin.tif -scamax scamax.tif

    #taudem_function_to_run = r'E:\SoftwareProjects\TauDEM\Taudem5PCVS2010\x64\Release\SinmapSI'
    taudem_function_to_run = 'SinmapSI'

    cmd = taudem_function_to_run + \
          ' -slp ' + params_dict[ParameterNames.dinf_slope_file] + \
          ' -sca ' + params_dict[ParameterNames.dinf_sca_file] + \
          ' -calpar ' + params_dict[ParameterNames.cal_csv_file] + \
          ' -cal ' + params_dict[ParameterNames.cal_grid_file] + \
          ' -si ' + params_dict[ParameterNames.csi_grid_file] + \
          ' -sat ' + params_dict[ParameterNames.sat_grid_file] + \
          ' -par ' + params_dict[ParameterNames.min_terrain_recharge] + ' ' + params_dict[ParameterNames.max_terrain_recharge] + ' ' + params_dict[ParameterNames.gravity] + ' ' + params_dict[ParameterNames.rhow]

    if params_dict[ParameterNames.dinf_sca_min_file] and params_dict[ParameterNames.dinf_sca_max_file]:
        cmd += ' -scamin ' + params_dict[ParameterNames.dinf_sca_min_file] + \
               ' -scamax ' + params_dict[ParameterNames.dinf_sca_max_file]

    # Capture the contents of shell command and print it to the arcgis dialog box
    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    taudem_messages = []
    # Submit command to operating system
    os.system(cmd)
    for line in process.stdout.readlines():
        taudem_messages.append(line)
    return taudem_messages


def _sindex_drain_points(parm_dict):
    # for each drain point in the drain points shape file find the cell value in the combined stability index grid file
    # and use that value to populate the corresponding row in the drainpoints table
    driver = ogr.GetDriverByName(utils.GDALFileDriver.ShapeFile())
    dataSource = driver.Open(parm_dict[ParameterNames.drain_points_file], 1)
    layer = dataSource.GetLayer()
    layerDefn = layer.GetLayerDefn()
    fld_index_graipdid = layerDefn.GetFieldIndex('GRAIPDID')

    si_grid = gdal.Open(parm_dict[ParameterNames.csi_grid_file])
    si_band = si_grid.GetRasterBand(1)

    road_impact = False
    if parm_dict[ParameterNames.dinf_sca_min_file] and parm_dict[ParameterNames.dinf_sca_max_file]:
        road_impact = True

    try:
        if road_impact:
            field_to_create = 'SIR'
        else:
            field_to_create = 'SI'

        #delete field if it exists in drainpoints shapefile
        fld_index_dp = layerDefn.GetFieldIndex(field_to_create)
        if fld_index_dp > 0:
            layer.DeleteField(fld_index_dp)

        # add a new field (column) to the attribute table of drainpoints shapefile
        layer.CreateField(ogr.FieldDefn(field_to_create, ogr.OFTReal))

        fld_index_dp = layerDefn.GetFieldIndex(field_to_create)
    except:
        pass

    try:
        conn = pyodbc.connect(utils. MS_ACCESS_CONNECTION % parm_dict[ParameterNames.mdb])
        cursor = conn.cursor()

        for feature in layer:
            geom = feature.GetGeometryRef()
            total_points = geom.GetPointCount()
            if total_points > 0:
                # calculate range from the elevation of 2 end points of the road segment
                row, col = utils.get_coordinate_to_grid_row_col(geom.GetX(0), geom.GetY(0), si_grid)
                si_cell_data = si_band.ReadAsArray(xoff=col, yoff=row, win_xsize=1, win_ysize=1)
                graipdid = feature.GetFieldAsInteger(fld_index_graipdid)
                dp_row = cursor.execute("SELECT * FROM DrainPoints WHERE GRAIPDID=%d" % graipdid).fetchone()

                if dp_row:
                    if si_cell_data[0][0] == si_band.GetNoDataValue():
                        if road_impact:
                            dp_row.SIR = -9999
                        else:
                            dp_row.SI = -9999
                    else:
                        if road_impact:
                            dp_row.SIR = float(si_cell_data[0][0])
                        else:
                            dp_row.SI = float(si_cell_data[0][0])

                    if road_impact:
                        update_sql = "UPDATE DrainPoints SET SIR=? WHERE GRAIPDID=?"
                        data = (dp_row.SIR, dp_row.GRAIPDID)
                    else:
                        update_sql = "UPDATE DrainPoints SET SI=? WHERE GRAIPDID=?"
                        data = (dp_row.SI, dp_row.GRAIPDID)

                    cursor.execute(update_sql, data)

                    # write si data to drainpoints shapefile
                    feature.SetField(fld_index_dp, data[0])
                    # rewrite the feature to the layer - this will in fact save the data to the file
                    layer.SetFeature(feature)

            geom = None

        conn.commit()
    except:
        raise
    finally:
        # cleanup
        if conn:
            conn.close

        if dataSource:
            dataSource.Destroy()


if __name__ == '__main__':
    try:
        main()
        sys.exit(0)
    except Exception as e:
        print "Combined stability index computation failed."
        print(e.message)
        sys.exit(1)