__author__ = 'Pabitra'

import os
import sys
from osgeo import ogr, gdal, osr

from gdalconst import *
import numpy as np
import click
import arcpy
from arcpy import env
import utils

gdal.UseExceptions()

# Check out any necessary licenses
arcpy.CheckOutExtension("spatial")

@click.command()
### Use the followings for debugging within PyCharm
#@click.option('--dem', default=r"E:\Graip\GRAIPPythonTools\demo\demo_Calibration_Region_Tool\demfel", type=click.Path(exists=True))
#@click.option('--parreg-in', default=r"E:\Graip\GRAIPPythonTools\demo\demo_Calibration_Region_Tool\parreg_out_shp_3.tif", type=click.Path(exists=True))
#@click.option('--parreg', default=r"E:\Graip\GRAIPPythonTools\demo\demo_Calibration_Region_Tool\parreg_out_from_esri_demfel_1.tif", type=click.Path(exists=False))
#@click.option('--att', default=r"E:\Graip\GRAIPPythonTools\demo\demo_Calibration_Region_Tool\demcalp_from_esri_demfel_1.txt", type=click.Path(exists=False))
#@click.option('--shp', default=r"E:\Graip\GRAIPPythonTools\demo\demo_Calibration_Region_Tool\RegionShape.shp", type=click.Path(exists=True))
#@click.option('--shp-att-name', default='ID', type=click.STRING)

@click.option('--dem', default=None, type=click.Path(exists=True))
@click.option('--parreg-in', default=None, type=click.Path(exists=True))
@click.option('--parreg', default=None, type=click.Path(exists=False))
@click.option('--att', default=None, type=click.Path(exists=False))
@click.option('--shp', default=None, type=click.Path(exists=True))
@click.option('--shp-att-name', default=None, type=click.STRING)
@click.option('--att-tmin', default=2.708, type=click.FLOAT)
@click.option('--att-tmax', default=2.708, type=click.FLOAT)
@click.option('--att-cmin', default=0.0, type=click.FLOAT)
@click.option('--att-cmax', default=0.25, type=click.FLOAT)
@click.option('--att-phimin', default=30.0, type=click.FLOAT)
@click.option('--att-phimax', default=45.0, type=click.FLOAT)
@click.option('--att-soildens', default=2000.0, type=click.FLOAT)
def main(dem, parreg_in, parreg, shp, shp_att_name, att, att_tmin, att_tmax, att_cmin, att_cmax, att_phimin, att_phimax, att_soildens):
    if shp_att_name:
        shp_att_name = shp_att_name.encode('ascii', 'ignore')

    _validate_args(dem, parreg_in, shp, shp_att_name, parreg, att)
    _create_parameter_region_grid(dem, shp, shp_att_name, parreg_in, parreg)
    _create_parameter_attribute_table_text_file(parreg, parreg_in, shp, att, att_tmin, att_tmax, att_cmin, att_cmax,
                                                att_phimin, att_phimax, att_soildens)

