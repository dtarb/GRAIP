__author__ = 'Pabitra'

import os
import subprocess

import arcpy

# get the input parameters
stream_network_shapefile = arcpy.GetParameterAsText(0)
desc = arcpy.Describe(stream_network_shapefile)
stream_network_shapefile = str(desc.catalogPath)

contributing_area_raster_file = arcpy.GetParameterAsText(1)
desc = arcpy.Describe(contributing_area_raster_file)
contributing_area_raster_file = str(desc.catalogPath)

sac_raster_file = arcpy.GetParameterAsText(2)
desc = arcpy.Describe(sac_raster_file)
sac_raster_file = str(desc.catalogPath)

is_dinfinity = arcpy.GetParameterAsText(3)
spe_raster_file = arcpy.GetParameterAsText(4)


# construct command to execute
current_script_dir = os.path.dirname(os.path.realpath(__file__))
# put quotes around file paths in case they have spaces
stream_network_shapefile = '"' + stream_network_shapefile + '"'
contributing_area_raster_file = '"' + contributing_area_raster_file + '"'
sac_raster_file = '"' + sac_raster_file + '"'
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

# remove stream network file from map document
stream_network_shapefile = stream_network_shapefile.replace('"', '')
stream_network_shapefile_name = os.path.basename(stream_network_shapefile)
stream_network_shapefile_name_no_ext = stream_network_shapefile_name.split(".")[0]

stream_network_layer = stream_network_shapefile_name_no_ext

# get the current map document
mxd = arcpy.mapping.MapDocument("CURRENT")
df = arcpy.mapping.ListDataFrames(mxd, "Layers")[0]

# show executing command
arcpy.AddMessage('\nEXECUTING COMMAND:\n' + cmd)

# Capture the contents of shell command and print it to the arcgis dialog box
process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
arcpy.AddMessage('\nProcess started:\n')
start_message = "Please wait. It may take a minute or so. Computation is in progress ..."
arcpy.AddMessage(start_message)
streamdata = process.communicate()[0]

messages = streamdata.split("\n")
for msg in messages:
    arcpy.AddMessage(msg)

# if the above subprocess ran successfully
if process.returncode == 0:
    # create a copy of the streamnetwork layer to save its symbology
    # so that we can use this copied layer to apply the symbology to the
    # layer object that will be loading from the updates streamnetwork shape file
    is_stream_network_layer_in_map_doc = False
    stream_network_layer_copy = "streamnet_copy"
    for lyr in arcpy.mapping.ListLayers(mxd, "", df):
        if lyr.name.lower() == stream_network_layer.lower():
            copy_lyr = lyr
            lyr_original_name = lyr.name
            copy_lyr.name = str(stream_network_layer_copy)
            arcpy.mapping.AddLayer(df, copy_lyr, "AUTO_ARRANGE")
            lyr.name = stream_network_layer
            is_stream_network_layer_in_map_doc = True

    # delete the in memory original streamnetwork layer object
    if is_stream_network_layer_in_map_doc:
        arcpy.Delete_management(stream_network_layer)

    # Set overwrite option
    arcpy.env.overwriteOutput = True

    if is_stream_network_layer_in_map_doc:
        # create feature layer from the updated streamnetwork shape file on disk and add it to the map document
        arcpy.MakeFeatureLayer_management(stream_network_shapefile, stream_network_layer)
        addLayer_streamNetwork = arcpy.mapping.Layer(stream_network_layer)

        # apply the symbology from the copied streamnetwork layer object
        # to the newly added streamnetwork layer object

        arcpy.mapping.AddLayer(df, addLayer_streamNetwork, "TOP")
        updateLayer = arcpy.mapping.ListLayers(mxd, stream_network_layer, df)[0]
        sourceLayer = arcpy.mapping.ListLayers(mxd, stream_network_layer_copy, df)[0]
        arcpy.mapping.UpdateLayer(df, updateLayer, sourceLayer, True)

        # delete the copied streamnetwork layer object from memory
        arcpy.Delete_management(stream_network_layer_copy)

        # save the streamnetwork layer object to a layer file on disk
        stream_network_shapefile_dir_path = os.path.dirname(stream_network_shapefile)
        stream_network_layer_file = os.path.join(stream_network_shapefile_dir_path, 'streamnet.lyr')
        arcpy.SaveToLayerFile_management(updateLayer, stream_network_layer_file, "ABSOLUTE")

        # delete the streamnetwork layer object from memory
        arcpy.Delete_management(stream_network_layer)

        # load the streamnetwork layer object from the layer file on disk
        addLayer_streamNetwork = arcpy.mapping.Layer(stream_network_layer_file)
        arcpy.mapping.AddLayer(df, addLayer_streamNetwork, "TOP")

    # refresh the map document Table Of Content and current active view of the document
    arcpy.RefreshTOC()
    arcpy.RefreshActiveView()
    arcpy.AddMessage("Streamnetwork shape file re-loaded")

