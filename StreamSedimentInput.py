__author__ = 'Pabitra'

from osgeo import ogr, gdal, osr
from gdalconst import *
import numpy as np
import sys
import click
import os
import time

# TODO: Need to find out how to catch gdal exceptions

gdal.UseExceptions()
NO_DATA_VALUE = -9999

class GDALFileDriver(object):

    @classmethod
    def ShapeFile(cls):
        return "ESRI Shapefile"

    @classmethod
    def TifFile(cls):
        return "GTiff"


@click.command()
#@click.option('--net', default=r"E:\Graip\GRAIPPythonTools\demo\demo_SSI\demnet.shp", type=click.Path(exists=True))
@click.option('--net', default=r"E:\Graip\GRAIPPythonTools\demo\demo_SSI_Dinfinity\demnet.shp", type=click.Path(exists=True))
#@click.option('--dpsi', default=r"E:\Graip\GRAIPPythonTools\demo\demo_SSI_Dinfinity\demdpsi.tif", type=click.Path(exists=False))
@click.option('--sca', default=r"E:\Graip\GRAIPPythonTools\demo\demo_SSI_Dinfinity\demsca.tif", type=click.Path(exists=False))
#@click.option('--dpsi', default=None, type=click.Path(exists=False))
#@click.option('--sca', default=None, type=click.Path(exists=False))
@click.option('--ad8', default=r"E:\Graip\GRAIPPythonTools\demo\demo_SSI\demad8.tif", type=click.Path(exists=True))
#@click.option('--ad8', default=None, type=click.Path(exists=False))
#@click.option('--sac', default=r"E:\Graip\GRAIPPythonTools\demo\demo_SSI\demsac.tif", type=click.Path(exists=True))
@click.option('--sac', default=r"E:\Graip\GRAIPPythonTools\demo\demo_SSI_Dinfinity\demsac.tif", type=click.Path(exists=True))
#@click.option('--spe', default=r"E:\Graip\GRAIPPythonTools\demo\demo_SSI\demspe.tif", type=click.Path(exists=False))
@click.option('--spe', default=r"E:\Graip\GRAIPPythonTools\demo\demo_SSI_Dinfinity\demspe.tif", type=click.Path(exists=False))

def main(net, sca, ad8, sac, spe):
    if not _validate_args(net, sca, ad8, sac, spe):
        sys.exit(1)

    #_initialize_output_raster_file(sac, spe)
    if ad8:
        _compute_specific_sediment(sac, ad8, spe, 'd8')
    else:
        _compute_specific_sediment(sac, sca, spe, 'sca')

    _compute_upstream_sediment(sac, ad8, sca, net)

    _compute_direct_stream_sediment(net)
    print "done"

def _validate_args(net, sca, ad8, sac, spe):
    driver_shp = ogr.GetDriverByName(GDALFileDriver.ShapeFile())
    try:
        dataSource = driver_shp.Open(net, 1)
        if not dataSource:
            print("Not a valid shape file (%s)" % net)
            return False
        else:
            dataSource.Destroy()
    except Exception as e:
        print(e.message)
        return False

    # if not ad8:
    #     print "A value must be provided for parameter 'ad8'."
    #     return False

    # if ad8 and sca:
    #     print "Only one of the parameter options 'ad8' or 'sca' can be used."
    #     return False

    try:

        if sca:
            dataSource = gdal.Open(sca, 1)
            if not dataSource:
                print("Not a valid tif file (%s) provided for the 'sca' parameter." % sca)
                return False
            else:
                dataSource = None

        if ad8:
            dataSource = gdal.Open(ad8, 1)
            if not dataSource:
                print("Not a valid tif file (%s) provided for 'ad8' parameter." % ad8)
                return False
            else:
                dataSource = None

        dataSource = gdal.Open(sac, 1)
        if not dataSource:
            print("Not a valid tif file (%s)" % sac)
            return False
        else:
            dataSource = None
    except Exception as e:
        print(e.message)
        return False

    spe_dir = os.path.dirname(spe)
    if not os.path.exists(spe_dir):
        print ("File path '(%s)' for tif output file does not exist." % spe_dir)
        return False

    return True


