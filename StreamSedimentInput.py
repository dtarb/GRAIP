__author__ = 'Pabitra'

import os
import sys
import time

from osgeo import ogr, gdal, osr
from gdalconst import *
import numpy as np
import click

import utils


# TODO: Need to find out how to catch gdal exceptions

gdal.UseExceptions()

progress_dots = '.'

@click.command()
### Use the followings for debugging within the PyCharm
#@click.option('--net', default=r"E:\Graip\GRAIPPythonTools\demo\demo_SSI\demnet.shp", type=click.Path(exists=True))
#@click.option('--sca', default=r"E:\Graip\GRAIPPythonTools\demo\demo_SSI\DEM\demsca", type=click.Path(exists=True))
#@click.option('--sca', default=None, type=click.Path(exists=False))
#@click.option('--ad8', default=r"E:\Graip\GRAIPPythonTools\demo\demo_SSI\demad8.tif", type=click.Path(exists=True))
#@click.option('--ad8', default=None, type=click.Path(exists=False))
#@click.option('--sac', default=r"E:\Graip\GRAIPPythonTools\demo\demo_SSI\DEM\demsac", type=click.Path(exists=True))
#@click.option('--spe', default=r"E:\Graip\GRAIPPythonTools\demo\demo_SSI\demspe_from_grid_1.tif", type=click.Path(exists=False))

@click.option('--net', default="demnet.shp", type=click.Path(exists=True))
@click.option('--sca', default=None, type=click.Path(exists=True))
@click.option('--ad8', default=None, type=click.Path(exists=True))
@click.option('--sac', default="demsac.tif", type=click.Path(exists=True))
@click.option('--spe', default="demspe.tif", type=click.Path(exists=False))

def main(net, sca, ad8, sac, spe):

    """
    This script computes stream sediment production and saves data to the stream network shapefile.
    Either 'ad8' or 'sca' parameter needs to be provided. All other parameters are required.

    \b
    :param --net: Path to the stream network shapefile
    :param --sca: Path to the contributing area grid file generated using TauDEM 'Areadinf' function (optional)
    :param --ad8: Path to the contributing area grid file generated using TauDEM 'Aread8' function (optional)
    :param --sac: Path to accumulated upstream sediment load grid file
    :param --spe: Path to specific sediment accumulation grid file
    :return: None
    """
    _validate_args(net, sca, ad8, sac, spe)

    print ("Please wait. It may take a minute or so. Computation is in progress ...")
    _initialize_output_raster_file(sac, spe)

    if sca:
        _compute_specific_sediment(sac, sca, spe, 'sca')
    else:
        _compute_specific_sediment(sac, ad8, spe, 'ad8')

    _compute_upstream_sediment(sac, ad8, sca, net)

    _compute_direct_stream_sediment(net)

    print ("Stream sediment computation finished successfully.")


def _validate_args(net, sca, ad8, sac, spe):
    driver_shp = ogr.GetDriverByName(utils.GDALFileDriver.ShapeFile())
    try:
        dataSource = driver_shp.Open(net, 1)
        if not dataSource:
            raise utils.ValidationException("Not a valid shape file (%s) provided for the '--net' parameter." % net)
        else:
            dataSource.Destroy()
    except Exception as ex:
        raise utils.ValidationException(ex.message)

    try:
        if not ad8 and not sca:
            raise utils.ValidationException("One of the 2 parameters '--ad8' or '--sca' must be specified.")

        if ad8 and sca:
            raise utils.ValidationException("Only one of the 2 parameters '--ad8' or '--sca' needs to be specified.")

        if sca:
            dataSource = gdal.Open(sca, GA_ReadOnly)
            if not dataSource:
                raise utils.ValidationException("File open error. Not a valid file (%s) provided for the '--sca' "
                                                "parameter." % sca)
            else:
                dataSource = None

        if ad8:
            dataSource = gdal.Open(ad8, GA_ReadOnly)
            if not dataSource:
                raise utils.ValidationException("File open error. Not a valid file (%s) provided for '--ad8' "
                                                "parameter." % ad8)
            else:
                dataSource = None

        dataSource = gdal.Open(sac, GA_ReadOnly)
        if not dataSource:
            raise utils.ValidationException("File open error. Not a valid file (%s) provided for '--sac' parameter."
                                            % sac)
        else:
            dataSource = None
    except Exception as ex:
        raise utils.ValidationException(ex.message)

    spe_dir = os.path.dirname(os.path.abspath(spe))
    if not os.path.exists(spe_dir):
        raise utils.ValidationException("File path '(%s)' for output file (parameter '--spe') does not exist."
                                        % spe_dir)


