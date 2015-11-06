__author__ = 'Pabitra'

import os
import subprocess

import arcpy

# get the input parameters
graip_database_file = arcpy.GetParameterAsText(0)
desc = arcpy.Describe(graip_database_file)
graip_database_file = str(desc.catalogPath)

drainpoint_shp_file = arcpy.GetParameterAsText(1)
desc = arcpy.Describe(drainpoint_shp_file)
drainpoint_shp_file = str(desc.catalogPath)

slp_raster_file = arcpy.GetParameterAsText(2)
desc = arcpy.Describe(slp_raster_file)
slp_raster_file = str(desc.catalogPath)
alpha_value = arcpy.GetParameterAsText(3)

# optional inputs
si_raster_file = arcpy.GetParameterAsText(4)
if arcpy.Exists(si_raster_file):
    desc = arcpy.Describe(si_raster_file)
    si_raster_file = str(desc.catalogPath)

sic_raster_file = arcpy.GetParameterAsText(5)
if arcpy.Exists(sic_raster_file):
    desc = arcpy.Describe(sic_raster_file)
    sic_raster_file = str(desc.catalogPath)

stream_dist_raster_file = arcpy.GetParameterAsText(6)
if arcpy.Exists(stream_dist_raster_file):
    desc = arcpy.Describe(stream_dist_raster_file)
    stream_dist_raster_file = str(desc.catalogPath)

# construct command to execute
current_script_dir = os.path.dirname(os.path.realpath(__file__))
# put quotes around file paths in case they have spaces
graip_database_file = '"' + graip_database_file + '"'
drainpoint_shp_file = '"' + drainpoint_shp_file + '"'
slp_raster_file = '"' + slp_raster_file + '"'
if len(si_raster_file) > 0:
    si_raster_file = '"' + si_raster_file + '"'

if len(sic_raster_file) > 0:
    sic_raster_file = '"' + sic_raster_file + '"'

if len(stream_dist_raster_file) > 0:
    stream_dist_raster_file = '"' + stream_dist_raster_file + '"'

py_script_to_execute = os.path.join(current_script_dir, 'MassWastingPotential.py')
py_script_to_execute = '"' + py_script_to_execute + '"'
cmd = py_script_to_execute + \
      ' --mdb ' + graip_database_file + \
      ' --dp ' + drainpoint_shp_file + \
      ' --slpd ' + slp_raster_file + \
      ' --alpha ' + alpha_value

if len(si_raster_file) > 0:
    cmd += ' --si ' + si_raster_file

if len(sic_raster_file) > 0:
    cmd += ' --sic ' + sic_raster_file

if len(stream_dist_raster_file) > 0:
    cmd += ' --dist ' + stream_dist_raster_file

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