def _validate_args(dem, parreg_in, shp, shp_att_name, parreg, att):
    # TODO: remove all the commented code lines
    try:
        dataSource = gdal.Open(dem, GA_ReadOnly)
        if not dataSource:
            raise utils.ValidationException("File open error. Not a valid file (%s) provided for the '--dem' parameter." % dem)
            # print("Not a valid tif file (%s) provided for the '--dem' parameter." % dem)
            # return False
        else:
            dataSource = None

        if parreg_in:
            dataSource = gdal.Open(parreg_in, 1)
            if not dataSource:
                raise utils.ValidationException("File open error. Not a valid file (%s) provided for the '--parreg-in' parameter."
                                                % parreg_in)
                # print("Not a valid tif file (%s) provided for the '--parreg-in' parameter." % parreg_in)
                # return False
            else:
                # check the provided region grid file has only integer data
                parreg_in_band = dataSource.GetRasterBand(1)
                if parreg_in_band.DataType != gdal.GDT_UInt32 and parreg_in_band.DataType != gdal.GDT_UInt16 and \
                                parreg_in_band.DataType != gdal.GDT_Byte:
                    dataSource = None
                    raise utils.ValidationException("Not a valid file (%s) provided for the '--parreg-in' "
                                                    "parameter. Data type must be integer." % parreg_in)
                    # print("Not a valid tif file (%s) provided for the '--parreg-in' parameter. Data type must be "
                    #       "integer." % parreg_in)
                    # dataSource = None
                    # return False
                else:
                    dataSource = None

        if parreg_in and shp:
            raise utils.ValidationException("Either a value for the parameter '--parreg-in' or '--shp' should be "
                                            "provided. But not both.")
            # print("Either a value for the parameter '--parreg-in' or '--shp' should be provided. But not both.")
            # return False

        if shp:
            driver_shp = ogr.GetDriverByName(utils.GDALFileDriver.ShapeFile())
            dataSource = driver_shp.Open(shp, 1)
            if not dataSource:
                raise  utils.ValidationException("Not a valid shape file (%s) provided for the '--shp' parameter."
                                                 % shp)
                # print("Not a valid shape file (%s) provided for the '--shp' parameter." % shp)
                # return False
            else:
                if shp_att_name is None:
                    raise utils.ValidationException("Name for the attribute from the shapefile to be used for creating "
                                                    "region grid is missing. ('--shp-att-name' parameter).")
                    # print("Name for the attribute from the shapefile to be used for creating region grid is missing. "
                    #       "('--shp-att-name' parameter).")
                    # return False
                else:
                    # Attribute name can't be 'FID" since one of the FID values is always zero
                    # and zero is a no-data value in the grid that we generate from the shape file
                    if shp_att_name == 'FID':
                        raise utils.ValidationException("'FID' is an invalid shape file attribute for calibration "
                                                        "region calculation.")
                        # print ("'FID' is an invalid shape file attribute for calibration region calculation.")
                        # return False

                    # check the provided attribute name is valid for the shapefile
                    layer = dataSource.GetLayer()
                    layer_defn = layer.GetLayerDefn()
                    try:
                        layer_defn.GetFieldIndex(shp_att_name)
                    except:
                        dataSource.Destroy()
                        raise utils.ValidationException("Invalid shapefile. Attribute '%s' is missing." % shp_att_name)
                        # print ("Invalid shapefile. Attribute '%s' is missing." % shp_att_name)
                        # dataSource.Destroy()
                        # return False
                dataSource.Destroy()

    except Exception as ex:
        raise ex
        # print(ex.message)
        # return False

    parreg_dir = os.path.dirname(os.path.abspath(parreg))
    if not os.path.exists(parreg_dir):
        raise utils.ValidationException("File path '(%s)' for tif output file (parameter '--parreg') does not exist."
                                        % parreg_dir)
        # print ("File path '(%s)' for tif output file (parameter '--parreg') does not exist." % parreg_dir)
        # return False

    att_dir = os.path.dirname(os.path.abspath(att))
    if not os.path.exists(att_dir):
        raise utils.ValidationException("File path '(%s)' for output parameter attribute table (parameter '--att') "
                                        "does not exist." % att_dir)
        # print ("File path '(%s)' for output parameter attribute table (parameter '--att') does not exist." % att_dir)
        # return False

    # return True
    #TODO: check the extension of the parreg grid file is 'tif'