def _initialize_output_raster_file(base_raster_file, output_raster_file):

    """
    Creates an empty raster file based on the dimension, projection, and cell size of an input raster file

    :param base_raster_file: raster file based on which the new empty raster file to be created
    :param output_raster_file: name and location of of the output raster file to be created
    :return: None
    """
    base_raster = gdal.Open(base_raster_file, GA_ReadOnly)
    geotransform = base_raster.GetGeoTransform()
    originX = geotransform[0]
    originY = geotransform[3]
    pixelWidth = geotransform[1]
    pixelHeight = geotransform[5]
    rows = base_raster.RasterYSize
    cols = base_raster.RasterXSize

    driver = gdal.GetDriverByName(utils.GDALFileDriver.TifFile())
    number_of_bands = 1
    outRaster = driver.Create(output_raster_file, cols, rows, number_of_bands, gdal.GDT_Float32)
    outRaster.SetGeoTransform((originX, pixelWidth, 0, originY, 0, pixelHeight))

    # initialize the newly created tif file with zeros
    grid_initial_data = np.zeros((rows, cols), dtype=np.float32)
    grid_initial_data[:] = 0.0
    outband = outRaster.GetRasterBand(1)
    outband.SetNoDataValue(utils.NO_DATA_VALUE)
    outband.WriteArray(grid_initial_data)

    # set the projection of the tif file same as that of the base_raster file
    outRasterSRS = osr.SpatialReference()
    outRasterSRS.ImportFromWkt(base_raster.GetProjectionRef())
    outRaster.SetProjection(outRasterSRS.ExportToWkt())

    outRaster = None


def _compute_specific_sediment(sac, cont_area, spe, area_type):
    # ref to the specificsed() c++ method for the computational logic

    """
    Creates the specific sediment accumulation grid file

    :param sac: Accumulated upstream sediment load grid file
    :param cont_area: contributing area grid file
    :param spe: Specific sediment accumulation grid file
    :param area_type: A flag to indicate whether the contributing area is based on 'ad8' or 'dinfinity'
    :return: None
    """
    out_raster_spe = gdal.Open(spe, GA_Update)
    raster_sac = gdal.Open(sac)
    raster_cont_area = gdal.Open(cont_area)
    out_band_spe = out_raster_spe.GetRasterBand(1)
    band_sac = raster_sac.GetRasterBand(1)
    band_cont_area = raster_cont_area.GetRasterBand(1)
    geotransform = raster_cont_area.GetGeoTransform()
    cont_area_pixel_width = abs(geotransform[1])
    cont_area_pixel_height = abs(geotransform[5])

    # put area in km^2 by dividing by 10^6 and then multiply by 1000 for kg to Mg conversion with this in
    # the denominator
    if area_type == 'ad8':
        # in case of d8 each cell area is 1
        PIXEL_TO_AREA_AND_MG_CONVERSION_FACTOR = (cont_area_pixel_height * cont_area_pixel_width) / 1000
    else:
        # in case of sca (dinfinity) each cell area is same as the cell size. If cell size is 10 m then cell area is 10
        PIXEL_TO_AREA_AND_MG_CONVERSION_FACTOR = (cont_area_pixel_height *
                                                  cont_area_pixel_width) / (1000 * cont_area_pixel_height)

    start = time.time()
    sed_array_spe = np.zeros((band_sac.YSize, band_sac.XSize), dtype=np.float32)
    for row in range(0, band_sac.YSize):
        # get the data for the current row for ad8 and sac
        cont_area_current_row_data = band_cont_area.ReadAsArray(xoff=0, yoff=row, win_xsize=band_cont_area.XSize,
                                                                win_ysize=1)
        sac_current_row_data = band_sac.ReadAsArray(xoff=0, yoff=row, win_xsize=band_sac.XSize, win_ysize=1)

        for col in range(0, band_sac.XSize):
            if cont_area_current_row_data[0][col] != 0:
                if cont_area_current_row_data[0][col] != band_cont_area.GetNoDataValue():
                    if sac_current_row_data[0][col] != band_sac.GetNoDataValue():
                       sed_array_spe[row][col] = sac_current_row_data[0][col] / (cont_area_current_row_data[0][col] *
                                                                                 PIXEL_TO_AREA_AND_MG_CONVERSION_FACTOR)

                    else:
                        sed_array_spe[row][col] = out_band_spe.GetNoDataValue()
                else:
                    sed_array_spe[row][col] = out_band_spe.GetNoDataValue()

    #_show_progress()
    # here we are writing all the data for the grid file. Have tried writing data cell by cell which makes it run
    # very slow
    out_band_spe.WriteArray(sed_array_spe)
    out_band_spe.FlushCache()

    # calculate raster statistics (min, max, mean, stdDev)
    out_band_spe.GetStatistics(0, 1)

    out_raster_spe = None
    raster_sac = None
    raster_cont_area = None
    sed_array_spe = None
    end = time.time()
    #print str(end - start)

