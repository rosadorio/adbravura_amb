# Import necessary QGIS and GDAL modules
import os, re
import processing
from qgis.core import QgsRasterLayer, QgsVectorLayer
from qgis.analysis import QgsZonalStatistics
from osgeo import gdal
import numpy as np
import pickle



# Perform NDVI calculation using GDAL
def calculate_ndvi(red_band, nir_band, output_path):
    red_ds = gdal.Open(red_band.source())
    nir_ds = gdal.Open(nir_band.source())

    geo_transform = red_ds.GetGeoTransform()
    proj = red_ds.GetProjection()

    red_band = red_ds.GetRasterBand(1)
    nir_band = nir_ds.GetRasterBand(1)

    red_data = red_band.ReadAsArray()
    nir_data = nir_band.ReadAsArray()

    ndvi_data = (nir_data - red_data) / (nir_data + red_data)

    driver = gdal.GetDriverByName('GTiff')
    ndvi_ds = driver.Create(output_path, red_band.XSize, red_band.YSize, 1, gdal.GDT_Float32)
    ndvi_ds.SetGeoTransform(geo_transform)
    ndvi_ds.SetProjection(proj)

    ndvi_band = ndvi_ds.GetRasterBand(1)
    ndvi_band.WriteArray(ndvi_data)
    ndvi_band.FlushCache()

    del red_ds, nir_ds, red_band, nir_band, ndvi_ds, ndvi_band


def compute_ndvi(date):
    # Ensure that you have matching Red (B04) and NIR (B05) bands for each date to calculate NDVI
    if date in band["nir"]:
        red_band_layer = QgsRasterLayer(band["red"][date], f'Red_{date}')
        nir_band_layer = QgsRasterLayer(band["nir"][date], f'NIR_{date}')

        if red_band_layer.isValid() and nir_band_layer.isValid():
            #display Bands on qgis
            #QgsProject.instance().addMapLayer(red_band_layer)
            #QgsProject.instance().addMapLayer(nir_band_layer)
               
            #compute NDVI
            output_ndvi_path = os.path.join(output_directory, f'{date}_ndvi.tiff')
            calculate_ndvi(red_band_layer, nir_band_layer, output_ndvi_path)
            #display NDVI on qgis
            ndvi_band_layer = QgsRasterLayer(output_ndvi_path, f'{date}_nvdi')
            QgsProject.instance().addMapLayer(ndvi_band_layer)
            
            print(f"NDVI calculated and saved to '{output_ndvi_path}'.")
            
            return output_ndvi_path
            
        else:
            print(f"Error: Layers for date {date} are not valid.")
    else:
        print(f"Error: No matching NIR band for date {date}.")


def filter_index_layer(layer_path, output_directory, threshold, CRS, date):
    if not os.path.isfile(layer_path):
        print(f"Error: NDVI file '{layer_path}' not found.")
        return

    band_layer = QgsRasterLayer(layer_path, f'{date}_ndvi')

    if not band_layer.isValid():
        print(f"Error: NDVI layer is not valid.")
        return

    # Confirm output directory exists
    os.makedirs(output_directory, exist_ok=True)

    # Filter NDVI raster by threshold
    output_filtered_path = os.path.join(output_directory, f'{date}_filtered.tiff')
    

    try:
        # Open the input raster
        input_ds = gdal.Open(layer_path, gdal.GA_ReadOnly)
        if input_ds is None:
            print(f"Error: Failed to open NDVI raster '{layer_path}'.")
            return

        # Get some properties from the input raster
        geo_transform = input_ds.GetGeoTransform()
        proj = input_ds.GetProjection()
        num_cols = input_ds.RasterXSize
        num_rows = input_ds.RasterYSize

        # Create an output raster with 1-band
        driver = gdal.GetDriverByName('GTiff')
        output_ds = driver.Create(output_filtered_path, num_cols, num_rows, 1, gdal.GDT_Float32)
        output_ds.SetGeoTransform(geo_transform)
        output_ds.SetProjection(proj)

        # Read the input band
        input_band = input_ds.GetRasterBand(1)
        input_data = input_band.ReadAsArray()

        # Apply the threshold and create the output data, replacing only values below the threshold with NaN
        output_data = np.where(input_data >= threshold, input_data, np.nan) # remove pixels and keep NDVI value
         
        # Create a binary mask where 1 represents healthy vegetation (NDVI > threshold) and 0 represents other values
        mask = np.where(input_data >= threshold, 1, 0)

        # Create a mask for NaN values in the input data
        nan_mask = np.isnan(input_data)

        # Set NaN values where the input data is NaN
        mask[nan_mask] = -9999 #NaN

        output_band = output_ds.GetRasterBand(1)
        output_band.SetNoDataValue(-9999)
        output_band.WriteArray(output_data)

        # Close the output raster
        output_ds = None

        print(f"Filtered NDVI raster successfully calculated and saved to:", output_filtered_path)
    except Exception as e:
        print("An error occurred while writing the raster:", str(e))


    # Add the filtered raster layer to the QGIS project
    filtered_layer = QgsRasterLayer(output_filtered_path, f'{date}_filtered_layer')
    QgsProject.instance().addMapLayer(filtered_layer)

    if filtered_layer.isValid():
        QgsProject.instance().addMapLayer(filtered_layer)
        print(f"NDVI filtered by threshold and added to the QGIS project for debugging.")
    else:
        print(f"Error: FilteredNDVI layer is not valid.")

    # Save the filtered vector layer to the output directory
    print(f"NDVI filtered by threshold and saved to '{output_filtered_path}'.")

    return filtered_layer

