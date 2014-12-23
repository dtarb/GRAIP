__author__ = 'Pabitra'

from osgeo import ogr, gdal, osr
import numpy as np

NO_DATA_VALUE = -9999
MS_ACCESS_CONNECTION = "Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=%s;"

class GDALFileDriver(object):

    @classmethod
    def ShapeFile(cls):
        return "ESRI Shapefile"

    @classmethod
    def TifFile(cls):
        return "GTiff"


def initialize_output_raster_file(base_raster_file, output_raster_file):

    """
    Creates an empty raster file based on the dimension, projection, and cell size of an input raster file

    :param base_raster_file: raster file based on which the new empty raster file to be created
    :param output_raster_file: name and location of of the output raster file to be created
    :return: None
    """
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

    # initialize the newly created tif file with zeros
    grid_initial_data = np.zeros((rows, cols), dtype=np.float32)
    grid_initial_data[:] = 0.0
    outband = outRaster.GetRasterBand(1)
    outband.SetNoDataValue(NO_DATA_VALUE)
    outband.WriteArray(grid_initial_data)

    # set the projection of the tif file same as that of the base_raster file
    outRasterSRS = osr.SpatialReference()
    outRasterSRS.ImportFromWkt(base_raster.GetProjectionRef())
    outRaster.SetProjection(outRasterSRS.ExportToWkt())

    outRaster = None


def get_coordinate_to_grid_row_col(x, y, dem):
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