def _compute_upstream_sediment(sac, ad8, sca, net):

    """
    Computes sediment accumulation (SedAccum) and specif sediment accumulation (SpecSedAccum) and saves
    these data to the stream network file.
    :param sac: Accumulated upstream sediment load grid file
    :param ad8: ad8 Upstream contributing area grid file
    :param sca: dinfinity Upstream contributing area grid file
    :param net: Stream network shapefile
    :return: None
    """
    driver = ogr.GetDriverByName(utils.GDALFileDriver.ShapeFile())
    dataSource = driver.Open(net, 1)
    layer = dataSource.GetLayer()
    layerDefn = layer.GetLayerDefn()

    try:
        # delete field "SedAccum" if it exists
        fld_index = layerDefn.GetFieldIndex('SedAccum')
        if fld_index > 0:
            layer.DeleteField(fld_index)

        # delete "SpecSed" if it exists
        fld_index = layerDefn.GetFieldIndex('SpecSed')
        if fld_index > 0:
            layer.DeleteField(fld_index)

    except:
        pass

    # add a new field (column) 'SedAccum' to the attribute table
    layer.CreateField(ogr.FieldDefn('SedAccum', ogr.OFTReal))
    fld_index_sed_accum = layerDefn.GetFieldIndex('SedAccum')

    # add a new field (column) 'SpecSed' to the attribute table
    layer.CreateField(ogr.FieldDefn('SpecSed', ogr.OFTReal))
    fld_index_spec_sed = layerDefn.GetFieldIndex('SpecSed')

    raster_sac = gdal.Open(sac)
    band_sac = raster_sac.GetRasterBand(1)
    raster_ad8 = None
    raster_sca = None
    if ad8:
        raster_ad8 = gdal.Open(ad8)
        band_ad8 = raster_ad8.GetRasterBand(1)
        geotransform = raster_ad8.GetGeoTransform()
        ad8_pixel_width = abs(geotransform[1])
        ad8_pixel_height = abs(geotransform[5])
    else:
        raster_sca = gdal.Open(sca)
        band_sca = raster_sca.GetRasterBand(1)
        geotransform = raster_sca.GetGeoTransform()
        sca_pixel_width = abs(geotransform[1])
        sca_pixel_height = abs(geotransform[5])

    # put area in km^2 by dividing by 10^6 and then multiply by 1000 for kg to Mg conversion with this in the denominator
    if ad8:
        # in case of d8 each cell area is 1
        PIXEL_TO_AREA_AND_MG_CONVERSION_FACTOR = (ad8_pixel_height * ad8_pixel_width) / 1000
    else:
        # in case of sca each cell area is same as the cell size. If cell size is 10 m then cell area is 10
        PIXEL_TO_AREA_AND_MG_CONVERSION_FACTOR = (sca_pixel_height * sca_pixel_width) / (1000 * sca_pixel_height)

    def _cleanup():
        dataSource.Destroy()
        global raster_sac
        global raster_ad8
        global raster_sca
        raster_sac = None
        raster_ad8 = None
        raster_sca = None

    # for each stream segment
    for feature in layer:
        try:
            geom = feature.GetGeometryRef()
            total_points = geom.GetPointCount()
            if total_points == 0:
                raise Exception("Invalid stream segment found in stream network shapefile.")
            # Assumption: The stream network created from TauDEM has points ordered from downstream to upstream end
            # in each feature. The following logic works based on this assumption

            if total_points > 1:
                # find grid (raster_sac) row and col corresponding to stream segment first point that is not a
                # segment join point. the first point where the segment is joined to another segment is at
                # geom.GetX(0) and geom.GetY(0)
                row, col = _get_coordinate_to_grid_row_col(geom.GetX(1), geom.GetY(1), raster_sac)
            else:
                row, col = _get_coordinate_to_grid_row_col(geom.GetX(0), geom.GetY(0), raster_sac)

            # read the cell data for the current row/col from ad8
            if ad8:
                contributing_area_grid_current_cell_data = band_ad8.ReadAsArray(xoff=col, yoff=row, win_xsize=1,
                                                                                win_ysize=1)
            else:
                # read the cell data for the current row/col from sca
                contributing_area_grid_current_cell_data = band_sca.ReadAsArray(xoff=col, yoff=row, win_xsize=1,
                                                                                win_ysize=1)

            sac_current_cell_data = band_sac.ReadAsArray(xoff=col, yoff=row, win_xsize=1, win_ysize=1)
            if sac_current_cell_data[0][0] != band_sac.GetNoDataValue():
                feature.SetField(fld_index_sed_accum, float(sac_current_cell_data[0][0]))
                feature.SetField(fld_index_spec_sed, float(sac_current_cell_data[0][0] /
                                                           (contributing_area_grid_current_cell_data[0][0] *
                                                            PIXEL_TO_AREA_AND_MG_CONVERSION_FACTOR)))

            else:
                feature.SetField(fld_index_sed_accum, 0.0)
                feature.SetField(fld_index_spec_sed, 0.0)

            # rewrite the feature to the layer - this will in fact save the data
            layer.SetFeature(feature)
            geom = None
        except:
            _cleanup()
            raise

    _cleanup()


