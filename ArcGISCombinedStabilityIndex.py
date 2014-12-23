__author__ = 'Pabitra'
import arcpy
import os
import subprocess

# get the input parameters
dp_shapefile = arcpy.GetParameterAsText(0)
dp_selected_types = arcpy.GetParameterAsText(1).split(';')
db_file = arcpy.GetParameterAsText(2)
road_width = arcpy.GetParameterAsText(3)
min_terr_recharge = arcpy.GetParameterAsText(4)
max_terr_recharge = arcpy.GetParameterAsText(5)
capl_text_file = arcpy.GetParameterAsText(6)
slp_raster_file = arcpy.GetParameterAsText(7)
sca_raster_file = arcpy.GetParameterAsText(8)
cal_raster_file = arcpy.GetParameterAsText(9)
ang_raster_file = arcpy.GetParameterAsText(10)
si_raster_file = arcpy.GetParameterAsText(11)
sat_raster_file = arcpy.GetParameterAsText(12)

# create the cis_inputs.txt file from the provided above parameters
this_script_dir = os.path.dirname(os.path.realpath(__file__))
#this_script_dir = '"' + this_script_dir + '"'
csi_input_file = os.path.join(this_script_dir, 'csi_inputs.txt')
csi_input_file = r'' + csi_input_file

with open(csi_input_file, 'w') as file_obj:
    file_obj.write('# input parameters for combined stability index computation\n')
    file_obj.write('# input files\n')
    file_obj.write('mdb=' + db_file + '\n')
    file_obj.write('drainpoints=' + dp_shapefile + '\n')
    file_obj.write('slp=' + slp_raster_file + '\n')
    if len(ang_raster_file) > 0:
        file_obj.write('ang=' + ang_raster_file + '\n')
        ang_dir_path = os.path.dirname(os.path.abspath(ang_raster_file))
        scamin_raster_file = os.path.join(ang_dir_path, 'scamin.tif')
        scamax_raster_file = os.path.join(ang_dir_path, 'scamax.tif')
        file_obj.write('scamin=' + scamin_raster_file + '\n')
        file_obj.write('scamax=' + scamax_raster_file + '\n')

    file_obj.write('sca=' + sca_raster_file + '\n')
    file_obj.write('calpar=' + capl_text_file + '\n')
    file_obj.write('cal=' + cal_raster_file + '\n')
    file_obj.write('si=' + si_raster_file + '\n')
    file_obj.write('sat=' + sat_raster_file + '\n')

    # TODO: the road impact settings is probably not needed
    file_obj.write('roadimpact=False\n')

    file_obj.write('# drain point types' + '\n')

    if "'Broad base dip'" in dp_selected_types:
        file_obj.write('broadbasedip=On\n')
    else:
        file_obj.write('broadbasedip=Off\n')

    if "'Diffuse drain'" in dp_selected_types:
        file_obj.write('diffusedrain=On\n')
    else:
        file_obj.write('diffusedrain=Off\n')

    if "'Ditch relief'" in dp_selected_types:
        file_obj.write('ditchrelief=On\n')
    else:
        file_obj.write('ditchrelief=Off\n')

    if "'Lead off'" in dp_selected_types:
        file_obj.write('leadoff=On\n')
    else:
        file_obj.write('leadoff=Off\n')

    if 'Non-engineered' in dp_selected_types:
        file_obj.write('nonengineered=On\n')
    else:
        file_obj.write('nonengineered=Off\n')

    if "'Stream crossing'" in dp_selected_types:
        file_obj.write('streamcrossing=On\n')
    else:
        file_obj.write('streamcrossing=Off\n')

    if 'Sump' in dp_selected_types:
        file_obj.write('sump=On\n')
    else:
        file_obj.write('sump=Off\n')

    if "'Water bar'" in dp_selected_types:
        file_obj.write('waterbar=On\n')
    else:
        file_obj.write('waterbar=Off\n')

    if "'Excavated Stream Crossing'" in dp_selected_types:
        file_obj.write('excavatedstreamcrossing=On\n')
    else:
        file_obj.write('excavatedstreamcrossing=Off\n')

    file_obj.write('roadwidth=' + road_width + '\n')
    file_obj.write('minimumterrainrecharge=' + min_terr_recharge + '\n')
    file_obj.write('maximumterrainrecharge=' + max_terr_recharge + '\n')
    file_obj.write('minimumadditionalroadsurfacerunoff=0.001\n')
    file_obj.write('maximumadditionalroadsurfacerunoff=0.002\n')
    file_obj.write('g=9.81\n')
    file_obj.write('rhow=1000\n')

# put quotes around file paths in case they have spaces
#this_script_dir = '"' + this_script_dir + '"'
csi_input_file = '"' + csi_input_file + '"'
py_script_to_execute = os.path.join(this_script_dir, 'CombinedStabilityIndex.py')
py_script_to_execute = '"' + py_script_to_execute + '"'
cmd = py_script_to_execute + \
      ' --params ' + csi_input_file

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
