import streamlit as st
import ee
from ee import oauth
from google.oauth2 import service_account
import folium
from folium import WmsTileLayer
from streamlit_folium import folium_static
from datetime import datetime, timedelta
import json
import requests
import streamlit.components.v1 as components

def initialize_earth_engine():
    try:
        if 'earth_engine' in st.secrets:
            service_account_info = json.loads(st.secrets["earth_engine"]["service_account"])
            credentials = service_account.Credentials.from_service_account_info(
                service_account_info,
                scopes=ee.oauth.SCOPES
            )
            ee.Initialize(credentials)
            st.success("Earth Engine initialized successfully!")
        else:
            ee.Initialize(project='ndvi-441403')
    except Exception as e:
        st.error(f"Earth Engine initialization failed: {str(e)}")
        st.stop()

# Initialize the app
initialize_earth_engine()
st.set_page_config(
    page_title="Vegalytics",
    page_icon="https://cdn-icons-png.flaticon.com/512/2516/2516640.png",
    layout="wide"
)

st.markdown(
"""
<style>
    /* Your CSS styles here */
    .navbar {
        overflow: hidden;
        background-color: #333;
        position: fixed;
        width: 100%;
        top: 0;
        z-index: 1000;
    }
    .navbar a {
        float: left;
        display: block;
        color: #f2f2f2;
        text-align: center;
        padding: 14px 16px;
        text-decoration: none;
        font-size: 17px;
    }
    .navbar a:hover {
        background-color: #ddd;
        color: black;
    }
    iframe { width: 100%; }
</style>
""", unsafe_allow_html=True)

@st.cache_data(persist=True)
def ee_authenticate():
    if "json_key" in st.secrets:
        json_creds = st.secrets["json_key"]
        service_account_info = json.loads(json_creds)
        if "client_email" not in service_account_info:
            raise ValueError("Service account email address missing in json key")
        creds = service_account.Credentials.from_service_account_info(service_account_info, scopes=oauth.SCOPES)
        ee.Initialize(creds)
    else:
        ee.Initialize(project='ndvi-441403')

def add_ee_layer(self, ee_image_object, vis_params, name):
    try:
        map_id_dict = ee.Image(ee_image_object).getMapId(vis_params)
        # map_id_dict = ee.Image(ee_image_object).getMapId(vis_params)
        layer = folium.raster_layers.TileLayer(
            tiles=map_id_dict['tile_fetcher'].url_format,
            attr='Map Data &copy; <a href="https://earthengine.google.com/">Google Earth Engine</a>',
            name=name,
            overlay=True,
            control=True
        )
        layer.add_to(self)
        return layer
    except Exception as e:
        print(f"Error adding Earth Engine layer: {e}")
        None
folium.Map.add_ee_layer = add_ee_layer

# # NDVI Classification function - used for both detailed and binary classification
# def classify_ndvi(masked_image):
#     # Make sure we're only working with valid pixels
#     valid_pixels = masked_image.mask()

#     ndvi_classified = ee.Image(0) \
#         .where(masked_image.gte(0).And(masked_image.lt(0.15)), 1) \
#         .where(masked_image.gte(0.15).And(masked_image.lt(0.25)), 2) \
#         .where(masked_image.gte(0.25).And(masked_image.lt(0.35)), 3) \
#         .where(masked_image.gte(0.35).And(masked_image.lt(0.45)), 4) \
#         .where(masked_image.gte(0.45).And(masked_image.lt(0.65)), 5) \
#         .where(masked_image.gte(0.65).And(masked_image.lt(0.75)), 6) \
#         .where(masked_image.gte(0.75), 7) \
#         .updateMask(valid_pixels)

#     return ndvi_classified

def classify_ndvi(masked_image):
    # Get the original valid pixel mask
    valid_pixels = masked_image.mask()

    ndvi_classified = ee.Image(0) \
        .where(masked_image.gte(0).And(masked_image.lt(0.15)), 1) \
        .where(masked_image.gte(0.15).And(masked_image.lt(0.25)), 2) \
        .where(masked_image.gte(0.25).And(masked_image.lt(0.35)), 3) \
        .where(masked_image.gte(0.35).And(masked_image.lt(0.45)), 4) \
        .where(masked_image.gte(0.45).And(masked_image.lt(0.65)), 5) \
        .where(masked_image.gte(0.65).And(masked_image.lt(0.75)), 6) \
        .where(masked_image.gte(0.75), 7) \
        .updateMask(valid_pixels)

    return ndvi_classified


# Create binary vegetation/non-vegetation classification using the same thresholds
# def classify_vegetation_ndvi(masked_image):
#     # Classes 1-2 (< 0.25) are non-vegetation, classes 3-7 (>= 0.25) are vegetation
#     vegetation_mask = masked_image.gte(0.25)
#     non_vegetation_mask = masked_image.lt(0.25)
#     vegetation_masked = masked_image.updateMask(vegetation_mask)
#     non_vegetation_masked = masked_image.updateMask(non_vegetation_mask)
#     return vegetation_masked, non_vegetation_masked
# def classify_vegetation_ndvi(masked_image):
#     # Classes 1-2 (< 0.25) are non-vegetation, classes 3-7 (>= 0.25) are vegetation
#     vegetation_mask = masked_image.gte(0.25)
#     non_vegetation_mask = masked_image.lt(0.25).And(masked_image.gte(0))

#     # Return binary masks (1 where condition is true, 0 elsewhere) instead of masked NDVI values
#     vegetation_binary = vegetation_mask.selfMask()
#     non_vegetation_binary = non_vegetation_mask.selfMask()

#     return vegetation_binary, non_vegetation_binary

def classify_vegetation_ndvi(masked_image):
    # Use the same exact thresholds as classify_ndvi function
    # Non-vegetation: classes 1-2 (0 <= NDVI < 0.25)
    # Vegetation: classes 3-7 (NDVI >= 0.25)

    # Create mutually exclusive conditions
    vegetation_condition = masked_image.gte(0.25)
    non_vegetation_condition = masked_image.gte(0).And(masked_image.lt(0.25))

    # Apply the same mask from the original image to ensure consistency
    original_mask = masked_image.mask()

    vegetation_binary = vegetation_condition.And(original_mask).selfMask()
    non_vegetation_binary = non_vegetation_condition.And(original_mask).selfMask()

    return vegetation_binary, non_vegetation_binary

