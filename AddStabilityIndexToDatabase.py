__author__ = 'Pabitra'

import os
import sys

from osgeo import ogr, gdal
from gdalconst import *
import pyodbc
import click

import utils

@click.command()
### Use the followings for debugging within PyCharm
# @click.option('--mdb', default=r"E:\Graip\GRAIPPythonTools\demo\demo_CSI\test.mdb", type=click.Path(exists=True))
# @click.option('--dp', default=r"E:\Graip\GRAIPPythonTools\demo\demo_CSI\drainpoints.shp", type=click.Path(exists=True))
# @click.option('--si', default=r"E:\Graip\GRAIPPythonTools\demo\demo_CSI\Data\demsi_from_taudem_2.tif", type=click.Path(exists=True))

@click.option('--mdb', default="test.mdb", type=click.Path(exists=True))
@click.option('--dp', default="DrainPoints.shp", type=click.Path(exists=True))
@click.option('--si', default="demsi.tif", type=click.Path(exists=True))
def main(mdb, dp, si):
    _validate_args(mdb, dp, si)
    _sindex_drain_points(mdb, dp, si)

def _validate_args(mdb, dp, si):
    driver = ogr.GetDriverByName(utils.GDALFileDriver.ShapeFile())

    dataSource = driver.Open(dp, GA_ReadOnly)
    if not dataSource:
        raise utils.ValidationException("Not a valid shape file (%s) provided for parameter --dp." % dp)
    else:
        dataSource.Destroy()

    try:
        if not os.path.dirname(mdb):
            mdb = os.path.join(os.getcwd(), mdb)

        conn = pyodbc.connect(utils.MS_ACCESS_CONNECTION % mdb)
        conn.close()
    except pyodbc.Error as ex:
        raise utils.ValidationException(ex.message)

    dataSource = gdal.Open(si, GA_ReadOnly)
    if not dataSource:
        raise utils.ValidationException("File open error. Not a valid file (%s) provided for the '--si' parameter."
                                        % si)

    else:
        dataSource = None


def _sindex_drain_points(mdb, dp, si):
    # for each drain point in the drain points shape file find the cell value in the combined stability index grid file
    # and use that value to populate the corresponding row in the drainpoints table
    driver = ogr.GetDriverByName(utils.GDALFileDriver.ShapeFile())
    dataSource = driver.Open(dp, GA_Update)
    layer = dataSource.GetLayer()
    layerDefn = layer.GetLayerDefn()
    fld_index_graipdid = layerDefn.GetFieldIndex('GRAIPDID')

    si_grid = gdal.Open(si)
    si_band = si_grid.GetRasterBand(1)

    field_to_create = 'SI'
    try:
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
        conn = pyodbc.connect(utils. MS_ACCESS_CONNECTION % mdb)
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
                        dp_row.SI = -9999
                    else:
                       dp_row.SI = float(si_cell_data[0][0])

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
            conn.close()

        if dataSource:
            dataSource.Destroy()

if __name__ == '__main__':
    try:
        main()
        print("Adding of stability index to database was successful.\n")
        sys.exit(0)
    except Exception as e:
        print("Adding of stability index to database failed.\n")
        print(e.message)
        sys.exit(1)