__author__ = 'Pabitra'
import os
import subprocess

import arcpy

# get the input parameters
graip_database_file = arcpy.GetParameterAsText(0)
desc = arcpy.Describe(graip_database_file)
graip_database_file = str(desc.catalogPath)

dp_shapefile = arcpy.GetParameterAsText(1)
desc = arcpy.Describe(dp_shapefile)
dp_shapefile = str(desc.catalogPath)

si_grid_file = arcpy.GetParameterAsText(2)
desc = arcpy.Describe(si_grid_file)
si_grid_file = str(desc.catalogPath)

# construct command to execute
current_script_dir = os.path.dirname(os.path.realpath(__file__))

# put quotes around file paths in case they have spaces
graip_database_file = '"' + graip_database_file + '"'
dp_shapefile = '"' + dp_shapefile + '"'
si_grid_file = '"' + si_grid_file + '"'
py_script_to_execute = os.path.join(current_script_dir, 'AddStabilityIndexToDatabase.py')
py_script_to_execute = '"' + py_script_to_execute + '"'
cmd = py_script_to_execute + \
      ' --mdb ' + graip_database_file + \
      ' --dp ' + dp_shapefile + \
      ' --si ' + si_grid_file

# show executing command
arcpy.AddMessage('\nEXECUTING COMMAND:\n' + cmd)

# Capture the contents of shell command and print it to the arcgis dialog box
process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
arcpy.AddMessage('\nProcess started:\n')
start_message = "Please wait. It may take few seconds. Computation is in progress ..."
arcpy.AddMessage(start_message)
for line in process.stdout.readlines():
    if start_message not in line:
        arcpy.AddMessage(line)

