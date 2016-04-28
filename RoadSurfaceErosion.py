__author__ = 'Pabitra'

import os
import sys

from datetime import datetime

from numpy.numarray import array
from osgeo import ogr, gdal, osr
import numpy as np
import pyodbc
import click

from scipy import interpolate
from gdalconst import *

import utils

# TODO: Need to find out how to catch gdal exceptions

gdal.UseExceptions()


# Use the followings for debugging within PyCharm:
# change the signature of the main function to include the additional argument 'extra_args' as shown below
# def main(dp, rd, mdb, z, dpsi, sc, extra_args):
# @click.command(context_settings=dict(
#     ignore_unknown_options=True,
# ))
# @click.option('--dp', default=r"E:\Graip\GRAIPPythonTools\demo\demo_RSE\drainpoints.shp", type=click.Path(exists=True))
# @click.option('--rd', default=r"E:\Graip\GRAIPPythonTools\demo\demo_RSE\roadlines.shp", type=click.Path(exists=True))
# @click.option('--mdb', default=r"E:\Graip\GRAIPPythonTools\demo\demo_RSE\test.mdb", type=click.Path(exists=True))
# @click.option('--z', default=r"E:\Graip\GRAIPPythonTools\demo\demo_RSE\DEM\dem.tif", type=click.Path(exists=True))
# @click.option('--dpsi', default=r"E:\Graip\GRAIPPythonTools\demo\demo_RSE\demdpsi.tif", type=click.Path(exists=False))
# @click.option('--sc', default=True, type=click.BOOL)


@click.command()
@click.option('--dp', default="drainpoints.shp", type=click.Path(exists=True))
@click.option('--rd', default="roadlines.shp", type=click.Path(exists=True))
@click.option('--mdb', default="test.mdb", type=click.Path(exists=True))
@click.option('--z', default="DEM\dem.tif", type=click.Path(exists=True))
@click.option('--dpsi', default="demdpsi.tif", type=click.Path(exists=False))
@click.option('--sc', is_flag=True)
def main(dp, rd, mdb, z, dpsi, sc):
    """
    This script computes road sediment production and writes sediment
    related data to the RoadLines table (affected table columns are: Length, Slope, SedProd1
    SedProd2, TotSedProd, TotSedDel, UnitTotSedDel, UnitSed) and DrainPoints table (affected table columns are:
    SedProd, ELength, UnitSed, SedDel). It also creates the weight sediment grid file (dpsi)

    :param --dp: Path to the drainpoints shape file
    :param --rd: Path to the roadlines shape file
    :param --mdb: Path to the graip Access database file
    :param --z: Path to the dem file
    :param --dpsi: Path to the output weight sediment production grid file
    :param --sc: A flag if provided sediment production will be writen to grid file for only stream connected drain points, otherwise for all drain points
    :return: None
    """
    # print(">>>> Start time:" + str(datetime.now()))
    _validate_args(dp, rd, z, mdb, dpsi)
    input_dem = z

    # check if the dir path is missing for the database file, then add the current dir path to the file name
    # Access driver needs the full path to the database file to open it.
    if not os.path.dirname(mdb):
        mdb = os.path.join(os.getcwd(), mdb)

    graip_db = mdb
    rd_shapefile = rd
    dp_shapefile = dp
    dpsi_gridfile = dpsi

    if sc:
        is_stream_connected = True
    else:
        is_stream_connected = False

    print ("Please wait a few minutes. Computation is in progress ...")
    compute_length_elevation_interpolation(rd_shapefile, input_dem)
    compute_road_sediment_production(rd_shapefile, graip_db)
    compute_drainpoint_sediment_production(graip_db)
    create_drainpoint_weighted_grid(input_dem, graip_db, dpsi_gridfile, dp_shapefile, is_stream_connected)
    print ("Road surface erosion computation finished successfully.")
    #print(">>>> Finish time:" + str(datetime.now()))


