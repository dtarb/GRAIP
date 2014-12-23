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
# put quotes around file paths in case they have spaces
#this_script_dir = '"' + this_script_dir + '"'
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
