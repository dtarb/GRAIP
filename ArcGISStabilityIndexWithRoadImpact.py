__author__ = 'Pabitra'
import arcpy
import os
import subprocess

# get the input parameters
slp_raster_file = arcpy.GetParameterAsText(0)
sca_raster_file = arcpy.GetParameterAsText(1)
ang_raster_file = arcpy.GetParameterAsText(2)
cal_raster_file = arcpy.GetParameterAsText(3)
capl_text_file = arcpy.GetParameterAsText(4)
dp_shapefile = arcpy.GetParameterAsText(5)
db_file = arcpy.GetParameterAsText(6)
dp_selected_types = arcpy.GetParameterAsText(7).split(';')
road_width = arcpy.GetParameterAsText(8)
min_terr_recharge = arcpy.GetParameterAsText(9)
max_terr_recharge = arcpy.GetParameterAsText(10)
min_additional_runoff = arcpy.GetParameterAsText(11)
max_additional_runoff = arcpy.GetParameterAsText(12)
si_raster_file = arcpy.GetParameterAsText(13)
sat_raster_file = arcpy.GetParameterAsText(14)
#min_additional_discharge_raster = arcpy.GetParameterAsText(15)
#max_additional_discharge_raster = arcpy.GetParameterAsText(16)
temp_output_files_directory = arcpy.GetParameterAsText(15)
is_delete_intermediate_output_files = arcpy.GetParameterAsText(16)

# create the cis_inputs.txt file from the provided above parameters
this_script_dir = os.path.dirname(os.path.realpath(__file__))
#this_script_dir = '"' + this_script_dir + '"'
si_control_file = os.path.join(temp_output_files_directory, 'Si_Control.txt')
si_control_file = r'' + si_control_file

with open(si_control_file, 'w') as file_obj:
    file_obj.write('# input parameters for combined stability index computation with road impact\n')
    file_obj.write('# input files\n')
    file_obj.write('slp=' + slp_raster_file + '\n')
    file_obj.write('sca=' + sca_raster_file + '\n')
    file_obj.write('ang=' + ang_raster_file + '\n')
    file_obj.write('cal=' + cal_raster_file + '\n')
    file_obj.write('calpar=' + capl_text_file + '\n')
    file_obj.write('drainpoints=' + dp_shapefile + '\n')
    file_obj.write('mdb=' + db_file + '\n')

    file_obj.write('# output files\n')
    file_obj.write('si=' + si_raster_file + '\n')
    file_obj.write('sat=' + sat_raster_file + '\n')
    #file_obj.write('scamin=' + min_additional_discharge_raster + '\n')
    #file_obj.write('scamax=' + max_additional_discharge_raster + '\n')

    file_obj.write('# drain point types' + '\n')
    #selected_drainpoint_types_value = '[' + ','.join(dp_selected_types) + ']'
    selected_drainpoint_types_value = ','.join(dp_selected_types).replace("'", "")
    file_obj.write('selected_drainpoint_types=' + selected_drainpoint_types_value + '\n')

    file_obj.write('# Additional parameters' + '\n')
    file_obj.write('roadwidth=' + road_width + '\n')
    file_obj.write('minimumterrainrecharge=' + min_terr_recharge + '\n')
    file_obj.write('maximumterrainrecharge=' + max_terr_recharge + '\n')
    file_obj.write('minimumadditionalroadsurfacerunoff=' + min_additional_runoff + '\n')
    file_obj.write('maximumadditionalroadsurfacerunoff=' + max_additional_runoff + '\n')

    file_obj.write('# temporary output file directory\n')
    file_obj.write('temporary_output_files_directory=' + temp_output_files_directory + '\n')
    if str(is_delete_intermediate_output_files) == 'true':
        file_obj.write('is_delete_intermediate_output_files=True\n')
    else:
        file_obj.write('is_delete_intermediate_output_files=False\n')

# put quotes around file paths in case they have spaces
#this_script_dir = '"' + this_script_dir + '"'
si_control_file = '"' + si_control_file + '"'
py_script_to_execute = os.path.join(this_script_dir, 'StabilityIndex.py')
py_script_to_execute = '"' + py_script_to_execute + '"'
cmd = py_script_to_execute + \
      ' --params ' + si_control_file

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