def compute_length_elevation_interpolation(rd_shapefile, input_dem):
    """
    Calculates road segment length and elevation and writes to roadlines shapefile

    :param rd_shapefile: Path to roadlines shapefile
    :param input_dem: Path to dem file
    :return: None
    """
    # DEBUG:
    print ("Computing length/elevation interpolation...")

    driver = ogr.GetDriverByName(utils.GDALFileDriver.ShapeFile())
    dataSource = driver.Open(rd_shapefile, 1)
    layer = dataSource.GetLayer()
    layerDefn = layer.GetLayerDefn()

    dem = gdal.Open(input_dem)
    dem_nx = dem.RasterXSize
    dem_ny = dem.RasterYSize
    gt = dem.GetGeoTransform()
    dem_band = dem.GetRasterBand(1)

    # Compute mid-point grid spacings
    # ref: http://gis.stackexchange.com/questions/7611/bilinear-interpolation-of-point-data-on-a-raster-in-python
    # gt[0] dem originX
    # gt[3] dem originY
    # gt[1] dem cell width (in pixel)
    # gt[5] dem cell height (in pixel)

    ax = array([gt[0] + ix*gt[1] + gt[1]/2.0 for ix in range(dem_nx)])
    ay = array([gt[3] + iy*gt[5] + gt[5]/2.0 for iy in range(dem_ny)])

    try:
        # delete field "Length" if it exists
        fld_index = layerDefn.GetFieldIndex('Length')
        if fld_index > 0:
            layer.DeleteField(fld_index)

        # delete "Range" if it exists
        fld_index = layerDefn.GetFieldIndex('Range')
        if fld_index > 0:
            layer.DeleteField(fld_index)
    except:
        pass

    # add a new field (column) 'Length' to the attribute table
    layer.CreateField(ogr.FieldDefn('Length', ogr.OFTReal))
    fld_index_length = layerDefn.GetFieldIndex('Length')

    # add a new field (column) 'Range' to the attribute table
    layer.CreateField(ogr.FieldDefn('Range', ogr.OFTReal))
    fld_index_range = layerDefn.GetFieldIndex('Range')

    for feature in layer:
        try:
            geom = feature.GetGeometryRef()
            if geom:
                total_points = geom.GetPointCount()
                # write length value to shapefile
                # feature.SetField(fld_index_length, geom.Length())
                rd_length = geom.Length()
                if total_points > 0:
                    # calculate range from the elevation of 2 end points of the road segment
                    # using interpolation

                    # first find the row, col of the dem corresponding to
                    # the fist point of the road segment
                    row, col = utils.get_coordinate_to_grid_row_col(geom.GetX(0), geom.GetY(0), dem)
                    # get the dem cells corresponding to row, col needed to generate the interpolation function
                    dem_array = dem_band.ReadAsArray(xoff=col, yoff=row, win_xsize=2, win_ysize=2)
                    # define the interpolation function
                    bilinterp = interpolate.interp2d(ax[col:col+2], ay[row:row+2], dem_array,
                                                     kind='linear')

                    # find the elevation of the 1st point using the interpolation function
                    elevation_1 = bilinterp(geom.GetX(0), geom.GetY(0))[0]

                    # find the row, col of the dem corresponding to
                    # the 2nd point of the road segment
                    row, col = utils.get_coordinate_to_grid_row_col(geom.GetX(total_points-1),
                                                                    geom.GetY(total_points-1), dem)
                    # get the dem cells corresponding to row, col needed to generate the interpolation function
                    dem_array = dem_band.ReadAsArray(xoff=col, yoff=row, win_xsize=2, win_ysize=2)
                    # define the interpolation function
                    bilinterp = interpolate.interp2d(ax[col:col+2], ay[row:row+2], dem_array,
                                                     kind='linear')

                    # find the elevation of the 1st point using the interpolation function
                    elevation_2 = bilinterp(geom.GetX(total_points-1), geom.GetY(total_points-1))[0]
                    rd_range = abs(elevation_2 - elevation_1)
                else:
                    rd_range = 0    # sometimes shape/feature have no points - in that case we say range is zero
            else:
                rd_length = 0
                rd_range = 0

            # write length value to shapefile
            feature.SetField(fld_index_length, rd_length)
            # write range value to shapefile
            feature.SetField(fld_index_range, rd_range)

            # rewrite the feature to the layer - this will in fact save the data
            layer.SetFeature(feature)
            geom = None

        except Exception as ex:
            dataSource.Destroy()
            raise

    # close datasource
    dataSource.Destroy()
    # DEBUG:
    print ("Finished computing length/elevation interpolation...")