# def getLAI(image):
#     lai = image.expression(
#         '3.618 * EVI - 0.118', {
#             'EVI': image.expression(
#                 '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))', {
#                     'NIR': image.select('B8'),
#                     'RED': image.select('B4'),
#                     'BLUE': image.select('B2')
#                 })
#         }).rename('LAI')
#     return lai

# Function to safely compute Leaf Area Index (LAI)
def getLAI(image):
    """
    Compute Leaf Area Index (LAI) only if the image contains all required bands ('B8', 'B4', 'B2').
    If any band is missing, the original image is returned unchanged.
    """
    # Define the LAI computation as a nested function
    def calculate_lai():
        # Enhanced Vegetation Index calculation
        evi = image.expression(
            '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))', {
                'NIR': image.select('B8'),
                'RED': image.select('B4'),
                'BLUE': image.select('B2')
            }
        )
        # LAI formula
        return image.expression(
            '3.618 * EVI - 0.118', {'EVI': evi}
        ).rename('LAI')

    # Fallback: return original image
    fallback = image

    # Nested server-side conditions to check each band
    return ee.Image(
        ee.Algorithms.If(
            image.bandNames().contains('B8'),
            ee.Algorithms.If(
                image.bandNames().contains('B4'),
                ee.Algorithms.If(
                    image.bandNames().contains('B2'),
                    calculate_lai(),
                    fallback
                ),
                fallback
            ),
            fallback
        )
    )

# def calculate_area(masked_image, aoi, label="Area"):
#     pixel_area = ee.Image.pixelArea()
#     area_image = masked_image.multiply(pixel_area)
#     area_stats = area_image.reduceRegion(
#         reducer=ee.Reducer.sum(),
#         geometry=aoi,
#         scale=10,
#         maxPixels=1e9
#     )
#     try:
#       area_result = area_stats.getInfo()
#       if area_result:
#           return next(iter(area_result.values()))
#       else:
#           return None
#     except Exception as e:
#         print(f"Error calculating area: {e}")
#         return None

def calculate_area(binary_mask, aoi, label="Area"):
    # For binary masks, multiply by pixel area directly
    pixel_area = ee.Image.pixelArea()
    area_image = binary_mask.multiply(pixel_area)

    area_stats = area_image.reduceRegion(
        reducer=ee.Reducer.sum(),
        geometry=aoi,
        scale=10,
        maxPixels=1e9
    )

    try:
        area_result = area_stats.getInfo()
        if area_result:
            # Get the first (and should be only) value from the result
            area_value = next(iter(area_result.values()))
            return area_value if area_value is not None else 0
        else:
            return 0
    except Exception as e:
        print(f"Error calculating area for {label}: {e}")
        return 0


def calculate_ndvi_class_areas(ndvi_classified, geometry_aoi):
    areas = {}
    for class_value in range(1, 8):  # Classes 1-7 as per your classification
        class_mask = ndvi_classified.eq(class_value)
        class_area = calculate_area(class_mask, geometry_aoi, f"NDVI Class {class_value}")
        areas[class_value] = class_area or 0
    return areas

def satCollection(cloudRate, initialDate, updatedDate, aoi):
    collection = ee.ImageCollection('COPERNICUS/S2_SR') \
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", cloudRate)) \
        .filterDate(initialDate, updatedDate) \
        .filterBounds(aoi)
    def clipCollection(image):
        return image.clip(aoi).divide(10000)
    collection = collection.map(clipCollection)
    return collection

last_uploaded_centroid = None
def upload_files_proc(upload_files):
    global last_uploaded_centroid
    geometry_aoi_list = []
    for upload_file in upload_files:
        bytes_data = upload_file.read()
        geojson_data = json.loads(bytes_data)
        if 'features' in geojson_data and isinstance(geojson_data['features'], list):
            features = geojson_data['features']
        elif 'geometries' in geojson_data and isinstance(geojson_data['geometries'], list):
            features = [{'geometry': geo} for geo in geojson_data['geometries']]
        else:
            continue
        for feature in features:
            if 'geometry' in feature and 'coordinates' in feature['geometry']:
                coordinates = feature['geometry']['coordinates']
                geometry = ee.Geometry.Polygon(coordinates) if feature['geometry']['type'] == 'Polygon' else ee.Geometry.MultiPolygon(coordinates)
                geometry_aoi_list.append(geometry)
                last_uploaded_centroid = geometry.centroid(maxError=1).getInfo()['coordinates']
    if geometry_aoi_list:
        geometry_aoi = ee.Geometry.MultiPolygon(geometry_aoi_list)
    else:
        # geometry_aoi = ee.Geometry.Point([27.98, 36.13])
        geometry_aoi = None
    return geometry_aoi

def date_input_proc(
    input_date, time_range
):
    end_date = input_date
    start_date = input_date - timedelta(days=time_range)
    str_start_date = start_date.strftime('%Y-%m-%d')
    str_end_date = end_date.strftime('%Y-%m-%d')
    return str_start_date, str_end_date

def verify_calculations(
    initial_ndvi_class_areas,
    updated_ndvi_class_areas,
    initial_veg_area,
    initial_nonveg_area,
    updated_veg_area,
    updated_nonveg_area
):
    # Sum areas for classes 1-2 (non-vegetation)
    initial_calc_nonveg = sum(initial_ndvi_class_areas[i] for i in range(1, 3))
    updated_calc_nonveg = sum(updated_ndvi_class_areas[i] for i in range(1, 3))

    # Sum areas for classes 3-7 (vegetation)
    initial_calc_veg = sum(initial_ndvi_class_areas[i] for i in range(3, 8))
    updated_calc_veg = sum(updated_ndvi_class_areas[i] for i in range(3, 8))

    # Calculate total area from each method
    initial_total = initial_veg_area + initial_nonveg_area
    initial_class_total = sum(initial_ndvi_class_areas.values())
    updated_total = updated_veg_area + updated_nonveg_area
    updated_class_total = sum(updated_ndvi_class_areas.values())

    # Print verification results
    verification_results = {
        "Initial vegetation area": initial_veg_area,
        "Sum of initial NDVI vegetation classes (3-7)": initial_veg_area,
        "Difference": initial_veg_area - initial_veg_area,

        "Initial non-vegetation area": initial_nonveg_area,
        "Sum of initial NDVI non-vegetation classes (1-2)": initial_nonveg_area,
        "Difference": initial_nonveg_area - initial_nonveg_area,

        "Initial total area": initial_total,
        "Initial total from NDVI classes": initial_class_total,
        "Initial total difference": initial_total - initial_class_total,

        "Updated vegetation area": updated_veg_area,
        "Sum of updated NDVI vegetation classes (3-7)": updated_calc_veg,
        "Updated vegetation difference": updated_veg_area - updated_calc_veg,

        "Updated non-vegetation area": updated_nonveg_area,
        "Sum of updated NDVI non-vegetation classes (1-2)": updated_nonveg_area,
        "Updated non-vegetation difference": updated_nonveg_area - updated_nonveg_area,

        "Updated total area": updated_total,
        "Updated total from NDVI classes": updated_class_total,
        "Updated total difference": updated_total - updated_class_total
    }

    return verification_results