def _initialize_output_raster_file(base_raster_file, output_raster_file):
    base_raster = gdal.Open(base_raster_file, 1)
    geotransform = base_raster.GetGeoTransform()
    originX = geotransform[0]
    originY = geotransform[3]
    pixelWidth = geotransform[1]
    pixelHeight = geotransform[5]
    rows = base_raster.RasterYSize
    cols = base_raster.RasterXSize

    driver = gdal.GetDriverByName(GDALFileDriver.TifFile())
    number_of_bands = 1
    outRaster = driver.Create(output_raster_file, cols, rows, number_of_bands, gdal.GDT_Float32)
    outRaster.SetGeoTransform((originX, pixelWidth, 0, originY, 0, pixelHeight))
    # initialize the newly created tif file with no data values
    grid_initial_data = np.zeros((rows, cols), dtype=np.float32)
    grid_initial_data[:] = 0.0
    outband = outRaster.GetRasterBand(1)
    outband.SetNoDataValue(NO_DATA_VALUE)
    outband.WriteArray(grid_initial_data)

    # set the projection of the tif file same as that of the base_raster shape file
    outRasterSRS = osr.SpatialReference()
    outRasterSRS.ImportFromWkt(base_raster.GetProjectionRef())
    outRaster.SetProjection(outRasterSRS.ExportToWkt())

    outRaster = None

def _compute_specific_sediment(sac, ad8, spe):
    # ref to the specificsed() c++ method for the computational logic
    out_raster_spe = gdal.Open(spe, GA_Update)
    raster_sac = gdal.Open(sac)
    raster_ad8 = gdal.Open(ad8)
    out_band_spe = out_raster_spe.GetRasterBand(1)
    band_sac = raster_sac.GetRasterBand(1)
    band_ad8 = raster_ad8.GetRasterBand(1)
    geotransform = raster_ad8.GetGeoTransform()
    ad8_pixel_width = abs(geotransform[1])
    ad8_pixel_height = abs(geotransform[5])

    start = time.time()
    sed_array_spe = np.zeros((band_sac.YSize, band_sac.XSize), dtype=np.float32)
    for row in range(0, band_sac.YSize):
        # get the data for the current row for ad8 and sac
        ad8_current_row_data = band_ad8.ReadAsArray(xoff=0, yoff=row, win_xsize=band_ad8.XSize, win_ysize=1)
        sac_current_row_data = band_sac.ReadAsArray(xoff=0, yoff=row, win_xsize=band_sac.XSize, win_ysize=1)

        for col in range(0, band_sac.XSize):
            #TODO: cleanup the commented code below
            # read the cell data for the current row/col from ad8 - this is causing the processing to be very slow
            #ad8_current_cell_data = band_ad8.ReadAsArray(xoff=col, yoff=row, win_xsize=1, win_ysize=1)
            #sac_current_cell_data = band_sac.ReadAsArray(xoff=col, yoff=row, win_xsize=1, win_ysize=1)
            # create a 2D array to store sediment production data
            #sed_array_spe = np.zeros((1, 1), dtype=np.float32)
            # if ad8_current_cell_data[0][0] != 0:
            #     if ad8_current_cell_data[0][0] != band_ad8.GetNoDataValue():
            #         sed_array_spe[row][col] = (sac_current_cell_data[0][0] / (ad8_current_cell_data[0][0] *
            #                                                              ad8_pixel_width* ad8_pixel_height)) * 1000
            #     else:
            #         sed_array_spe[row][col] = out_band_spe.GetNoDataValue()

            if ad8_current_row_data[0][col] != 0:
                if ad8_current_row_data[0][col] != band_ad8.GetNoDataValue():
                    sed_array_spe[row][col] = (sac_current_row_data[0][col] / (ad8_current_row_data[0][col] *
                                                                              ad8_pixel_width* ad8_pixel_height)) * 1000
                else:
                    sed_array_spe[row][col] = out_band_spe.GetNoDataValue()

                    # here we are writing to a specific cell of the grid
                # out_band_spe.WriteArray(sed_array_spe, xoff=col, yoff=row)
                #print('Writing specific sediment data to cell at %d*%d' % (row, col))
    out_band_spe.WriteArray(sed_array_spe)
    out_band_spe.FlushCache()

    out_raster_spe = None
    raster_sac = None
    raster_ad8 = None
    sed_array_spe = None
    end = time.time()
    print str(end - start)