def _validate_args(dp, rd, z, mdb, dpsi):
    # DEBUG:
    print ("Validating inputs...")
    driver = ogr.GetDriverByName(utils.GDALFileDriver.ShapeFile())
    try:
        dataSource = driver.Open(dp, GA_ReadOnly)
        if not dataSource:
            raise utils.ValidationException("Not a valid shapefile (%s) provided for parameter --dp." % dp)
        else:
            dataSource.Destroy()
    except Exception as e:
        msg = "Failed to open the shapefile (%s) provided for parameter --dp. " % dp + e.message
        raise utils.ValidationException(msg)

    try:
        dataSource = driver.Open(rd, GA_ReadOnly)
        if not dataSource:
            raise utils.ValidationException("Not a valid shapefile (%s) provided for parameter --rd." % rd)
        else:
            dataSource.Destroy()
    except Exception as e:
        msg = "Failed to open the shapefile (%s) provided for parameter --rd. " % rd + e.message
        raise utils.ValidationException(msg)

    dpsi_dir = os.path.dirname(os.path.abspath(dpsi))
    if not os.path.exists(dpsi_dir):
        raise utils.ValidationException("File path '(%s)' for output file (parameter --dpsi) does not exist." % dpsi_dir)
    try:
        if not os.path.dirname(mdb):
            mdb = os.path.join(os.getcwd(), mdb)

        conn = pyodbc.connect(utils.MS_ACCESS_CONNECTION % mdb)
        conn.close()
    except pyodbc.Error as ex:
        raise utils.ValidationException(ex.message)

    try:
        dem = gdal.Open(z)
        dem = None
    except Exception as ex:
        raise utils.ValidationException(ex.message)

    # DEBUG:
    print ("Finished validating inputs...")


