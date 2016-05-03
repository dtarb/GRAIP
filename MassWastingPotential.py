__author__ = 'Pabitra'

"""
Populates data in graip database drainpoints table. Uses drainpoint shapefile to lookup values
from the provided grids. The slope grid (slpd, required) data is used in populating the Slope and ESI columns.
The stability index (si, optional) grid is used in populating the SI column. The combined stability index
(sic, optional) grid is used in populating the SIR column. The distance to stream (dist, optional) grid is used in
populating the DistToStream column.
"""
import sys
import os
import math

from osgeo import ogr, gdal
import pyodbc
import click
from gdalconst import *
import utils

# TODO: Need to find out how to catch gdal exceptions

gdal.UseExceptions()
@click.command()
### Use the followings for debugging within PyCharm
# @click.option('--mdb', default=r"E:\Graip\GRAIPPythonTools\demo\demo_MWP\test.mdb", type=click.Path(exists=True))
# @click.option('--dp', default=r"E:\Graip\GRAIPPythonTools\demo\demo_MWP\drainpoints.shp", type=click.Path(exists=True))
# @click.option('--slpd', default=r"E:\Graip\GRAIPPythonTools\demo\demo_MWP\demslp.tif", type=click.Path(exists=True))
# @click.option('--si', default=r"E:\Graip\GRAIPPythonTools\demo\demo_MWP\demsi.tif", type=click.Path(exists=True))
# @click.option('--sic', default=r"E:\Graip\GRAIPPythonTools\demo\demo_MWP\demsic.tif", type=click.Path(exists=True))
# @click.option('--dist', default=r"E:\Graip\GRAIPPythonTools\demo\demo_MWP\demdist.tif", type=click.Path(exists=True))

### use the following for production
@click.option('--mdb', default="test.mdb", type=click.Path(exists=True))
@click.option('--dp', default="drainpoints.shp", type=click.Path(exists=True))
@click.option('--slpd', default="demslpd.tif", type=click.Path(exists=True))
@click.option('--si', default=None, type=click.Path(exists=True))
@click.option('--sic', default=None, type=click.Path(exists=True))
@click.option('--dist', default=None, type=click.Path(exists=True))

@click.option('--alpha', default=2, type=click.INT)
def main(mdb, dp, slpd, alpha, si, sic, dist):
    _validate_args(mdb, dp, slpd, si, sic, dist)
    compute_mass_potential(mdb, dp, slpd, alpha, si, sic, dist)

