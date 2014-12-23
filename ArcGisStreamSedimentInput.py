__author__ = 'Pabitra'
import arcpy
import os
import subprocess

# get the input parameters
stream_network_shapefile = arcpy.GetParameterAsText(0)
contributing_area_raster_file = arcpy.GetParameterAsText(1)
sac_raster_file = arcpy.GetParameterAsText(2)
is_dinfinity = arcpy.GetParameterAsText(3)
#sca_raster_file = arcpy.GetParameterAsText(3)
spe_raster_file = arcpy.GetParameterAsText(4)


# construct command to execute
current_script_dir = os.path.dirname(os.path.realpath(__file__))
# put quotes around file paths in case they have spaces
#current_script_dir = '"' + current_script_dir + '"'
stream_network_shapefile = '"' + stream_network_shapefile + '"'
contributing_area_raster_file = '"' + contributing_area_raster_file + '"'
sac_raster_file = '"' + sac_raster_file + '"'
#sca_raster_file = '"' + sca_raster_file + '"'
spe_raster_file = '"' + spe_raster_file + '"'
py_script_to_execute = os.path.join(current_script_dir, 'StreamSedimentInput.py')
py_script_to_execute = '"' + py_script_to_execute + '"'
cmd = py_script_to_execute + \
      ' --net ' + stream_network_shapefile + \
      ' --sac ' + sac_raster_file + \
      ' --spe ' + spe_raster_file

if str(is_dinfinity) == 'true':
    cmd += ' --sca ' + contributing_area_raster_file
else:
    cmd += ' --ad8 ' + contributing_area_raster_file

# Submit command to operating system - don't do this as this open a console window
#os.system(cmd)

# show executing command
arcpy.AddMessage('\nEXECUTING COMMAND:\n' + cmd)

# Capture the contents of shell command and print it to the arcgis dialog box
process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
arcpy.AddMessage('\nProcess started:\n')
start_message = "Please wait. It may take a minute or so. Computation is in progress ..."
arcpy.AddMessage(start_message)
for line in process.stdout.readlines():
    if not start_message in line:
        arcpy.AddMessage(line)