def compute_road_sediment_production(rd_shapefile, graip_db):
    """
    Populates the RoadLine table with sediment related data

    :param rd_shapefile: path to the roadlines shapefile
    :param graip_db: path to the graip database file
    :return: None
    """
    # DEBUG:
    print ("Starting to write sediment production to database (RoadLines).")

    driver = ogr.GetDriverByName(utils.GDALFileDriver.ShapeFile())
    dataSource = driver.Open(rd_shapefile, 1)
    layer = dataSource.GetLayer()
    layerDefn = layer.GetLayerDefn()
    fld_index_griapid = layerDefn.GetFieldIndex('GRAIPRID')
    fld_index_range = layerDefn.GetFieldIndex('Range')
    fld_index_length = layerDefn.GetFieldIndex('Length')

    # store all the road segments in a list
    features = [ft for ft in layer]

    try:
        conn = pyodbc.connect(utils.MS_ACCESS_CONNECTION % graip_db)
        cursor = conn.cursor()
        roadlines_rows = cursor.execute("SELECT * FROM RoadLines").fetchall()

        for row in roadlines_rows:
            roadnetwork_row = cursor.execute("SELECT * FROM RoadNetworkDefinitions WHERE RoadNetworkID=%d"
                                             % row.RoadNetworkID).fetchone()
            if not roadnetwork_row:
                base_rate = 75
            else:
                base_rate = roadnetwork_row.BaseRate

            flowpathvegdef_row = cursor.execute("SELECT * FROM FlowPathVegDefinitions WHERE FlowPathVegID=%d"
                                                % row.FlowPathVeg1ID).fetchone()
            if not flowpathvegdef_row:
                ditch_veg_multiplier_1 = 1
            else:
                ditch_veg_multiplier_1 = flowpathvegdef_row.Multiplier

            flowpathvegdef_row = cursor.execute("SELECT * FROM FlowPathVegDefinitions WHERE FlowPathVegID=%d"
                                                % row.FlowPathVeg2ID).fetchone()
            if not flowpathvegdef_row:
                ditch_veg_multiplier_2 = 1
            else:
                ditch_veg_multiplier_2 = flowpathvegdef_row.Multiplier

            surfacetypedef_row = cursor.execute("SELECT * FROM SurfaceTypeDefinitions WHERE SurfaceTypeID=%d"
                                                % row.SurfaceTypeID).fetchone()

            if not surfacetypedef_row:
                surface_multiplier = 1
            else:
                surface_multiplier = surfacetypedef_row.Multiplier

            selected_features = [ft for ft in features if ft.GetFieldAsInteger(fld_index_griapid) == row.GRAIPRID]

            if selected_features:
                feature = selected_features[0]
                road_range = feature.GetFieldAsDouble(fld_index_range)
                road_length = feature.GetFieldAsDouble(fld_index_length)
                if row.FlowPathVeg1ID != 1:
                    sed_prod_1 = base_rate * road_range * surface_multiplier * ditch_veg_multiplier_1 / 2
                else:
                    sed_prod_1 = base_rate * road_range * surface_multiplier * ditch_veg_multiplier_2 / 2

                # TODO: check this calculation with Dave (why the logic is different from above?)
                if row.FlowPathVeg2ID != 1:
                    sed_prod_2 = base_rate * road_range * surface_multiplier * ditch_veg_multiplier_2 / 2   # should this be ditch_veg_multiplier_1
                else:
                    sed_prod_2 = base_rate * road_range * surface_multiplier * ditch_veg_multiplier_1 / 2   # should this be ditch_veg_multiplier_2

                # update RoadLines table with sed production data
                # Note: Setting table row fields to new values doesn't update the field values
                row.SedProd1 = sed_prod_1
                row.SedProd2 = sed_prod_2
                row.TotSedProd = sed_prod_1 + sed_prod_2
                stream_con_1 = 0 if row.StreamConnect1ID == 1 or row.StreamConnect1ID == 0 else 1
                stream_con_2 = 0 if row.StreamConnect2ID == 1 or row.StreamConnect2ID == 0 else 1
                row.TotSedDel = sed_prod_1 * stream_con_1 + sed_prod_2 * stream_con_2
                row.Length = road_length

                update_sql = "UPDATE RoadLines SET SedProd1=?, SedProd2=?, TotSedProd=?, TotSedDel=?, Length=? " \
                             "WHERE GRAIPRID=?"
                data = (row.SedProd1, row.SedProd2, row.TotSedProd, row.TotSedDel, row.Length, row.GRAIPRID)
                cursor.execute(update_sql, data)

                if road_length > 0:
                    row.Slope = road_range / road_length
                    row.UnitSed = row.TotSedProd / road_length
                    row.UnitTotSedDel = row.TotSedDel / road_length

                    update_sql = "UPDATE RoadLines SET Slope=?, UnitSed=?, UnitTotSedDel=? WHERE GRAIPRID=?"
                    data = (row.Slope, row.UnitSed, row.UnitTotSedDel, row.GRAIPRID)
                    cursor.execute(update_sql, data)
                else:
                    row.Slope = 0
                    row.UnitSed = 0
                    row.UnitTotSedDel = 0

                update_sql = "UPDATE RoadLines SET Slope=?, UnitSed=?, UnitTotSedDel=? WHERE GRAIPRID=?"
                data = (row.Slope, row.UnitSed, row.UnitTotSedDel, row.GRAIPRID)
                cursor.execute(update_sql, data)

            conn.commit()
        # DEBUG:
        print ("Finished writing sediment production to database (RoadLines).")
    except:
        raise
    finally:
        # cleanup
        if conn:
            conn.close

        if dataSource:
            dataSource.Destroy()