def compute_zonal_statistics(shape_layer, raster_layer, prefix):
    try:        
        # Check if both layers are valid
        if shape_layer.isValid() and raster_layer.isValid():
            fields = shape_layer.fields()
            
            for feature in shape_layer.getFeatures():
                if feature.geometry().isNull():
                    # Process the feature
                    print (feature, "Has null geometry")
                    shape_layer.deleteFeature(feature.id())

            zone_stats = QgsZonalStatistics(
                            shape_layer, 
                            raster_layer,
                            prefix, 
                            1, 
                            QgsZonalStatistics.All)                                             
            status  = zone_stats.calculateStatistics(None)
            
            # Commit the changes
            shape_layer.commitChanges()
            
            shape_layer.dataProvider().forceReload()
            shape_layer.updateFields()
            
            if status != 0:
                print("Error during the computation of zonal statistics.")
                return
           
           # # Get the field names
            # field_names = zone_stats.displayName
            # # Print the field names
            # print("Zonal Statistics Field Names:", field_names)
            # # # Print CRS information
            # print("Shape Layer CRS:", shape_layer.crs().authid())
            # print("Raster Layer CRS:", raster_layer.crs().authid())

            # field_names = [field.name() for field in shape_layer.fields()]
            # print("All field names:", field_names)

            #define output
            basin_statistics = []

            for feature in shape_layer.getFeatures():
                # Print some sample features from the shape layer
                #print("Sample Shape Feature:", feature.attributes())
                basin_id = feature.id()
                attrs = feature.attributes()
                 
                # Convert both lists to lowercase for case-insensitive search
                field_names = [field.name() for field in shape_layer.fields()]
                field_names_lower = [f.lower().strip() for f in field_names]
                prefix_lower = prefix.lower().strip()
                try:
                    pixel_count_idx = field_names_lower.index(prefix_lower + "count")
                    pixel_sum_idx = field_names_lower.index(prefix_lower + "sum")
                    mean_idx = field_names_lower.index(prefix_lower + "mean")
                    
                    pixel_count = attrs[pixel_count_idx] if pixel_count_idx != -1 else None
                    pixel_sum = attrs[pixel_sum_idx] if pixel_sum_idx != -1 else None
                    pixel_mean = attrs[mean_idx] if mean_idx != -1 else None

                except ValueError:
                    print("One of the fields is not found!")                
                
                # Extracting additional fields from the shape layer
                area = feature.geometry().area()
                perimeter = feature.geometry().length()
                centroid = feature.geometry().centroid().asPoint()
            
                # Storing all data in basin_statistics
                basin_statistics.append({
                    "BasinID": basin_id,
                    "PixelCount": pixel_count,
                    "PixelSum": pixel_sum,
                    "PixelMean": pixel_mean,
                    "Area": area,
                    "Perimeter": perimeter,
                    "CentroidX": centroid.x(),
                    "CentroidY": centroid.y()
                })

            #print("basin stats:  ", basin_statistics)
        else:
            print('Invalid vector or raster layer.')
    except Exception as e:
        print('An error occurred during zonal statistics calculation:', str(e))

    return basin_statistics