def _compute_specific_sediment(sac, cont_area, spe, area_type):
    # ref to the specificsed() c++ method for the computational logic
    out_raster_spe = gdal.Open(spe, GA_Update)
    raster_sac = gdal.Open(sac)
    raster_cont_area = gdal.Open(cont_area)
    out_band_spe = out_raster_spe.GetRasterBand(1)
    band_sac = raster_sac.GetRasterBand(1)
    band_cont_area = raster_cont_area.GetRasterBand(1)
    geotransform = raster_cont_area.GetGeoTransform()
    cont_area_pixel_width = abs(geotransform[1])
    cont_area_pixel_height = abs(geotransform[5])

    #Put area in km^2 by dividing by 10^6 and then multiply by 1000 for kg to Mg conversion with this in the denominator
    if area_type == 'd8':
        # in case of d8 each cell area is 1
        PIXEL_TO_AREA_AND_MG_CONVERSION_FACTOR = (cont_area_pixel_height * cont_area_pixel_width) / 1000
    else:
        # in case of sca each cell area is same as the cell size. If cell size is 10 m then cell area is 10
        PIXEL_TO_AREA_AND_MG_CONVERSION_FACTOR = (cont_area_pixel_height * cont_area_pixel_width) / (1000 * cont_area_pixel_height)

    start = time.time()
    sed_array_spe = np.zeros((band_sac.YSize, band_sac.XSize), dtype=np.float32)
    for row in range(0, band_sac.YSize):
        # get the data for the current row for ad8 and sac
        cont_area_current_row_data = band_cont_area.ReadAsArray(xoff=0, yoff=row, win_xsize=band_cont_area.XSize, win_ysize=1)
        sac_current_row_data = band_sac.ReadAsArray(xoff=0, yoff=row, win_xsize=band_sac.XSize, win_ysize=1)

        for col in range(0, band_sac.XSize):
            #TODO: cleanup the commented code below
            # # read the cell data for the current row/col from ad8 - this is causing the processing to be very slow
            # cont_area_current_cell_data = band_cont_area.ReadAsArray(xoff=col, yoff=row, win_xsize=1, win_ysize=1)
            # sac_current_cell_data = band_sac.ReadAsArray(xoff=col, yoff=row, win_xsize=1, win_ysize=1)
            # #create a 2D array to store sediment production data
            # #sed_array_spe = np.zeros((1, 1), dtype=np.float32)
            # if cont_area_current_cell_data[0][0] != 0:
            #     if cont_area_current_cell_data[0][0] != band_cont_area.GetNoDataValue():
            #         sed_array_spe[row][col] = (sac_current_cell_data[0][0] / (cont_area_current_cell_data[0][0] *
            #                                                              cont_area_pixel_width* cont_area_pixel_height)) * 1000
            #     else:
            #         sed_array_spe[row][col] = out_band_spe.GetNoDataValue()

            if cont_area_current_row_data[0][col] != 0:
                if cont_area_current_row_data[0][col] != band_cont_area.GetNoDataValue():
                    if sac_current_row_data[0][col] != band_sac.GetNoDataValue():
                       sed_array_spe[row][col] = sac_current_row_data[0][col] / (cont_area_current_row_data[0][col] *
                                                                                 PIXEL_TO_AREA_AND_MG_CONVERSION_FACTOR)

                    else:
                        sed_array_spe[row][col] = out_band_spe.GetNoDataValue()
                else:
                    sed_array_spe[row][col] = out_band_spe.GetNoDataValue()
                    # here we are writing to a specific cell of the grid
                    # out_band_spe.WriteArray(sed_array_spe, xoff=col, yoff=row)
                    #print('Writing specific sediment data to cell at %d*%d' % (row, col))
    out_band_spe.WriteArray(sed_array_spe)
    out_band_spe.FlushCache()
    # calculate raster statistics (min, max, mean, stdDev)
    out_band_spe.GetStatistics(0, 1)

    out_raster_spe = None
    raster_sac = None
    raster_ad8 = None
    sed_array_spe = None
    end = time.time()
    print str(end - start)