def compute_drainpoint_sediment_production(graip_db):
    """
    Populates the DrainPoints table with sediment production related data.
    Table columns updated are: SedProd, ELength, UnitSed, SedDel

    :param graip_db: Path to graip database file
    :return: None
    """
    # DEBUG:
    print ("Starting to write sediment production to database (DrainPoints).")
    try:
        conn = pyodbc.connect(utils.MS_ACCESS_CONNECTION % graip_db)
        cursor = conn.cursor()
        dp_rows = cursor.execute("SELECT * FROM DrainPoints ORDER BY GRAIPDID").fetchall()
        for dp_row in dp_rows:
            # sum sediment and road length for the first side of the road
            sql_select = "SELECT SUM(SedProd1) As SumSedProd1, SUM(Length) As SumLength FROM RoadLines " \
                         "WHERE GRAIPDID1=? GROUP BY GRAIPDID1"
            dp_row_sum = cursor.execute(sql_select, dp_row.GRAIPDID).fetchone()
            e_length_dp = 0
            sed_prod_1 = 0
            if dp_row_sum:
                sed_prod_1 = dp_row_sum.SumSedProd1
                e_length_dp = dp_row_sum.SumLength / 2  # divide by 2 since it is only half of the road

            sql_select = "SELECT SUM(SedProd2) As SumSedProd2, SUM(Length) As SumLength FROM RoadLines " \
                         "WHERE GRAIPDID2=? GROUP BY GRAIPDID2"
            dp_row_sum = cursor.execute(sql_select, dp_row.GRAIPDID).fetchone()
            sed_prod_2 = 0
            if dp_row_sum:
                sed_prod_2 = dp_row_sum.SumSedProd2

                # combine together effective lengths from both sides of road
                e_length_dp = (dp_row_sum.SumLength / 2) + e_length_dp

            # update DrainPoints table current iterating row
            dp_row.SedProd = sed_prod_1 + sed_prod_2

            dp_row.ELength = e_length_dp
            if dp_row.ELength > 0:
                dp_row.UnitSed = dp_row.SedProd / dp_row.ELength
            else:
                dp_row.UnitSed = 0
                dp_row.SedProd = 0

            stream_con = 0 if dp_row.StreamConnectID == 1 or dp_row.StreamConnectID == 0 else 1
            dp_row.SedDel = stream_con * dp_row.SedProd

            update_sql = "UPDATE DrainPoints SET SedProd=?, ELength=?, UnitSed=?, SedDel=? WHERE GRAIPDID=?"
            data = (dp_row.SedProd, dp_row.ELength, dp_row.UnitSed, dp_row.SedDel, dp_row.GRAIPDID)
            cursor.execute(update_sql, data)

            conn.commit()
        # DEBUG:
        print ("Finished writing sediment production to database (DrainPoints).")
    except:
        raise
    finally:
        # cleanup
        if conn:
            conn.close()