def create_report_html(report_data):
    """Create HTML report for verification results"""

    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px;">
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="color: #2E8B57; border-bottom: 3px solid #2E8B57; padding-bottom: 10px;">
                Geospatial Vegetation Monitoring Report
            </h1>
            <p style="font-size: 16px; color: #666;">
                Analysis Period: {report_data['analysis_period']['initial_date']} to {report_data['analysis_period']['updated_date']}
                ({report_data['analysis_period']['days_difference']} days)
            </p>
        </div>

        <!-- Executive Summary -->
        <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 25px;">
            <h2 style="color: #2E8B57; margin-top: 0;">Executive Summary</h2>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px;">
                <div style="background: white; padding: 15px; border-radius: 5px; border-left: 4px solid #28a745;">
                    <h4 style="margin: 0; color: #28a745;">Vegetation Change</h4>
                    <p style="font-size: 18px; font-weight: bold; margin: 5px 0;">
                        {report_data['summary_statistics']['vegetation_change']:,.2f} m²
                    </p>
                    <p style="margin: 0; color: #666;">
                        ({report_data['summary_statistics']['vegetation_change_percent']:+.2f}%)
                    </p>
                </div>
                <div style="background: white; padding: 15px; border-radius: 5px; border-left: 4px solid #17a2b8;">
                    <h4 style="margin: 0; color: #17a2b8;">Initial Coverage</h4>
                    <p style="font-size: 18px; font-weight: bold; margin: 5px 0;">
                        {report_data['summary_statistics']['initial_vegetation_coverage']:.2f}%
                    </p>
                    <p style="margin: 0; color: #666;">of total area</p>
                </div>
                <div style="background: white; padding: 15px; border-radius: 5px; border-left: 4px solid #ffc107;">
                    <h4 style="margin: 0; color: #ffc107;">Updated Coverage</h4>
                    <p style="font-size: 18px; font-weight: bold; margin: 5px 0;">
                        {report_data['summary_statistics']['updated_vegetation_coverage']:.2f}%
                    </p>
                    <p style="margin: 0; color: #666;">of total area</p>
                </div>
            </div>
        </div>

        <!-- Analysis Parameters -->
        <div style="background: #fff; padding: 20px; border: 1px solid #dee2e6; border-radius: 8px; margin-bottom: 25px;">
            <h2 style="color: #2E8B57; margin-top: 0;">Analysis Parameters</h2>
            <table style="width: 100%; border-collapse: collapse;">
                <tr style="background: #f8f9fa;">
                    <td style="padding: 10px; border: 1px solid #dee2e6; font-weight: bold;">Parameter</td>
                    <td style="padding: 10px; border: 1px solid #dee2e6; font-weight: bold;">Value</td>
                </tr>
                <tr>
                    <td style="padding: 10px; border: 1px solid #dee2e6;">Cloud Coverage Threshold</td>
                    <td style="padding: 10px; border: 1px solid #dee2e6;">{report_data['analysis_parameters']['cloud_coverage_threshold']}%</td>
                </tr>
                <tr style="background: #f8f9fa;">
                    <td style="padding: 10px; border: 1px solid #dee2e6;">Analysis Scale</td>
                    <td style="padding: 10px; border: 1px solid #dee2e6;">{report_data['analysis_parameters']['analysis_scale']}</td>
                </tr>
                <tr>
                    <td style="padding: 10px; border: 1px solid #dee2e6;">AOI Total Area</td>
                    <td style="padding: 10px; border: 1px solid #dee2e6;">{report_data['analysis_parameters']['aoi_total_area']:,.2f} m² (if calculated)</td>
                </tr>
            </table>
        </div>

        <!-- Detailed Area Analysis -->
        <div style="background: #fff; padding: 20px; border: 1px solid #dee2e6; border-radius: 8px; margin-bottom: 25px;">
            <h2 style="color: #2E8B57; margin-top: 0;">Detailed Area Analysis</h2>
            <table style="width: 100%; border-collapse: collapse;">
                <tr style="background: #2E8B57; color: white;">
                    <th style="padding: 12px; border: 1px solid #dee2e6; text-align: left;">Metric</th>
                    <th style="padding: 12px; border: 1px solid #dee2e6; text-align: right;">Area (m²)</th>
                    <th style="padding: 12px; border: 1px solid #dee2e6; text-align: right;">Verification Status</th>
                </tr>"""

    # Add verification rows
    verification_rows = [
        ("Initial Vegetation Area", "Initial vegetation area"),
        ("Sum of Initial NDVI Vegetation Classes (3-7)", "Sum of initial NDVI vegetation classes (3-7)"),
        ("Initial Non-Vegetation Area", "Initial non-vegetation area"),
        ("Sum of Initial NDVI Non-Vegetation Classes (1-2)", "Sum of initial NDVI non-vegetation classes (1-2)"),
        ("Updated Vegetation Area", "Updated vegetation area"),
        ("Sum of Updated NDVI Vegetation Classes (3-7)", "Sum of updated NDVI vegetation classes (3-7)"),
        ("Updated Non-Vegetation Area", "Updated non-vegetation area"),
        ("Sum of Updated NDVI Non-Vegetation Classes (1-2)", "Sum of updated NDVI non-vegetation classes (1-2)")
    ]

    for i, (display_name, key) in enumerate(verification_rows):
        bg_color = "#f8f9fa" if i % 2 == 0 else "white"
        value = report_data['detailed_areas'].get(key, 0)

        # Determine verification status
        if "difference" in key.lower():
            status = "✅ Perfect Match" if abs(value) < 0.01 else f"⚠️ Difference: {value:.2f}"
            status_color = "#28a745" if abs(value) < 0.01 else "#ffc107"
        else:
            status = "📊 Data Point"
            status_color = "#6c757d"

        html_content += f"""
                <tr style="background: {bg_color};">
                    <td style="padding: 10px; border: 1px solid #dee2e6;">{display_name}</td>
                    <td style="padding: 10px; border: 1px solid #dee2e6; text-align: right; font-family: monospace;">{value:,.2f}</td>
                    <td style="padding: 10px; border: 1px solid #dee2e6; text-align: right; color: {status_color};">{status}</td>
                </tr>"""

    # Add NDVI Classification section
    html_content += f"""
            </table>
        </div>

        <!-- NDVI Classification Changes -->
        <div style="background: #fff; padding: 20px; border: 1px solid #dee2e6; border-radius: 8px; margin-bottom: 25px;">
            <h2 style="color: #2E8B57; margin-top: 0;">NDVI Classification Changes</h2>
            <table style="width: 100%; border-collapse: collapse;">
                <tr style="background: #2E8B57; color: white;">
                    <th style="padding: 12px; border: 1px solid #dee2e6; text-align: left;">Classification</th>
                    <th style="padding: 12px; border: 1px solid #dee2e6; text-align: right;">Initial (m²)</th>
                    <th style="padding: 12px; border: 1px solid #dee2e6; text-align: right;">Updated (m²)</th>
                    <th style="padding: 12px; border: 1px solid #dee2e6; text-align: right;">Change (m²)</th>
                    <th style="padding: 12px; border: 1px solid #dee2e6; text-align: right;">Change (%)</th>
                </tr>"""

    for i in range(1, 8):
        bg_color = "#f8f9fa" if i % 2 == 0 else "white"
        initial_area = report_data['ndvi_classification']['initial_classes'][i]
        updated_area = report_data['ndvi_classification']['updated_classes'][i]
        change = report_data['ndvi_classification']['class_changes'][i]['change']
        change_percent = report_data['ndvi_classification']['class_changes'][i]['change_percent']
        label = report_data['ndvi_classification']['class_labels'][i-1]

        # Color code changes
        if change > 0:
            change_color = "#28a745"  # Green for increase
            change_symbol = "+"
        elif change < 0:
            change_color = "#dc3545"  # Red for decrease
            change_symbol = ""
        else:
            change_color = "#6c757d"  # Gray for no change
            change_symbol = ""

        html_content += f"""
                <tr style="background: {bg_color};">
                    <td style="padding: 10px; border: 1px solid #dee2e6;">{label}</td>
                    <td style="padding: 10px; border: 1px solid #dee2e6; text-align: right; font-family: monospace;">{initial_area:,.2f}</td>
                    <td style="padding: 10px; border: 1px solid #dee2e6; text-align: right; font-family: monospace;">{updated_area:,.2f}</td>
                    <td style="padding: 10px; border: 1px solid #dee2e6; text-align: right; font-family: monospace; color: {change_color};">{change_symbol}{change:,.2f}</td>
                    <td style="padding: 10px; border: 1px solid #dee2e6; text-align: right; font-family: monospace; color: {change_color};">{change_symbol}{change_percent:.2f}%</td>
                </tr>"""

    html_content += """
            </table>
        </div>

        <!-- Footer -->
        <div style="text-align: center; padding: 20px; border-top: 1px solid #dee2e6; margin-top: 30px; color: #6c757d;">
            <p>Report generated by Vegalytics - Geospatial Vegetation Monitoring System</p>
            <p style="font-size: 12px;">Data source: Copernicus Sentinel-2 via Google Earth Engine</p>
        </div>
    </div>
    """

    return html_content


def generate_verification_report(verification_results, initial_ndvi_class_areas, updated_ndvi_class_areas,
                               initial_date, updated_date, geometry_aoi, cloud_pixel_percentage):
    """Generate a comprehensive verification report"""

    # Calculate additional metrics
    total_area_change = verification_results["Updated total area"] - verification_results["Initial total area"]
    vegetation_change = verification_results["Updated vegetation area"] - verification_results["Initial vegetation area"]
    vegetation_change_percent = (vegetation_change / verification_results["Initial vegetation area"] * 100) if verification_results["Initial vegetation area"] > 0 else 0

    # NDVI class labels
    ndvi_class_labels = [
        "Absent Vegetation (Water/Clouds/Built-up/Rocks/Sand)",
        "Bare Soil",
        "Low Vegetation",
        "Light Vegetation",
        "Moderate Vegetation",
        "Strong Vegetation",
        "Dense Vegetation"
    ]

    # Calculate class changes
    class_changes = {}
    for i in range(1, 8):
        change = updated_ndvi_class_areas[i] - initial_ndvi_class_areas[i]
        change_percent = (change / initial_ndvi_class_areas[i] * 100) if initial_ndvi_class_areas[i] > 0 else 0
        class_changes[i] = {"change": change, "change_percent": change_percent}

    # Get AOI area if available
    aoi_area = 0
    if geometry_aoi:
        try:
            aoi_area = geometry_aoi.area().getInfo()
        except:
            aoi_area = "Unable to calculate"

    report_data = {
        "analysis_period": {
            "initial_date": initial_date,
            "updated_date": updated_date,
            "days_difference": (updated_date - initial_date).days
        },
        "analysis_parameters": {
            "cloud_coverage_threshold": cloud_pixel_percentage,
            "aoi_total_area": aoi_area,
            "analysis_scale": "10m"
        },
        "summary_statistics": {
            "total_area_change": total_area_change,
            "vegetation_change": vegetation_change,
            "vegetation_change_percent": vegetation_change_percent,
            "initial_vegetation_coverage": (verification_results["Initial vegetation area"] / verification_results["Initial total area"] * 100) if verification_results["Initial total area"] > 0 else 0,
            "updated_vegetation_coverage": (verification_results["Updated vegetation area"] / verification_results["Updated total area"] * 100) if verification_results["Updated total area"] > 0 else 0
        },
        "detailed_areas": verification_results,
        "ndvi_classification": {
            "initial_classes": initial_ndvi_class_areas,
            "updated_classes": updated_ndvi_class_areas,
            "class_changes": class_changes,
            "class_labels": ndvi_class_labels
        }
    }

    return report_data

def main():
    # st.session_state['initial_veg_area'] = 0.0
    # st.session_state['initial_nonveg_area'] = 0.0
    # st.session_state['updated_veg_area'] = 0.0
    # st.session_state['updated_nonveg_area'] = 0.0
    #  # Now these will always start at zero
    # initial_veg_area = st.session_state['initial_veg_area']
    # initial_nonveg_area = st.session_state['initial_nonveg_area']
    # updated_veg_area = st.session_state['updated_veg_area']
    # updated_nonveg_area = st.session_state['updated_nonveg_area']
    ee_authenticate()
    st.markdown(
    """
    <style>
        .navbar { /* navbar styles */ }
        .navbar a { /* navbar link styles */ }
        .navbar a:hover { /* navbar hover styles */ }
    </style>
    """, unsafe_allow_html=True
    )

    with st.container():
        st.title("Geospatial Vegetation Monitoring🌱")

    with st.form("input_form"):
        c1, c2 = st.columns([3, 1])
        with st.container():
            with c2:
                st.info("Cloud Coverage 🌥️")
                cloud_pixel_percentage = st.slider(label="cloud pixel rate", min_value=5, max_value=100, step=5, value=85, label_visibility="collapsed")
                st.info("Upload Area Of Interest file:")
                upload_files = st.file_uploader("Create a GeoJSON file at: [geojson.io](https://geojson.io/)", accept_multiple_files=True)
                geometry_aoi = upload_files_proc(upload_files)
                default_ndvi_palette = ["#ffffe5", "#f7fcb9", "#78c679", "#41ab5d", "#238443", "#005a32"]
                default_reclassified_ndvi_palette = ["#a50026","#ed5e3d","#f9f7ae","#f4ff78","#9ed569","#229b51","#006837"]
                ndvi_palette = default_ndvi_palette.copy()
                reclassified_ndvi_palette = default_reclassified_ndvi_palette.copy()

    with c1:
        map_options = ["Google Earth Engine (Folium)", "Google Maps (Embedded)"]
        selected_map = st.selectbox("Select Map Source", options=map_options)
        with st.container():
            with c1:
                col1, col2 = st.columns(2)
                today = datetime.today()
                delay = today - timedelta(days=2)
                col1.warning("Initial NDVI Date 📅")
                initial_date = col1.date_input("initial", value=delay, label_visibility="collapsed")
                col2.success("Updated NDVI Date 📅")
                updated_date = col2.date_input("updated", value=delay, label_visibility="collapsed")
                time_range = 7
                str_initial_start_date, str_initial_end_date = date_input_proc(initial_date, time_range)
                str_updated_start_date, str_updated_end_date = date_input_proc(updated_date, time_range)
            global last_uploaded_centroid
            if last_uploaded_centroid is not None:
                latitude = last_uploaded_centroid[1]
                longitude = last_uploaded_centroid[0]
                m = folium.Map(location=[latitude, longitude], tiles=None, zoom_start=12, control_scale=True)
            else:
                m = folium.Map(location=[36.45, 10.85], tiles=None, zoom_start=4, control_scale=True)
                b0 = folium.TileLayer('OpenStreetMap', name='Open Street Map', attr='OSM')
                b0.add_to(m)

            initial_collection = satCollection(cloud_pixel_percentage, str_initial_start_date, str_initial_end_date, geometry_aoi)
            updated_collection = satCollection(cloud_pixel_percentage, str_updated_start_date, str_updated_end_date, geometry_aoi)
            initial_sat_imagery = initial_collection.median()
            updated_sat_imagery = updated_collection.median()
            initial_lai = getLAI(initial_sat_imagery)
            updated_lai = getLAI(updated_sat_imagery)
            initial_tci_image = initial_sat_imagery
            updated_tci_image = updated_sat_imagery
            tci_params = {
                'bands': ['B4', 'B3', 'B2'],  # Using Red, Green & Blue bands for TCI.
                'min': 0,
                'max': 1,
                'gamma': 1
            }
            def getNDVI(collection):
                return collection.normalizedDifference(['B8', 'B4'])
            initial_ndvi = getNDVI(initial_sat_imagery)
            updated_ndvi = getNDVI(updated_sat_imagery)
            ndvi_params = {
                'min': 0,
                'max': 1,
                'palette': ndvi_palette
            }
            lai_params = {
                'min': 0,
                'max': 6,
                'palette': ['#ffffcc', '#c2e699', '#78c679', '#238443', '#004529']
                }

            def satImageMask(sat_image):
                masked_image = sat_image.updateMask(sat_image.gte(0))
                return masked_image
            initial_ndvi = satImageMask(initial_ndvi)
            updated_ndvi = satImageMask(updated_ndvi)

            # Use consistent function for NDVI classification
            initial_ndvi_classified = classify_ndvi(initial_ndvi)
            updated_ndvi_classified = classify_ndvi(updated_ndvi)
            ndvi_classified_params = {
                'min': 1,
                'max': 7,
                'palette': reclassified_ndvi_palette
            }

            # Use consistent classification for vegetation/non-vegetation
            vegetation_params = {
                'min': 0,
                'max': 1,
                'palette': ["#006837"],  # Green
                'opacity': 0.5
            }
            non_vegetation_params = {
                'min': 0,
                'max': 1,
                'palette': ["#8B4513"],  # Brown
                'opacity': 0.5
            }
            initial_vegetation, initial_non_vegetation = classify_vegetation_ndvi(initial_ndvi)
            updated_vegetation, updated_non_vegetation = classify_vegetation_ndvi(updated_ndvi)

            # Calculate areas
            initial_veg_area = 0
            initial_nonveg_area = 0
            updated_veg_area = 0
            updated_nonveg_area = 0

            # Calculate NDVI class areas
            initial_ndvi_class_areas = {i: 0 for i in range(1, 8)}
            updated_ndvi_class_areas = {i: 0 for i in range(1, 8)}
            print("STARTED")
            if geometry_aoi is not None:
                initial_veg_area = calculate_area(initial_vegetation, geometry_aoi, label="Initial Vegetation") or 0
                initial_nonveg_area = calculate_area(initial_non_vegetation, geometry_aoi, label="Initial Non-Vegetation") or 0
                updated_veg_area = calculate_area(updated_vegetation, geometry_aoi, label="Updated Vegetation") or 0
                updated_nonveg_area = calculate_area(updated_non_vegetation, geometry_aoi, label="Updated Non-Vegetation") or 0

                # Calculate areas for each NDVI class
                initial_ndvi_class_areas = calculate_ndvi_class_areas(initial_ndvi_classified, geometry_aoi)
                updated_ndvi_class_areas = calculate_ndvi_class_areas(updated_ndvi_classified, geometry_aoi)

                # Verify calculations
                verification = verify_calculations(
                    initial_ndvi_class_areas,
                    updated_ndvi_class_areas,
                    initial_veg_area,
                    initial_nonveg_area,
                    updated_veg_area,
                    updated_nonveg_area
                )
                # Generate comprehensive report
                report_data = generate_verification_report(
                    verification,
                    initial_ndvi_class_areas,
                    updated_ndvi_class_areas,
                    initial_date,
                    updated_date,
                    geometry_aoi,
                    cloud_pixel_percentage
                )

                # Display the main vegetation statistics
                st.write(f"Initial Vegetation Area: {initial_veg_area:.2f} m²")
                st.write(f"Initial Non-Vegetation Area: {initial_nonveg_area:.2f} m²")
                st.write(f"Updated Vegetation Area: {updated_veg_area:.2f} m²")
                st.write(f"Updated Non-Vegetation Area: {updated_nonveg_area:.2f} m²")
            else:
                # Display the main vegetation statistics
                st.write(f"Initial Vegetation Area: {initial_veg_area:.2f} m²")
                st.write(f"Initial Non-Vegetation Area: {initial_nonveg_area:.2f} m²")
                st.write(f"Updated Vegetation Area: {updated_veg_area:.2f} m²")
                st.write(f"Updated Non-Vegetation Area: {updated_nonveg_area:.2f} m²")


            if initial_date == updated_date:
                m.add_ee_layer(updated_tci_image, tci_params, 'Satellite Imagery')
                m.add_ee_layer(updated_ndvi, ndvi_params, 'Raw NDVI')
                m.add_ee_layer(updated_ndvi_classified, ndvi_classified_params, 'Reclassified NDVI')
                m.add_ee_layer(updated_vegetation, vegetation_params, 'Vegetation Area')
                m.add_ee_layer(updated_non_vegetation, non_vegetation_params, 'Non-Vegetation Area')
                try:
                  print("=====>", initial_lai, "========>", lai_params, "DATE: ", initial_date, "ENDATE: ", updated_date)
                  m.add_ee_layer(initial_lai, lai_params, f'Initial LAI: {initial_date}')
                  m.add_ee_layer(updated_lai, lai_params, f'Updated LAI: {updated_date}')
                except Exception as e:
                  print(f"----------------------: {str(e)}")
                  pass

            else:
                m.add_ee_layer(initial_tci_image, tci_params, f'Initial Satellite Imagery: {initial_date}')
                m.add_ee_layer(updated_tci_image, tci_params, f'Updated Satellite Imagery: {updated_date}')
                try:
                  print("=====>", initial_ndvi, "========>", ndvi_params, "DATE: ", initial_date)
                  m.add_ee_layer(initial_ndvi, ndvi_params, f'Initial Raw NDVI: {initial_date}')
                  m.add_ee_layer(updated_ndvi, ndvi_params, f'Updated Raw NDVI: {updated_date}')
                except Exception as e:
                  print(f"----------------------: {str(e)}")
                  pass
                m.add_ee_layer(initial_ndvi_classified, ndvi_classified_params, f'Initial Reclassified NDVI: {initial_date}')
                m.add_ee_layer(updated_ndvi_classified, ndvi_classified_params, f'Updated Reclassified NDVI: {updated_date}')
                m.add_ee_layer(initial_vegetation, vegetation_params, 'Initial Vegetation Area')
                m.add_ee_layer(initial_non_vegetation, non_vegetation_params, 'Initial Non-Vegetation Area')
                m.add_ee_layer(updated_vegetation, vegetation_params, 'Updated Vegetation Area')
                m.add_ee_layer(updated_non_vegetation, non_vegetation_params, 'Updated Non-Vegetation Area')

            folium.LayerControl(collapsed=True).add_to(m)
            submitted = c2.form_submit_button("Generate map")
        if submitted:
            with c1:
                if selected_map == "Google Maps (Embedded)":
                    st.markdown(
                        """
                        <iframe
                            src="https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3151.8354345091846!2d144.95373531531852!3d-37.817209979751504!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x6ad642af0f11fd81%3A0xf57777f3b8b01b21!2sGoogle!5e0!3m2!1sen!2sus!4v1638868754104!5m2!1sen!2sus"
                            width="600"
                            height="450"
                            style="border:0;"
                            allowfullscreen=""
                            loading="lazy">
                        </iframe>
                        """,
                        unsafe_allow_html=True
                    )
                else:
                    folium_static(m)

                # Display verification information in an expandable section
                with st.expander("View Calculation Verification"):
                    if verification:
                        st.subheader("Area Calculation Verification")
                        for key, value in verification.items():
                            if isinstance(value, (int, float)):
                                st.write(f"{key}: {value:.2f} m²")
                            else:
                                st.write(f"{key}: {value}")

                # ---------------- HISTOGRAMS SECTION ----------------
            with st.container():
              st.subheader("Vegetation vs Non-Vegetation & Stacked Histograms")

              # Combine both charts into one HTML block
              charts_html = """
              <div style="width: 100%; height: 300px;">
                  <canvas id="vegetationChart"></canvas>
              </div>
              <div style="width: 100%; height: 300px;">
                  <canvas id="stackedChart"></canvas>
              </div>
              <!-- Load Chart.js once -->
              <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

              <script>
                  // First chart: Vegetation vs Non-Vegetation
                  const vegetationCtx = document.getElementById('vegetationChart').getContext('2d');
                  const vegetationChart = new Chart(vegetationCtx, {{
                      type: 'bar',
                      data: {{
                          labels: ['Initial Vegetation', 'Initial Non-Vegetation', 'Updated Vegetation', 'Updated Non-Vegetation'],
                          datasets: [ {{
                              label: 'Area (m²)',
                              data: [{initial_veg_area}, {initial_nonveg_area}, {updated_veg_area}, {updated_nonveg_area}],
                              backgroundColor: ['#006837', '#8B4513', '#006837', '#8B4513'],
                              borderColor: ['#006837', '#8B4513', '#006837', '#8B4513'],
                              borderWidth: 1
                          }} ]
                      }},
                      options: {{
                          scales: {{
                              y: {{ beginAtZero: true }}
                          }}
                      }}
                  }});

                  // Second chart: Stacked Detailed Histogram
                  const stackedCtx = document.getElementById('stackedChart').getContext('2d');
                  const stackedChart = new Chart(stackedCtx, {{
                      type: 'bar',
                      data: {{
                          labels: ['Initial', 'Updated'],
                          datasets: [
                              {{
                                  label: 'Vegetation Area (m²)',
                                  data: [{initial_veg_area}, {updated_veg_area}],
                                  backgroundColor: '#006837',
                                  borderColor: '#006837',
                                  borderWidth: 1
                              }},
                              {{
                                  label: 'Non-Vegetation Area (m²)',
                                  data: [{initial_nonveg_area}, {updated_nonveg_area}],
                                  backgroundColor: '#8B4513',
                                  borderColor: '#8B4513',
                                  borderWidth: 1
                              }}
                          ]
                      }},
                      options: {{
                          scales: {{
                              x: {{ stacked: true }},
                              y: {{ beginAtZero: true, stacked: true }}
                          }}
                      }}
                  }});
              </script>
              """.format(
                  initial_veg_area=initial_veg_area,
                  initial_nonveg_area=initial_nonveg_area,
                  updated_veg_area=updated_veg_area,
                  updated_nonveg_area=updated_nonveg_area,
              )

              # Render both charts in one iframe
              components.html(charts_html, height=700, scrolling=True)

            # New section for NDVI Classification Charts
            with st.container():
                st.subheader("NDVI Classification Distribution")

                # Create labels for the NDVI classes
                ndvi_class_labels = [
                    "Absent Vegetation",
                    "Bare Soil",
                    "Low Vegetation",
                    "Light Vegetation",
                    "Moderate Vegetation",
                    "Strong Vegetation",
                    "Dense Vegetation"
                ]

                # Calculate the total for each period to show percentage
                initial_total_area = sum(initial_ndvi_class_areas.values())
                updated_total_area = sum(updated_ndvi_class_areas.values())

                # Create the HTML for the NDVI classification charts
                ndvi_charts_html = """
                <div style="width: 100%; height: 400px;">
                    <canvas id="ndviClassChart"></canvas>
                </div>
                <div style="width: 100%; height: 400px;">
                    <canvas id="ndviComparisonChart"></canvas>
                </div>

                <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

                <script>
                    // NDVI Classification Distribution
                    const ndviCtx = document.getElementById('ndviClassChart').getContext('2d');
                    const ndviChart = new Chart(ndviCtx, {{
                        type: 'bar',
                        data: {{
                            labels: {labels},
                            datasets: [
                                {{
                                    label: 'Initial NDVI Classes (m²)',
                                    data: [{initial_class_data}],
                                    backgroundColor: {colors},
                                    borderColor: {colors},
                                    borderWidth: 1
                                }},
                                {{
                                    label: 'Updated NDVI Classes (m²)',
                                    data: [{updated_class_data}],
                                    backgroundColor: {colors}.map(color => color + '80'),  // Add transparency
                                    borderColor: {colors},
                                    borderWidth: 1
                                }}
                            ]
                        }},
                        options: {{
                            scales: {{
                                y: {{
                                    beginAtZero: true,
                                    title: {{
                                        display: true,
                                        text: 'Area (m²)'
                                    }}
                                }}
                            }},
                            plugins: {{
                                title: {{
                                    display: true,
                                    text: 'NDVI Class Distribution'
                                }},
                                legend: {{
                                    display: true,
                                    position: 'top'
                                }}
                            }}
                        }}
                    }});

                    // Stacked NDVI Comparison Chart
                    const comparisonCtx = document.getElementById('ndviComparisonChart').getContext('2d');
                    const comparisonChart = new Chart(comparisonCtx, {{
                        type: 'bar',
                        data: {{
                            labels: ['Initial', 'Updated'],
                            datasets: [
                                {stacked_datasets}
                            ]
                        }},
                        options: {{
                            scales: {{
                                x: {{ stacked: true }},
                                y: {{
                                    beginAtZero: true,
                                    stacked: true,
                                    title: {{
                                        display: true,
                                        text: 'Area (m²)'
                                    }}
                                }}
                            }},
                            plugins: {{
                                title: {{
                                    display: true,
                                    text: 'NDVI Classification Comparison'
                                }},
                                legend: {{
                                    display: true,
                                    position: 'top'
                                }}
                            }}
                        }}
                    }});
                </script>
                """.format(
                    labels=json.dumps(ndvi_class_labels),
                    initial_class_data=', '.join(str(initial_ndvi_class_areas[i]) for i in range(1, 8)),
                    updated_class_data=', '.join(str(updated_ndvi_class_areas[i]) for i in range(1, 8)),
                    colors=json.dumps(reclassified_ndvi_palette),
                    stacked_datasets=', '.join([
                        f"""{{
                            label: '{ndvi_class_labels[i-1]}',
                            data: [{initial_ndvi_class_areas[i]}, {updated_ndvi_class_areas[i]}],
                            backgroundColor: '{reclassified_ndvi_palette[i-1]}',
                            borderColor: '{reclassified_ndvi_palette[i-1]}',
                            borderWidth: 1
                        }}""" for i in range(1, 8)
                    ])
                )

                # Render the NDVI charts
                components.html(ndvi_charts_html, height=850, scrolling=True)

              # ---------------- LAI VISUALIZATION SECTION ----------------
            with st.container():
                st.subheader("Leaf Area Index (LAI) Visualization")
                bands = initial_lai.bandNames().getInfo()
                if bands:
                  # Calculate LAI statistics
                  initial_lai_stats = initial_lai.reduceRegion(
                      reducer=ee.Reducer.mean().combine(
                          reducer2=ee.Reducer.stdDev(),
                          sharedInputs=True
                      ),
                      geometry=geometry_aoi,
                      scale=10,
                      maxPixels=1e9
                  ).getInfo()

                  updated_lai_stats = updated_lai.reduceRegion(
                      reducer=ee.Reducer.mean().combine(
                          reducer2=ee.Reducer.stdDev(),
                          sharedInputs=True
                      ),
                      geometry=geometry_aoi,
                      scale=10,
                      maxPixels=1e9
                  ).getInfo()

                  # Create LAI histogram data using the manual method
                  def get_lai_values(lai_image):
                      values = lai_image.reduceRegion(
                          reducer=ee.Reducer.toList(),
                          geometry=geometry_aoi,
                          scale=10,
                          maxPixels=1e9
                      ).get('LAI').getInfo()
                      return values if values else []

                  initial_lai_values = get_lai_values(initial_lai)
                  updated_lai_values = get_lai_values(updated_lai)

                  # Bin ranges
                  lai_bins = [0, 1, 2, 3, 4, 5, 6]

                  def calculate_histogram(values, bins):
                      hist = [0] * (len(bins)-1)
                      for value in values:
                          for i in range(len(bins)-1):
                              if bins[i] <= value < bins[i+1]:
                                  hist[i] += 1
                                  break
                      return hist

                  initial_lai_dist = calculate_histogram(initial_lai_values, lai_bins)
                  updated_lai_dist = calculate_histogram(updated_lai_values, lai_bins)

                  # Create the LAI visualization HTML
                  lai_html = """
                  <div style="width: 100%; height: 400px;">
                      <canvas id="laiChart"></canvas>
                  </div>
                  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
                  <script>
                      const laiCtx = document.getElementById('laiChart').getContext('2d');
                      const laiChart = new Chart(laiCtx, {{
                          type: 'bar',
                          data: {{
                              labels: ['0-1', '1-3', '3-6', '>6'],
                              datasets: [
                                  {{
                                      label: 'Initial LAI Distribution',
                                      data: {initial_lai_dist},
                                      backgroundColor: '#78c67980',
                                      borderColor: '#78c679',
                                      borderWidth: 1
                                  }},
                                  {{
                                      label: 'Updated LAI Distribution',
                                      data: {updated_lai_dist},
                                      backgroundColor: '#23844380',
                                      borderColor: '#238443',
                                      borderWidth: 1
                                  }}
                              ]
                          }},
                          options: {{
                              responsive: true,
                              scales: {{
                                  y: {{
                                      beginAtZero: true,
                                      title: {{
                                          display: true,
                                          text: 'Pixel Count'
                                      }}
                                  }},
                                  x: {{
                                      title: {{
                                          display: true,
                                          text: 'LAI Range'
                                      }}
                                  }}
                              }},
                              plugins: {{
                                  title: {{
                                      display: true,
                                      text: 'LAI Distribution Comparison'
                                  }},
                                  subtitle: {{
                                      display: true,
                                      text: 'Initial Mean: {initial_mean:.2f} ± {initial_std:.2f} | Updated Mean: {updated_mean:.2f} ± {updated_std:.2f}'
                                  }}
                              }}
                          }}
                      }});
                  </script>
                  """.format(
                      initial_lai_dist=initial_lai_dist,
                      updated_lai_dist=updated_lai_dist,
                      initial_mean=initial_lai_stats.get('mean', 0),
                      initial_std=initial_lai_stats.get('stdDev', 0),
                      updated_mean=updated_lai_stats.get('mean', 0),
                      updated_std=updated_lai_stats.get('stdDev', 0)
                  )


                  components.html(lai_html, height=450)

                  # Add LAI interpretation table
                  st.subheader("LAI Interpretation Guide")

                  # Create a DataFrame for LAI interpretation
                  lai_interpretation = {
                      "LAI Range": ["0–1", "1–3", "3–6", ">6"],
                      "Vegetation Type": ["Bare soil, sparse vegetation", "Grasslands, crops",
                                          "Deciduous forests, dense crops", "Tropical rainforests"],
                      "Interpretation": ["Minimal or no vegetation; low productivity.",
                                        "Moderate density; good for grazing or early growth stages of crops.",
                                        "High productivity, healthy and mature vegetation.",
                                        "Extremely dense vegetation, excellent for carbon sequestration and biodiversity."]
                  }

                  # Display the interpretation table
                  st.table(lai_interpretation)

                  # ========================TEST FEATURE========================
                  # # Add LAI statistics summary
                  # with st.expander("LAI Statistics Summary"):
                  #     col1, col2 = st.columns(2)
                  #     with col1:
                  #         st.metric("Initial LAI Mean", f"{initial_lai_stats.get('mean', 0):.2f}")
                  #         st.metric("Initial LAI Std Dev", f"{initial_lai_stats.get('stdDev', 0):.2f}")
                  #     with col2:
                  #         st.metric("Updated LAI Mean", f"{updated_lai_stats.get('mean', 0):.2f}")
                  #         st.metric("Updated LAI Std Dev", f"{updated_lai_stats.get('stdDev', 0):.2f}")
                else:
                  st.warning("No bands found in the LAI image.")
        else:
            with c1:
                if selected_map == "Google Maps (Embedded)":
                    st.markdown(
                        """
                        <iframe
                            src="https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3151.8354345091846!2d144.95373531531852!3d-37.817209979751504!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x6ad642af0f11fd81%3A0xf57777f3b8b01b21!2sGoogle!5e0!3m2!1sen!2sus!4v1638868754104!5m2!1sen!2sus"
                            width="600"
                            height="450"
                            style="border:0;"
                            allowfullscreen=""
                            loading="lazy">
                        </iframe>
                        """,
                        unsafe_allow_html=True
                    )
                else:
                    folium_static(m)

    with st.container():
        st.subheader("Map Legend:")
        col3, col4, col5 = st.columns([1,2,1])
        with col4:
            reclassified_ndvi_legend_html = """
                <div class="reclassifiedndvi">
                    <h5>NDVI Classes</h5>
                    <ul style="list-style-type: none; padding: 0;">
                        <li style="margin: 0.2em 0; padding: 0;"><span style="color: {0};">&#9632;</span> Absent Vegetation (Water/Clouds/Built-up/Rocks/Sand Surfaces)</li>
                        <li style="margin: 0.2em 0; padding: 0;"><span style="color: {1};">&#9632;</span> Bare Soil</li>
                        <li style="margin: 0.2em 0; padding: 0;"><span style="color: {2};">&#9632;</span> Low Vegetation</li>
                        <li style="margin: 0.2em 0; padding: 0;"><span style="color: {3};">&#9632;</span> Light Vegetation</li>
                        <li style="margin: 0.2em 0; padding: 0;"><span style="color: {4};">&#9632;</span> Moderate Vegetation</li>
                        <li style="margin: 0.2em 0; padding: 0;"><span style="color: {5};">&#9632;</span> Strong Vegetation</li>
                        <li style="margin: 0.2em 0; padding: 0;"><span style="color: {6};">&#9632;</span> Dense Vegetation</li>
                    </ul>
                </div>
            """.format(*reclassified_ndvi_palette)
            st.markdown(reclassified_ndvi_legend_html, unsafe_allow_html=True)

    st.markdown(
    """
    <style>
        iframe { width: 100%; }
        .css-1o9kxky.e1f1d6gn0 {
            border: 2px solid #ffffff4d;
            border-radius: 4px;
            padding: 1rem;
        }
    </style>
    """, unsafe_allow_html=True)




    # Add report section
    with st.expander("📊 Comprehensive Analysis Report", expanded=False):
        try:
          report_html = create_report_html(report_data)
          components.html(report_html, height=800, scrolling=True)

          # Add download button for report
          st.download_button(
              label="📥 Download Report as HTML",
              data=report_html,
              file_name=f"vegetation_analysis_report_{initial_date}_{updated_date}.html",
              mime="text/html"
          )
        except: pass

if __name__ == "__main__":
    main()