def _compute_upstream_sediment(sac, ad8, net):
    driver = ogr.GetDriverByName(GDALFileDriver.ShapeFile())
    dataSource = driver.Open(net, 1)
    layer = dataSource.GetLayer()
    layerDefn = layer.GetLayerDefn()

    try:
        #delete field "SedAccum" if it exists
        fld_index = layerDefn.GetFieldIndex('SedAccum')
        if fld_index > 0:
            layer.DeleteField(fld_index)

        #delete "SpecSed" if it exists
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
    raster_ad8 = gdal.Open(ad8)
    band_ad8 = raster_ad8.GetRasterBand(1)
    geotransform = raster_ad8.GetGeoTransform()
    ad8_pixel_width = abs(geotransform[1])
    ad8_pixel_height = abs(geotransform[5])

    PIXEL_TO_AREA_AND_MG_CONVERSION_FACTOR = (ad8_pixel_height * ad8_pixel_width) / 1000

    def _cleanup():
        dataSource.Destroy()
        raster_sac = None
        raster_ad8 = None

    for feature in layer:
        try:
            geom = feature.GetGeometryRef()
            total_points = geom.GetPointCount()
            if total_points > 0:
                # calculate range from the elevation of 2 end points of the road segment
                # find grid row and col corresponding to stream network
                row1, col1 = _get_coordinate_to_grid_row_col(geom.GetX(1), geom.GetY(1), raster_sac)
                row2, col2 = _get_coordinate_to_grid_row_col(geom.GetX(total_points - 2), geom.GetY(total_points - 2), raster_sac)
                # read the cell data for the current row/col from ad8
                ad8_current_cell_1_data = band_ad8.ReadAsArray(xoff=col1, yoff=row1, win_xsize=1, win_ysize=1)
                ad8_current_cell_2_data = band_ad8.ReadAsArray(xoff=col2, yoff=row2, win_xsize=1, win_ysize=1)
                if total_points > 2:
                    if ad8_current_cell_1_data[0][0] > ad8_current_cell_2_data[0][0]:   # here area increases going downstream
                        sac_current_cell_1_data = band_sac.ReadAsArray(xoff=col1, yoff=row1, win_xsize=1, win_ysize=1)
                        feature.SetField(fld_index_sed_accum, float(sac_current_cell_1_data[0][0]))
                        feature.SetField(fld_index_spec_sed, float(sac_current_cell_1_data[0][0] /
                                         (ad8_current_cell_1_data[0][0] * PIXEL_TO_AREA_AND_MG_CONVERSION_FACTOR)))

                    elif ad8_current_cell_1_data[0][0] <= ad8_current_cell_2_data[0][0]:
                        sac_current_cell_2_data = band_sac.ReadAsArray(xoff=col2, yoff=row2, win_xsize=1, win_ysize=1)
                        feature.SetField(fld_index_sed_accum, float(sac_current_cell_2_data[0][0]))
                        feature.SetField(fld_index_spec_sed, float(sac_current_cell_2_data[0][0] /
                                         (ad8_current_cell_2_data[0][0] * PIXEL_TO_AREA_AND_MG_CONVERSION_FACTOR)))
                    else:
                        raise "Invalid shape file."
                else:   # If total_points is only 2 the back from far end is the first point so actually pick end point with lowest fad8 not highest
                    if ad8_current_cell_1_data[0][0] > ad8_current_cell_2_data[0][0]:
                        sac_current_cell_2_data = band_sac.ReadAsArray(xoff=col2, yoff=row2, win_xsize=1, win_ysize=1)
                        feature.SetField(fld_index_sed_accum, float(sac_current_cell_2_data[0][0]))
                        feature.SetField(fld_index_spec_sed, float(sac_current_cell_2_data[0][0] /
                                         (ad8_current_cell_2_data[0][0] * PIXEL_TO_AREA_AND_MG_CONVERSION_FACTOR)))

                    elif ad8_current_cell_1_data[0][0] <= ad8_current_cell_2_data[0][0]:
                        sac_current_cell_1_data = band_sac.ReadAsArray(xoff=col1, yoff=row1, win_xsize=1, win_ysize=1)
                        feature.SetField(fld_index_sed_accum, float(sac_current_cell_1_data[0][0]))
                        feature.SetField(fld_index_spec_sed, float(sac_current_cell_1_data[0][0] /
                                         (ad8_current_cell_1_data[0][0] * PIXEL_TO_AREA_AND_MG_CONVERSION_FACTOR)))
                    else:
                        raise "Invalid shape file."

            # rewrite the feature to the layer - this will in fact save the data
            layer.SetFeature(feature)
            geom = None
        except:
            _cleanup()
            raise

    _cleanup()