def compute_mass_potential(graip_db, dp_shp, slpd, alpha, si=None, sic=None, dist=None):
    conn = pyodbc.connect(utils.MS_ACCESS_CONNECTION % graip_db)
    cursor = conn.cursor()
    slpd_gdal = gdal.Open(slpd)
    slpd_gdal_band = slpd_gdal.GetRasterBand(1)

    if si:
        si_gdal = gdal.Open(si)
        si_gdal_band = si_gdal.GetRasterBand(1)

    if sic:
        sic_gdal = gdal.Open(sic)
        sic_gdal_band = sic_gdal.GetRasterBand(1)

    if dist:
        dist_gdal = gdal.Open(dist)
        dist_gdal_band = dist_gdal.GetRasterBand(1)

    # open the drainpoints shapefile
    driver = ogr.GetDriverByName(utils.GDALFileDriver.ShapeFile())
    dataSource = driver.Open(dp_shp, 1)
    layer = dataSource.GetLayer()

    try:
        # for each drain point in shape file
        for dp in layer:
            geom = dp.GetGeometryRef()

            # find grid row and col corresponding to drain point
            row, col = utils.get_coordinate_to_grid_row_col(geom.GetX(0), geom.GetY(0), slpd_gdal)
            geom = None
            # get the id of the drain point from shape file
            graipdid = dp.GetField('GRAIPDID')
            # get current grid cell data
            current_cell_slope_data = slpd_gdal_band.ReadAsArray(xoff=col, yoff=row, win_xsize=1, win_ysize=1)
            if si:
                current_cell_si_data = si_gdal_band.ReadAsArray(xoff=col, yoff=row, win_xsize=1, win_ysize=1)

            if sic:
                current_cell_sic_data = sic_gdal_band.ReadAsArray(xoff=col, yoff=row, win_xsize=1, win_ysize=1)

            if dist:
                current_cell_dist_data = dist_gdal_band.ReadAsArray(xoff=col, yoff=row, win_xsize=1, win_ysize=1)

            dp_row = cursor.execute("SELECT * FROM DrainPoints WHERE GRAIPDID=%d" % graipdid).fetchone()
            if dp_row:
                if current_cell_slope_data[0][0] != slpd_gdal_band.GetNoDataValue():
                    dp_row.Slope = float(current_cell_slope_data[0][0])
                    dp_row.ESI = dp_row.ELength * math.pow(dp_row.Slope, alpha)
                else:
                    dp_row.Slope = utils.NO_DATA_VALUE
                    dp_row.ESI = utils.NO_DATA_VALUE

                update_sql = "UPDATE DrainPoints SET Slope=?, ESI=? WHERE GRAIPDID=?"
                data = (dp_row.Slope, dp_row.ESI, dp_row.GRAIPDID)
                cursor.execute(update_sql, data)
                if si:
                    if current_cell_si_data[0][0] != si_gdal_band.GetNoDataValue():
                        dp_row.SI = float(current_cell_si_data[0][0])
                    else:
                        dp_row.SI = utils.NO_DATA_VALUE

                    update_sql = "UPDATE DrainPoints SET SI=? WHERE GRAIPDID=?"
                    data = (dp_row.SI, dp_row.GRAIPDID)
                    cursor.execute(update_sql, data)
                if sic:
                    if current_cell_sic_data[0][0] != sic_gdal_band.GetNoDataValue():
                        dp_row.SIR = float(current_cell_sic_data[0][0])
                    else:
                        dp_row.SIR = utils.NO_DATA_VALUE

                    update_sql = "UPDATE DrainPoints SET SIR=? WHERE GRAIPDID=?"
                    data = (dp_row.SIR, dp_row.GRAIPDID)
                    cursor.execute(update_sql, data)

                if dist:
                    if current_cell_dist_data[0][0] != dist_gdal_band.GetNoDataValue():
                        dp_row.DistToStream = float(current_cell_dist_data[0][0])
                    else:
                        dp_row.DistToStream = utils.NO_DATA_VALUE

                    update_sql = "UPDATE DrainPoints SET DistToStream=? WHERE GRAIPDID=?"
                    data = (dp_row.DistToStream, dp_row.GRAIPDID)
                    cursor.execute(update_sql, data)
        conn.commit()
    except:
        raise
    finally:
        # cleanup
        if conn:
            conn.close()

        if dataSource:
            dataSource.Destroy()

def _validate_args(mdb, dp, slpd, si, sic, dist):
    driver = ogr.GetDriverByName(utils.GDALFileDriver.ShapeFile())
    dataSource = driver.Open(dp, GA_ReadOnly)
    if not dataSource:
        raise utils.ValidationException("Not a valid shape file (%s) provided for parameter --dp." % dp)
    else:
        dataSource.Destroy()

    dataSource = gdal.Open(slpd, GA_ReadOnly)
    if not dataSource:
        raise utils.ValidationException("File open error. Not a valid file (%s) provided for '--slpd' "
                                        "parameter." % slpd)
    else:
        dataSource = None

    if si:
        dataSource = gdal.Open(si, GA_ReadOnly)
        if not dataSource:
            raise utils.ValidationException("File open error. Not a valid file (%s) provided for '--si' "
                                            "parameter." % si)
        else:
            dataSource = None

    if sic:
        dataSource = gdal.Open(sic, GA_ReadOnly)
        if not dataSource:
            raise utils.ValidationException("File open error. Not a valid file (%s) provided for '--sic' "
                                            "parameter." % sic)
        else:
            dataSource = None

    if dist:
        dataSource = gdal.Open(dist, GA_ReadOnly)
        if not dataSource:
            raise utils.ValidationException("File open error. Not a valid file (%s) provided for '--dist' "
                                            "parameter." % dist)
        else:
            dataSource = None

    try:
        if not os.path.dirname(mdb):
            mdb = os.path.join(os.getcwd(), mdb)

        conn = pyodbc.connect(utils.MS_ACCESS_CONNECTION % mdb)
        conn.close()
    except pyodbc.Error as ex:
        raise utils.ValidationException(ex.message)


if __name__ == '__main__':
    try:
        main()
        print ("Mass wasting potential computation successful.")
    except Exception as e:
        print ("Mass wasting potential computation failed.")
        print ">>>>>REASON FOR FAILURE:", sys.exc_info()
        print(e.message)
        sys.exit(1)