def _create_parameter_region_grid(dem, shp, shp_att_name, parreg_in, parreg):
    if os.path.exists(parreg):
            os.remove(parreg)

    if shp is None and parreg_in is None:
        utils.initialize_output_raster_file(dem, parreg, initial_data=1, data_type=gdal.GDT_UInt32)
    else:
        # determine cell size from the dem
        base_raster_file_obj = gdal.Open(dem, GA_ReadOnly)
        geotransform = base_raster_file_obj.GetGeoTransform()
        pixelWidth = geotransform[1]

        if shp:

            # This environment settings needed  for the arcpy.PlogonToRaster_conversion function
            #env.extent = dem
            #env.snapRaster = dem
            #print (">>> setting the environment for polygon to raster conversion")
            # TODO: try if we can use the gdal api to convert shape file to raster instead of arcpy
            # Ref: https://pcjericks.github.io/py-gdalogr-cookbook/raster_layers.html
            #utils.initialize_output_raster_file(dem, parreg, initial_data=1, data_type=gdal.GDT_Int32)
            #target_ds = gdal.Open(parreg)

            # For some reason the gdal RasterizeLayer function works with a in memory output raster dataset only
            target_ds = _create_in_memory_raster(dem, data_type=gdal.GDT_UInt32)
            source_ds = ogr.Open(shp)
            source_layer = source_ds.GetLayer()
            # Rasterize
            err = gdal.RasterizeLayer(target_ds, [1], source_layer, options=["ATTRIBUTE=%s" % shp_att_name])
            if err != 0:
                raise Exception(err)
            else:
                # save the in memory output raster to the disk
                gdal.GetDriverByName(utils.GDALFileDriver.TifFile()).CreateCopy(parreg, target_ds)

            target_ds = None
            source_ds = None

            # arcpy.PolygonToRaster_conversion(shp, shp_att_name, temp_shp_raster, "CELL_CENTER", "NONE", str(pixelWidth))
            #arcpy.ResetEnvironments()

        elif parreg_in:
            # TODO: This one only gets the grid cell size to the size in dem file
            # but it doesn't get the output grid size (rows and cols) same as the dem
            temp_parreg = os.path.join(os.path.dirname(dem), 'temp_parreg.tif')
            if os.path.exists(temp_parreg):
                arcpy.Delete_management(temp_parreg)
                #os.remove(temp_parreg)
            target_ds = _create_in_memory_raster(dem, data_type=gdal.GDT_UInt32)
            #utils.initialize_output_raster_file(dem, parreg, initial_data=utils.NO_DATA_VALUE, data_type=gdal.GDT_UInt32)
            #arcpy.Resample_management(parreg_in, parreg, str(pixelWidth), "NEAREST")
            arcpy.Resample_management(parreg_in, temp_parreg, str(pixelWidth), "NEAREST")
            # save the in memory output raster to the disk
            source_ds = gdal.Open(temp_parreg, GA_ReadOnly)
            gdal.ReprojectImage(source_ds, target_ds, None, None, gdal.GRA_NearestNeighbour)
            source_ds = None
            gdal.GetDriverByName(utils.GDALFileDriver.TifFile()).CreateCopy(parreg, target_ds)
            arcpy.Delete_management(temp_parreg)


def _create_in_memory_raster(base_raster, data_type):
    # TODO: document this method

    base_raster = gdal.Open(base_raster, GA_ReadOnly)
    geotransform = base_raster.GetGeoTransform()
    originX = geotransform[0]
    originY = geotransform[3]
    pixelWidth = geotransform[1]
    pixelHeight = geotransform[5]
    rows = base_raster.RasterYSize
    cols = base_raster.RasterXSize

    driver = gdal.GetDriverByName('MEM')
    number_of_bands = 1
    outRaster = driver.Create('', cols, rows, number_of_bands, data_type)
    outRaster.SetGeoTransform((originX, pixelWidth, 0, originY, 0, pixelHeight))

    outband = outRaster.GetRasterBand(1)
    outband.SetNoDataValue(0)

    # set the projection of the tif file same as that of the base_raster file
    outRasterSRS = osr.SpatialReference()
    outRasterSRS.ImportFromWkt(base_raster.GetProjectionRef())
    outRaster.SetProjection(outRasterSRS.ExportToWkt())
    return outRaster

def _create_parameter_attribute_table_text_file(parreg, parreg_in, shp, att, att_tmin, att_tmax, att_cmin, att_cmax,
                                                att_phimin, att_phimax, att_soildens):

    param_ids = []
    if shp or parreg_in:
        # read the parameter grid file to create a list of unique grid cell values
        # which can then be used to populate the SiID column of the parameter text file
        parreg_raster = gdal.Open(parreg)
        parreg_band = parreg_raster.GetRasterBand(1)
        no_data = parreg_band.GetNoDataValue()

        for row in range(0, parreg_band.YSize):
            current_row_data_array = parreg_band.ReadAsArray(xoff=0, yoff=row, win_xsize=parreg_band.XSize, win_ysize=1)
            # get a list of unique data values in the current row
            current_row_unique_data = set(current_row_data_array[0])
            for data in current_row_unique_data:
                if data != no_data:
                    if data not in param_ids:
                        param_ids.append(data)

        param_ids.sort()
    else:
        param_ids.append(1)

    with open(att, 'w') as file_obj:
        file_obj.write('SiID,tmin,tmax,cmin,cmax,phimin,phimax,SoilDens\n')
        for id in param_ids:
            file_obj.write(str(id) + ',' + str(att_tmin) + ',' + str(att_tmax) + ',' + str(att_cmin) + ',' +
                           str(att_cmax) + ',' + str(att_phimin) + ',' + str(att_phimax) + ',' +
                           str(att_soildens) + '\n')


if __name__ == '__main__':
    try:
        main()
        print("Calibration region computation is successful.")
    except Exception as e:
        print "Calibration region computation failed."
        print(e.message)
        sys.exit(1)
