__author__ = 'Pabitra'
import arcpy
import os
import subprocess

# get the input parameters
dp_shapefile = arcpy.GetParameterAsText(0)
rd_shapefile = arcpy.GetParameterAsText(1)
graip_db_file = arcpy.GetParameterAsText(2)
dem_grid_file = arcpy.GetParameterAsText(3)
dpsi_raster_file = arcpy.GetParameterAsText(4)
is_stream_connected = arcpy.GetParameterAsText(5)

# construct command to execute
this_script_dir = os.path.dirname(os.path.realpath(__file__))
py_script_to_execute = os.path.join(this_script_dir, 'RoadSurfaceErosion.py')
cmd = py_script_to_execute + \
      ' --dp ' + dp_shapefile + \
      ' --rd ' + rd_shapefile + \
      ' --mdb ' + graip_db_file + \
      ' --z ' + dem_grid_file + \
      ' --dpsi ' + dpsi_raster_file + \
      ' --sc ' + is_stream_connected

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