def create_drainpoint_weighted_grid(input_dem, graip_db, dpsi_gridfile, dp_shapefile, is_stream_connected):
    """
    Creates a new grid file with drain point sediment production data

    :param input_dem: Path to dem file
    :param graip_db: Path to graip database file
    :param dpsi_gridfile: Path the output grid file to which sediment data will be writen
    :param dp_shapefile: Path to drainpoint shapefile
    :param is_stream_connected: Flag(True/False) to indicate if sediment data grid file be created for all
    drainpoints or only stream connected points
    :return: None
    """

    # DEBUG:
    print ("Starting to write sediment data to output grid file.")
    try:
        conn = pyodbc.connect(utils.MS_ACCESS_CONNECTION % graip_db)
        cursor = conn.cursor()
        # TODO: May be use the no data value from the input dem
        # (ref: http://www.gdal.org/classGDALRasterBand.html#adcca51d230b5ac848c43f1896293fb50)

        # create a new weighted tif file based on the dem file
        dem = gdal.Open(input_dem)
        geotransform = dem.GetGeoTransform()
        originX = geotransform[0]
        originY = geotransform[3]
        pixelWidth = geotransform[1]
        pixelHeight = geotransform[5]
        rows = dem.RasterYSize
        cols = dem.RasterXSize

        # DEBUG:
        print ("Creating sediment output grid file.")
        driver = gdal.GetDriverByName(utils.GDALFileDriver.TifFile())
        number_of_bands = 1
        outRaster = driver.Create(dpsi_gridfile, cols, rows, number_of_bands, gdal.GDT_Float32)
        outRaster.SetGeoTransform((originX, pixelWidth, 0, originY, 0, pixelHeight))

        # TODO: use the band Fill() method to initialize the raster (ref:http://www.gdal.org/classGDALRasterBand.html#a55bf20527df638dc48bf25e2ff26f353)
        # initialize the newly created tif file with zeros
        grid_initial_data = np.zeros((rows, cols), dtype=np.float32)
        grid_initial_data[:] = 0.0
        outband = outRaster.GetRasterBand(1)
        outband.SetNoDataValue(utils.NO_DATA_VALUE)
        outband.WriteArray(grid_initial_data)
        # DEBUG:
        print ("Empty sediment grid file created.")

        # set the projection of the tif file same as that of the dem
        outRasterSRS = osr.SpatialReference()
        outRasterSRS.ImportFromWkt(dem.GetProjectionRef())
        outRaster.SetProjection(outRasterSRS.ExportToWkt())

        # open the drainpoints shapefile
        driver = ogr.GetDriverByName(utils.GDALFileDriver.ShapeFile())
        dataSource = driver.Open(dp_shapefile, 1)
        layer = dataSource.GetLayer()

        # for each drain point in shape file
        # DEBUG:
        print ("Looping over drain points in shapefile")
        for dp in layer:
            geom = dp.GetGeometryRef()

            # find grid row and col corresponding to drain point
            row, col = utils.get_coordinate_to_grid_row_col(geom.GetX(0), geom.GetY(0), dem)
            geom = None
            # get the id of the drain point from shape file
            graipdid = dp.GetField('GRAIPDID')

            def _write_sed_accum_to_grid():
                # create a 2D array to store sediment production data
                sed_array = np.zeros((1, 1), dtype=np.float32)

                # get current grid cell data
                current_cell_data = outband.ReadAsArray(xoff=col, yoff=row, win_xsize=1, win_ysize=1)
                if current_cell_data[0][0] != utils.NO_DATA_VALUE:
                    sed_array[0][0] = current_cell_data[0][0] + dp_row.SedProd
                else:
                    sed_array[0][0] = dp_row.SedProd

                # here we are writing to a specific cell of the grid
                outband.WriteArray(sed_array, xoff=col, yoff=row)

            # find the drain point matching row from the DrainPoints db table
            dp_row = cursor.execute("SELECT SedProd, StreamConnectID FROM DrainPoints WHERE GRAIPDID=?",
                                    graipdid).fetchone()
            if is_stream_connected:
                if dp_row.StreamConnectID == 2:
                    _write_sed_accum_to_grid()
            else:
                _write_sed_accum_to_grid()

        outband.FlushCache()
        # calculate raster statistics (min, max, mean, stdDev)
        outband.GetStatistics(0, 1)
        # DEBUG:
        print ("Finished writing data to sediment grid file.")

    except:
        raise
    finally:
        if dataSource is not None:
            dataSource.Destroy()

        if conn:
            conn.close()

        dem = None
        outRaster = None

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print ("Road surface erosion computation failed.")
        print (e.message)
        sys.exit(1)