def _compute_direct_stream_sediment(net):
    # ref to seddirstream c++ function for the logic of this function

    """
    Computes 'SedDir" and 'SpecSedDir' and appends these 2 fields to the stream network shapefile

    :param net: stream network shapefile
    :return: None
    """

    driver = ogr.GetDriverByName(utils.GDALFileDriver.ShapeFile())
    dataSource = driver.Open(net, 1)
    layer = dataSource.GetLayer()
    layerDefn = layer.GetLayerDefn()

    # put area in m^2 to km^2 by multiplying 10^6 and then put weight in kg to Mg by dividing 10^3
    KG_PER_SQUARE_METER_TO_MG_PER_SQUARE_KM_FACTOR = 1000

    try:
        # delete field "SedDir" if it exists
        fld_index = layerDefn.GetFieldIndex('SedDir')
        if fld_index > 0:
            layer.DeleteField(fld_index)

        # delete "SpecSedDir" if it exists
        fld_index = layerDefn.GetFieldIndex('SpecSedDir')
        if fld_index > 0:
            layer.DeleteField(fld_index)

        # check the following fields exist
        fld_index_sed_accum = layerDefn.GetFieldIndex('SedAccum')
        fld_index_spec_sed = layerDefn.GetFieldIndex('SpecSed')
        fld_index_link_no = layerDefn.GetFieldIndex('LINKNO')
        fld_index_us_link_no1 = layerDefn.GetFieldIndex('USLINKNO1')
        fld_index_us_link_no2 = layerDefn.GetFieldIndex('USLINKNO2')
        fld_index_cont_area = layerDefn.GetFieldIndex('DSContAr')

        if any(index == -1 for index in [fld_index_sed_accum,
               fld_index_spec_sed,
               fld_index_link_no,
               fld_index_us_link_no1,
               fld_index_us_link_no2,
               fld_index_cont_area]):
            raise Exception("Invalid stream network shapefile.")

    except Exception as ex:
        raise  utils.ValidationException(ex.message)

    # add a new field (column) 'SedDir' to the attribute table
    layer.CreateField(ogr.FieldDefn('SedDir', ogr.OFTReal))
    fld_index_sed_dir = layerDefn.GetFieldIndex('SedDir')

    # add a new field (column) 'SpecSedDir' to the attribute table
    layer.CreateField(ogr.FieldDefn('SpecSedDir', ogr.OFTReal))
    fld_index_spec_sed_dir = layerDefn.GetFieldIndex('SpecSedDir')

    # list objects to store shape file data
    links = []
    up1_links = []
    up2_links = []
    sed_accums = []
    ds_areas = []

    # populate the list objects
    for feature in layer:
        links.append(feature.GetField(fld_index_link_no))
        up1_links.append(feature.GetField(fld_index_us_link_no1) if feature.GetField(fld_index_us_link_no1) > 0 else 0)
        up2_links.append(feature.GetField(fld_index_us_link_no2) if feature.GetField(fld_index_us_link_no2) > 0 else 0)
        sed_accums.append(feature.GetField(fld_index_sed_accum))
        ds_areas.append(feature.GetField(fld_index_cont_area))

    list_index = 0
    sac_dir = 0
    dir_area = 0
    link_sed_accum = 0
    link_ds_area = 0

    layer.ResetReading()
    for feature in layer:

        try:
            def _get_upstream_sed_accum_and_area(link_no, links, sed_accums, ds_areas):
                if link_no == 0:
                    return 0, 0

                for i in range(0, len(links)):
                    if links[i] == link_no:
                        return sed_accums[i], ds_areas[i]

                return 0, 0

            link_sed_accum = 0
            if up1_links[list_index] == 0 and up2_links[list_index] == 0:
                # get the sedaccum and dsarea for the link
                link_sed_accum = sed_accums[list_index]
                sac_dir = link_sed_accum
                dir_area = ds_areas[list_index]

            elif up1_links[list_index] == 0 and up2_links[list_index] > 0:
                # get the sedaccum and dsarea for the link
                link_sed_accum = sed_accums[list_index]
                link_ds_area = ds_areas[list_index]

                # get the sedaccum and dsarea for the link upstream 2
                link_up2_sed_accum, link_up2_ds_area = _get_upstream_sed_accum_and_area(up2_links[list_index],
                                                                                        links, sed_accums, ds_areas)

                sac_dir = link_sed_accum - link_up2_sed_accum
                dir_area = link_ds_area - link_up2_ds_area

            else:
                # get the sedaccum and dsarea for the link
                link_sed_accum = sed_accums[list_index]
                link_ds_area = ds_areas[list_index]

                # get the sedaccum and dsarea for the link upstream 1
                link_up1_sed_accum, link_up1_ds_area = _get_upstream_sed_accum_and_area(up1_links[list_index],
                                                                                        links, sed_accums, ds_areas)

                # get the sedaccum and dsarea for the link upstream 2
                link_up2_sed_accum, link_up2_ds_area = _get_upstream_sed_accum_and_area(up2_links[list_index],
                                                                                        links, sed_accums, ds_areas)

                sac_dir = link_sed_accum - link_up1_sed_accum - link_up2_sed_accum
                dir_area = link_ds_area - link_up1_ds_area - link_up2_ds_area

            # due to rounding any dir sed accum that is too small, set those to zero
            if abs(sac_dir) < link_sed_accum * pow(10, -6):
                sac_dir = 0

            # write dir sed accum to stream network shapefile
            feature.SetField(fld_index_sed_dir, sac_dir)
            specific_sed_accum = (sac_dir / dir_area) * KG_PER_SQUARE_METER_TO_MG_PER_SQUARE_KM_FACTOR

            # write specific dir sed accum to stream network shapefile
            feature.SetField(fld_index_spec_sed_dir, specific_sed_accum)

            # rewrite the feature to the layer - this will in fact save the data to the file
            layer.SetFeature(feature)
            list_index += 1
            #_show_progress()
        except:
            dataSource.Destroy()
            raise

    # close datasource
    dataSource.Destroy()

def _get_coordinate_to_grid_row_col(x, y, dem):
    """
    Finds the row and col of a point on the grid

    :param x: x coordinate of the point
    :param y: y coordinate of the point
    :param dem: gdal file object for the grid
    :return: row, col
    """

    geotransform = dem.GetGeoTransform()
    originX = geotransform[0]
    originY = geotransform[3]
    pixelWidth = geotransform[1]
    pixelHeight = geotransform[5]
    col = int((x - originX)/pixelWidth)
    row = int((y - originY)/pixelHeight)

    return row, col


def _show_progress():
    global progress_dots
    if len(progress_dots) == 20:
        progress_dots = '.'
    else:
        progress_dots += '.'
    sys.stdout.write("\r%s" % progress_dots)
    sys.stdout.flush()

if __name__ == '__main__':
    try:
        main()
        sys.exit(0)
    except Exception as e:
        print("Stream sediment computation failed.")
        print(e.message)
        sys.exit(1)