def _compute_upstream_sediment(sac, ad8, sca, net):
    driver = ogr.GetDriverByName(GDALFileDriver.ShapeFile())
    dataSource = driver.Open(net, 1)
    layer = dataSource.GetLayer()
    layerDefn = layer.GetLayerDefn()

    try:
        #delete field "SedAccum" if it exists
        fld_index = layerDefn.GetFieldIndex('SedAccum')
        if fld_index > 0:
            layer.DeleteField(fld_index)

        #delete "SpecSed" if it exists
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
    raster_ad8 = gdal.Open(ad8)
    band_ad8 = raster_ad8.GetRasterBand(1)
    geotransform = raster_ad8.GetGeoTransform()
    ad8_pixel_width = abs(geotransform[1])
    ad8_pixel_height = abs(geotransform[5])

    if sca:
        raster_sca = gdal.Open(ad8)
        band_sca = raster_sca.GetRasterBand(1)
        sca_pixel_width = abs(geotransform[1])
        sca_pixel_height = abs(geotransform[5])

    #Put area in km^2 by dividing by 10^6 and then multiply by 1000 for kg to Mg conversion with this in the denominator
    if not sca:
        # in case of d8 each cell area is 1
        PIXEL_TO_AREA_AND_MG_CONVERSION_FACTOR = (ad8_pixel_height * ad8_pixel_width) / 1000
    else:
        # in case of sca each cell area is same as the cell size. If cell size is 10 m then cell area is 10
        PIXEL_TO_AREA_AND_MG_CONVERSION_FACTOR = (sca_pixel_height * sca_pixel_width) / (1000 * sca_pixel_height)

    def _cleanup():
        dataSource.Destroy()
        raster_sac = None
        raster_ad8 = None
        raster_sca = None

    # for each stream segment
    for feature in layer:
        try:
            geom = feature.GetGeometryRef()
            total_points = geom.GetPointCount()
            if total_points > 0:
                # find grid (raster_sac) row and col corresponding to stream segment first point
                row1, col1 = _get_coordinate_to_grid_row_col(geom.GetX(1), geom.GetY(1), raster_sac)
                # find grid (raster_sac) row and col corresponding to stream segment last point
                row2, col2 = _get_coordinate_to_grid_row_col(geom.GetX(total_points - 2), geom.GetY(total_points - 2), raster_sac)
                # read the cell data for the current row/col from ad8
                ad8_current_cell_1_data = band_ad8.ReadAsArray(xoff=col1, yoff=row1, win_xsize=1, win_ysize=1)
                ad8_current_cell_2_data = band_ad8.ReadAsArray(xoff=col2, yoff=row2, win_xsize=1, win_ysize=1)
                if sca:
                    # read the cell data for the current row/col from sca
                    sca_current_cell_1_data = band_sca.ReadAsArray(xoff=col1, yoff=row1, win_xsize=1, win_ysize=1)
                    sca_current_cell_2_data = band_sca.ReadAsArray(xoff=col2, yoff=row2, win_xsize=1, win_ysize=1)

                # if cont_area_current_cell_1_data[0][0] != band_cont_area.GetNoDataValue() and \
                #                 cont_area_current_cell_2_data[0][0] != band_cont_area.GetNoDataValue():
                if total_points > 2:
                    if ad8_current_cell_1_data[0][0] > ad8_current_cell_2_data[0][0]:   # here area increases going downstream
                        sac_current_cell_1_data = band_sac.ReadAsArray(xoff=col1, yoff=row1, win_xsize=1, win_ysize=1)
                        if sac_current_cell_1_data[0][0] != band_sac.GetNoDataValue():
                            feature.SetField(fld_index_sed_accum, float(sac_current_cell_1_data[0][0]))
                            if sca:
                                feature.SetField(fld_index_spec_sed, float(sac_current_cell_1_data[0][0] /
                                                                       (sca_current_cell_1_data[0][0] * PIXEL_TO_AREA_AND_MG_CONVERSION_FACTOR)))
                            else:   # ad8
                                feature.SetField(fld_index_spec_sed, float(sac_current_cell_1_data[0][0] /
                                                                           (ad8_current_cell_1_data[0][0] * PIXEL_TO_AREA_AND_MG_CONVERSION_FACTOR)))
                        else:
                            feature.SetField(fld_index_sed_accum, 0.0)
                            feature.SetField(fld_index_spec_sed, 0.0)

                    elif ad8_current_cell_1_data[0][0] <= ad8_current_cell_2_data[0][0]:
                        sac_current_cell_2_data = band_sac.ReadAsArray(xoff=col2, yoff=row2, win_xsize=1, win_ysize=1)
                        if sac_current_cell_2_data[0][0] != band_sac.GetNoDataValue():
                            feature.SetField(fld_index_sed_accum, float(sac_current_cell_2_data[0][0]))
                            if sca:
                                feature.SetField(fld_index_spec_sed, float(sac_current_cell_2_data[0][0] /
                                                                   (sca_current_cell_2_data[0][0] * PIXEL_TO_AREA_AND_MG_CONVERSION_FACTOR)))
                            else:   # ad8
                                feature.SetField(fld_index_spec_sed, float(sac_current_cell_2_data[0][0] /
                                                                           (ad8_current_cell_2_data[0][0] * PIXEL_TO_AREA_AND_MG_CONVERSION_FACTOR)))
                        else:
                            feature.SetField(fld_index_sed_accum, 0.0)
                            feature.SetField(fld_index_spec_sed, 0.0)
                    else:
                        raise "Invalid shape file."
                else:   # If total_points is only 2 the back from far end is the first point so actually pick end point with lowest cont_area not highest
                    if ad8_current_cell_1_data[0][0] > ad8_current_cell_2_data[0][0]:
                        sac_current_cell_2_data = band_sac.ReadAsArray(xoff=col2, yoff=row2, win_xsize=1, win_ysize=1)
                        if sac_current_cell_2_data[0][0] != band_sac.GetNoDataValue():
                            feature.SetField(fld_index_sed_accum, float(sac_current_cell_2_data[0][0]))
                            if sca:
                                feature.SetField(fld_index_spec_sed, float(sac_current_cell_2_data[0][0] /
                                                                   (sca_current_cell_2_data[0][0] * PIXEL_TO_AREA_AND_MG_CONVERSION_FACTOR)))
                            else:   # ad8
                                feature.SetField(fld_index_spec_sed, float(sac_current_cell_2_data[0][0] /
                                                                           (ad8_current_cell_2_data[0][0] * PIXEL_TO_AREA_AND_MG_CONVERSION_FACTOR)))
                        else:
                            feature.SetField(fld_index_sed_accum, 0.0)
                            feature.SetField(fld_index_spec_sed, 0.0)

                    elif ad8_current_cell_1_data[0][0] <= ad8_current_cell_2_data[0][0]:
                        sac_current_cell_1_data = band_sac.ReadAsArray(xoff=col1, yoff=row1, win_xsize=1, win_ysize=1)
                        if sac_current_cell_1_data[0][0] != band_sac.GetNoDataValue():
                            feature.SetField(fld_index_sed_accum, float(sac_current_cell_1_data[0][0]))
                            if sca:
                                feature.SetField(fld_index_spec_sed, float(sac_current_cell_1_data[0][0] /
                                                                   (sca_current_cell_1_data[0][0] * PIXEL_TO_AREA_AND_MG_CONVERSION_FACTOR)))
                            else:   # ad8
                                feature.SetField(fld_index_spec_sed, float(sac_current_cell_1_data[0][0] /
                                                                           (ad8_current_cell_1_data[0][0] * PIXEL_TO_AREA_AND_MG_CONVERSION_FACTOR)))
                        else:
                            feature.SetField(fld_index_sed_accum, 0.0)
                            feature.SetField(fld_index_spec_sed, 0.0)
                    else:
                        raise "Invalid shape file."

            # rewrite the feature to the layer - this will in fact save the data
            layer.SetFeature(feature)
            geom = None
        except:
            _cleanup()
            raise

    _cleanup()

