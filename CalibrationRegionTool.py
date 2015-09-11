__author__ = 'Pabitra'

import os
import sys
from osgeo import ogr, gdal, osr
from gdalconst import *
import click
import arcpy
import utils

gdal.UseExceptions()


@click.command()
### Use the followings for debugging within PyCharm
@click.option('--dem', default=r"E:\Graip\GRAIPPythonTools\demo\demo_Calibration_Region_Tool\demfel.tif", type=click.Path(exists=True))
@click.option('--parreg-in', default=r"E:\Graip\GRAIPPythonTools\demo\demo_Calibration_Region_Tool\parreg.tif", type=click.Path(exists=False))
@click.option('--parreg', default=r"E:\Graip\GRAIPPythonTools\demo\demo_Calibration_Region_Tool\parreg_out.tif", type=click.Path(exists=False))
@click.option('--att', default=r"E:\Graip\GRAIPPythonTools\demo\demo_Calibration_Region_Tool\demcalp.txt", type=click.Path(exists=False))
# @click.option('--shp', default=r"E:\Graip\GRAIPPythonTools\demo\demo_Calibration_Region_Tool\RegionShape.shp", type=click.Path(exists=True))
# @click.option('--shp-att-name', default='ID', type=click.STRING)

# @click.option('--dem', default=None, type=click.Path(exists=True))
# @click.option('--parreg-in', default=None, type=click.Path(exists=True))
# @click.option('--parreg', default=None, type=click.Path(exists=False))
# @click.option('--att', default=None, type=click.Path(exists=False))
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

    if not _validate_args(dem, parreg_in, shp, shp_att_name, parreg, att):
        sys.exit(1)

    _create_parameter_region_grid(dem, shp, shp_att_name, parreg_in, parreg)
    _create_parameter_attribute_table_text_file(parreg, parreg_in, shp, att, att_tmin, att_tmax, att_cmin, att_cmax,
                                                att_phimin, att_phimax, att_soildens)

def _validate_args(dem, parreg_in, shp, shp_att_name, parreg, att):
    try:
        dataSource = gdal.Open(dem, 1)
        if not dataSource:
            print("Not a valid tif file (%s) provided for the '--dem' parameter." % dem)
            return False
        else:
            dataSource = None

        if parreg_in:
            dataSource = gdal.Open(parreg_in, 1)
            if not dataSource:
                print("Not a valid tif file (%s) provided for the '--parreg-in' parameter." % parreg_in)
                return False
            else:
                dataSource = None

        if parreg_in and shp:
            print("Either a value for the parameter '--parreg-in' or '--shp' should be provided. But not both.")
            return False

        if shp:
            driver_shp = ogr.GetDriverByName(utils.GDALFileDriver.ShapeFile())
            dataSource = driver_shp.Open(shp, 1)
            if not dataSource:
                print("Not a valid shape file (%s) provided for the '--shp' parameter." % shp)
                return False
            else:
                if shp_att_name is None:
                    print("Name for the attribute from the shapefile to be used for creating region grid is missing. "
                          "('--shp-att-name' parameter).")
                    return False
                else:
                    # check the provided attribute name is valid for the shapefile
                    layer = dataSource.GetLayer()
                    layer_defn = layer.GetLayerDefn()
                    try:
                        layer_defn.GetFieldIndex(shp_att_name)
                    except:
                        print ("Invalid shapefile. Attribute '%s' is missing." % shp_att_name)
                        dataSource.Destroy()
                        return False
                dataSource.Destroy()

    except Exception as ex:
        print(ex.message)
        return False

    parreg_dir = os.path.dirname(os.path.abspath(parreg))
    if not os.path.exists(parreg_dir):
        print ("File path '(%s)' for tif output file (parameter '--parreg') does not exist." % parreg_dir)
        return False

    att_dir = os.path.dirname(os.path.abspath(att))
    if not os.path.exists(att_dir):
        print ("File path '(%s)' for output parameter attribute table (parameter '--att') does not exist." % att_dir)
        return False

    return True
    #TODO: check the extension of the parreg grid file is 'tif'

def _create_parameter_region_grid(dem, shp, shp_att_name, parreg_in, parreg):
    if os.path.exists(parreg):
            os.remove(parreg)

    if shp is None and parreg_in is None:
        utils.initialize_output_raster_file(dem, parreg, initial_data=1, data_type=gdal.GDT_Int16)
    else:
        # determine cell size from the dem
        base_raster = gdal.Open(dem, 1)
        geotransform = base_raster.GetGeoTransform()
        pixelWidth = geotransform[1]
        if shp:

            # TODO: try if we can use the gdal api to convert shape file to raster instead of arcpy
            # Ref: https://pcjericks.github.io/py-gdalogr-cookbook/raster_layers.html
            # if os.path.exists(parreg):
            #     os.remove(parreg)
            arcpy.PolygonToRaster_conversion(shp, shp_att_name, parreg, "CELL_CENTER", "NONE", str(pixelWidth))
        elif parreg_in:
            arcpy.Resample_management(parreg_in, parreg, str(pixelWidth), "NEAREST")

def _create_parameter_attribute_table_text_file(parreg, parreg_in, shp, att, att_tmin, att_tmax, att_cmin, att_cmax,
                                                att_phimin, att_phimax, att_soildens):

    param_ids = []
    if shp or parreg_in:
        # read the parameter grid file to create a list of unique grid cell values
        # which can then be used to populate the SiID column of the parameter text file
        parreg_raster = gdal.Open(parreg)
        parreg_band = parreg_raster.GetRasterBand(1)
        no_data = parreg_band.GetNoDataValue()

        # TODO: this double loop to go through each grid cell takes for ever
        for row in range(0, parreg_band.YSize):
            for col in range(0, parreg_band.XSize):
                current_cell_data = parreg_band.ReadAsArray(xoff=col, yoff=row, win_xsize=1, win_ysize=1)
                if current_cell_data[0][0] != no_data:
                    if current_cell_data[0][0] not in param_ids:
                        param_ids.append(current_cell_data[0][0])

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
    except Exception as e:
        print "Calibration region computation failed."
        print(e.message)
        sys.exit(1)
