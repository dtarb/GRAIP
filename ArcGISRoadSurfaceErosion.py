__author__ = 'Pabitra'
import arcpy
from arcpy import env
import os
import subprocess


# Set overwrite option
arcpy.env.overwriteOutput = True

# get the input parameters
dp_shapefile = arcpy.GetParameterAsText(0)
rd_shapefile = arcpy.GetParameterAsText(1)
graip_db_file = arcpy.GetParameterAsText(2)
dem_grid_file = arcpy.GetParameterAsText(3)
dpsi_raster_file = arcpy.GetParameterAsText(4)
is_stream_connected = arcpy.GetParameterAsText(5)

# construct command to execute
this_script_dir = os.path.dirname(os.path.realpath(__file__))
# put quotes around file paths in case they have spaces
dp_shapefile = '"' + dp_shapefile + '"'
rd_shapefile = '"' + rd_shapefile + '"'
graip_db_file = '"' + graip_db_file + '"'
dem_grid_file = '"' + dem_grid_file + '"'
dpsi_raster_file = '"' + dpsi_raster_file + '"'
py_script_to_execute = os.path.join(this_script_dir, 'RoadSurfaceErosion.py')
py_script_to_execute = '"' + py_script_to_execute + '"'
cmd = py_script_to_execute + \
      ' --dp ' + dp_shapefile + \
      ' --rd ' + rd_shapefile + \
      ' --mdb ' + graip_db_file + \
      ' --z ' + dem_grid_file + \
      ' --dpsi ' + dpsi_raster_file

if str(is_stream_connected) == 'true':
    cmd += ' --sc '

# Submit command to operating system - don;t use this as it will show the console window
#os.system(cmd)

# show executing command
arcpy.AddMessage('\nEXECUTING COMMAND:\n' + cmd)

# Capture the contents of shell command and print it to the arcgis dialog box
process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
arcpy.AddMessage('\nProcess started:\n')
start_message = "Please wait a few seconds. Computation is in progress ..."
arcpy.AddMessage('\n' + start_message + '\n')
for line in process.stdout.readlines():
    if not start_message in line:
        arcpy.AddMessage(line)

# join roadlines shape file with the roadline graip database table
# Process: Make Feature Layer
rd_shapefile = rd_shapefile.replace('"', '')
dp_shapefile = dp_shapefile.replace('"', '')
roadlines_layer = 'RoadLines'
drainpoints_layer = 'DrainPoints'

# get the current map document
mxd = arcpy.mapping.MapDocument("CURRENT")
df = arcpy.mapping.ListDataFrames(mxd, "Layers")[0]

# remove if the shape file layers currently in the map document
for lyr in arcpy.mapping.ListLayers(mxd, "", df):
    if lyr.name.lower() == roadlines_layer.lower() or lyr.name.lower() == drainpoints_layer.lower() :
        # delete layer object from memory
        arcpy.Delete_management(lyr.name)
        #arcpy.AddMessage("Layer removed")

# create feature layer from the roadlines shape file
arcpy.MakeFeatureLayer_management(rd_shapefile, roadlines_layer)

# create feature layer from the drainpoints shape file
arcpy.MakeFeatureLayer_management(dp_shapefile, drainpoints_layer)

addLayer_roadLines = arcpy.mapping.Layer(roadlines_layer)
addLayer_drainPoints = arcpy.mapping.Layer(drainpoints_layer)

graip_db_file = graip_db_file.replace('"', '')
graip_roadlines_table = os.path.join(graip_db_file, "RoadLines")
graip_drainpoints_table = os.path.join(graip_db_file, "DrainPoints")

# join the roasline layer to the roadlines db table
arcpy.AddJoin_management(roadlines_layer, "GRAIPRID", graip_roadlines_table, "GRAIPRID", "KEEP_ALL")
arcpy.mapping.AddLayer(df, addLayer_roadLines, "TOP")

# join the drainpoints layer to the drainpoints table
arcpy.AddJoin_management(drainpoints_layer, "GRAIPDID", graip_drainpoints_table, "GRAIPDID", "KEEP_ALL")
arcpy.mapping.AddLayer(df, addLayer_drainPoints, "TOP")
arcpy.RefreshActiveView()
arcpy.AddMessage("RoadLine shape file was joined with Roadlines database table")
arcpy.AddMessage("DrainPoints shape file was joined with DrainPoints database table")