def _compute_direct_stream_sediment(net):
    #ref to seddirstream c++ function for the logic of this function
    driver = ogr.GetDriverByName(GDALFileDriver.ShapeFile())
    dataSource = driver.Open(net, 1)
    layer = dataSource.GetLayer()
    layerDefn = layer.GetLayerDefn()
    # put area in m^2 to km^2 by multiplying 10^6 and then put weight in kg to Mg by dividing 10^3
    KG_PER_SQUARE_METER_TO_MG_PER_SQUARE_KM_FACTOR = 1000

    try:
        #delete field "SedDir" if it exists
        fld_index = layerDefn.GetFieldIndex('SedDir')
        if fld_index > 0:
            layer.DeleteField(fld_index)

        #delete "SpecSedDir" if it exists
        fld_index = layerDefn.GetFieldIndex('SpecSedDir')
        if fld_index > 0:
            layer.DeleteField(fld_index)

        #check the following fields exist
        fld_index_sed_accum = layerDefn.GetFieldIndex('SedAccum')
        fld_index_spec_sed = layerDefn.GetFieldIndex('SpecSed')
        fld_index_link_no = layerDefn.GetFieldIndex('LINKNO')
        fld_index_us_link_no1 = layerDefn.GetFieldIndex('USLINKNO1')
        fld_index_us_link_no2 = layerDefn.GetFieldIndex('USLINKNO2')
        fld_index_cont_area = layerDefn.GetFieldIndex('DS_Cont_Ar')

        if any(index == -1 for index in [fld_index_sed_accum,
               fld_index_spec_sed,
               fld_index_link_no,
               fld_index_us_link_no1,
               fld_index_us_link_no2,
               fld_index_cont_area]):
            raise "Invalid streamnetwork shapefile."

    except:
        pass

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
                link_up2_sed_accum, link_up2_ds_area = _get_upstream_sed_accum_and_area(up2_links[list_index], links, sed_accums, ds_areas)

                sac_dir = link_sed_accum - link_up2_sed_accum
                dir_area = link_ds_area - link_up2_ds_area

            else:
                # get the sedaccum and dsarea for the link
                link_sed_accum = sed_accums[list_index]
                link_ds_area = ds_areas[list_index]

                # get the sedaccum and dsarea for the link upstream 1
                link_up1_sed_accum, link_up1_ds_area = _get_upstream_sed_accum_and_area(up1_links[list_index], links, sed_accums, ds_areas)

                # get the sedaccum and dsarea for the link upstream 2
                link_up2_sed_accum, link_up2_ds_area = _get_upstream_sed_accum_and_area(up2_links[list_index], links, sed_accums, ds_areas)

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
            # rewrite the feature to the layer - this will in fact save the data
            layer.SetFeature(feature)
            list_index += 1
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

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(e.message)
        sys.exit(1)