# Define the mission names and their corresponding patterns
## Mission name :  Mission Regular expression 
mission_patterns = {
#    "Landsat_1-5": r'Landsat_1-5',
#    "Landsat_4-5": r'Landsat_4-5',
#    "Landsat_7": r'Landsat_7',
#    "Landsat_8-9": r'Landsat_8-9',
    "Sentinel-2": r'Sentinel-2'
}

def get_mission(file):
    for mission, pattern in mission_patterns.items():
        if re.search(pattern, file):
            return mission
    return None  # Return None if no mission is found

mission_bands = {
# dictionary between band name and frequency
    "Landsat_1-5": [('B01','green'),('B02','red'),("B03",'nir'),('B04','water_vapour')],
    "Landsat_4-5": [('B01','blue'),('B02','green'),('B03','red'),('B04','nir'),('B05','swir_2'),('B06','thermal_1'),('B06','swir_3')],
    "Landsat_7": [('B01','blue'),('B02','green'),('B03','red'),('B04','nir'),('B05','swir_2'),('B06','thermal_2'),('B07','swir_3'),('B08','panchrom')],
    "Landsat_8-9": [('B01','aerosol'),('B02','blue'),('B03','green'),('B04','red'),('B05','nir'), ('B06','swir_2'),('B07','swir_3'),('B08','panchrom'),('B09','swir_1'),('B07','thermal_1'),('B07','thermal_2')],                    
    "Sentinel-2": [('B01','aerosol'),('B02','blue'),('B03','green'),('B04','red'),('B05','veg_1'),('B06','veg_2'),('B07','veg_3'),('B08_','nir'),('B08a','nnir'),('B09','swir_2'),('B10','swir_3'),('B08','panchrom'),('B09','swir_1'),('B07','thermal_1'),('B07','thermal_2')] 
}

band = {
    "aerosol":{},
    "blue":{},
    "green":{},
    "red":{},
    "veg_1":{},
    "veg_2":{},
    "veg_3":{},
    "nir":{},
    "nnir":{},
    "water_vapour":{},
    "swir_1":{},
    "swir_2":{},
    "swir_3":{},
    "panchrom":{},
    "thermal_1":{},
    "thermal_2":{}
}

## Mission name :  Mission Regular expression 
ndvi_threshold = {
    "Landsat_1-5": 0.18,  #0.12 barren land,  >0.3 Healthy Vegetation
    "Landsat_4-5": 0.5, #0.25 barren land, >0.6 Healthy Vegetation
    "Landsat_7": 0.5,    #0.55,   #0.25 barren land, >0.6 Healthy Vegetation
    "Landsat_8-9": 0.5, #0.25 barren land, >0.6 Healthy Vegetation
    "Sentinel-2": 0.5   #0.25 barren land, >0.6 Healthy Vegetation
}


def duplicate_layer(input_layer_path, new_layer_name, output_directory):
    # Load the layer from the provided path
    input_layer = QgsVectorLayer(input_layer_path, "temp_name_for_loading", "ogr")
    
    # Check if the layer is valid
    if not input_layer.isValid():
        raise ValueError("Failed to load the layer!")
    
    # Clone the layer into a new memory layer
    clone_layer = QgsVectorLayer("Polygon?crs=" + input_layer.crs().authid(), new_layer_name, "memory")
    clone_layer.dataProvider().addAttributes(input_layer.fields())
    clone_layer.updateFields()
    
    for feature in input_layer.getFeatures():
        clone_layer.dataProvider().addFeature(feature)

    # Write the duplicated layer to the output directory
    output_path = os.path.join(output_directory, new_layer_name + ".shp")
    error = QgsVectorFileWriter.writeAsVectorFormat(clone_layer, output_path, "UTF-8", input_layer.crs(), "ESRI Shapefile")

    return output_path

def clone_and_transform_shape(polygonZ_path, date):
    layer_name = os.path.splitext(os.path.basename(polygonZ_path))[0]
    #print(layer_name)
    layers = QgsProject.instance().mapLayersByName(layer_name)
    if layers:
        input_layer = layers[0]
    else:
        raise ValueError("Layer not found!")

    # Load the vector layer
    land_shapes = QgsVectorLayer(polygonZ_path, layer_name, "ogr")
    if not land_shapes.isValid():
        raise ValueError("Failed to load the layer!")


    # Create a new memory layer with the same fields
    output_layer = QgsVectorLayer("Polygon?crs=" + input_layer.crs().authid(), layer_name , "memory")
    output_layer.dataProvider().addAttributes(input_layer.fields())
    output_layer.updateFields()

    # Drop Z value and add features to the 2D layer
    for feature in input_layer.getFeatures():
        new_geom = feature.geometry().constGet().clone()
        new_geom.dropZValue()
        new_feature = QgsFeature()
        new_feature.setGeometry(QgsGeometry(new_geom))
        new_feature.setAttributes(feature.attributes())
        output_layer.dataProvider().addFeature(new_feature)

    # Duplicate shape 
    new_layer_name = f'{date}_'+"clone_"+layer_name
    cloned_shape_path = duplicate_layer(reference_shape_file, new_layer_name, output_directory)

    return new_layer_name,cloned_shape_path

def convert_to_python_types(data):
    if isinstance(data, dict):
        return {k: convert_to_python_types(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_to_python_types(v) for v in data]
    elif isinstance(data, (int, float, str)):
        return data
    else:
        return str(data)

def read_sat_bands_input (input_directory):
    # Iterate through the files in the input directory
    for root, dirs, files in os.walk(input_directory):
        for file in files:
            if file.lower().endswith('.tiff'):  # Assuming data files are in TIFF format
                file_path = os.path.join(root, file)
                mission_name = get_mission(file)
                if mission_name:
                    date = file[:10]  # Extract the first 10 characters as the date
                    print( "Mission name: ", date,f" {mission_name}")
                    for (band_name,band_freq) in mission_bands[mission_name]:
                        if band_name in file:
                            band[band_freq][date] = file_path
                else:
                    print("Warning: couldn't find mission in filename that matches dictionary. Skiping entry")
                                

# Define the input directory where data is sorted by date and band name
input_directory = r'C:\Users\Human\Sync\QGIS\data\Aldeia da Bravura\Remote Sensing\Images\Inputs\Bravura'
output_directory= r'C:\Users\Human\Sync\QGIS\data\Aldeia da Bravura\Remote Sensing\Images\Outputs\Bravura\ndvi'
reference_shape_file=r'C:\Users\Human\Sync\QGIS\data\Aldeia da Bravura\Remote Sensing\Polygons\bravura_bacins_polygon.shp'
#reference_shape_file=r'C:\Users\Human\Sync\QGIS\data\EarthObservation\Polygons\bravura_watershed_polygon.shp'

output_statistics=r'C:\Users\Human\Sync\QGIS\scripts'

#define coordinate system
CRS=QgsCoordinateReferenceSystem("EPSG:4326")

# read input metadata of inputs images
read_sat_bands_input (input_directory)

#output of statistics computed
basin_statistics={}

# Process NDVI
for date,filepath in band["red"].items():

    mission_name = get_mission(filepath)
    threshold = ndvi_threshold[mission_name]  

    # compute nvdi 
    output_ndvi_path = compute_ndvi(date)
    ndvi_layer = QgsRasterLayer(output_ndvi_path, f'{date}_ndvi')    
    
    # filter ndvi index below threshold
    ndvi_filter_layer = filter_index_layer(output_ndvi_path,
                                                output_directory,
                                                threshold,
                                                CRS,
                                                date)


    #clone and convert input shapefile to polygon   
    layer_name,shapes_layer_path = clone_and_transform_shape(reference_shape_file, date)   
    # Load the saved layer from disk to the project
    cloned_layer = QgsVectorLayer(shapes_layer_path, layer_name, "ogr")
    #QgsProject.instance().addMapLayer(cloned_layer)  
    
    basin_statistics[date] = compute_zonal_statistics(cloned_layer,ndvi_filter_layer,'NDVI_')
    
    # Remove layers from the project to release resources
    #QgsProject.instance().removeMapLayer(ndvi_filter_layer.id())

simplified_basin_statistics = convert_to_python_types(basin_statistics)

output_path = os.path.join(output_statistics, 'watershed_statistics.pkl')
with open(output_path, 'wb') as f:
    pickle.dump(simplified_basin_statistics, f)

 
 
 
