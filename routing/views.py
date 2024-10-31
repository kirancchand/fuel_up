import requests
import pandas as pd
from django.http import JsonResponse
from django.http import HttpResponse
from geopy.distance import geodesic
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import math
import requests
import os
import time
import csv 

FUEL_PRICE_FILE = './fuel-prices-for-be-assessment.csv'
FUEL_EFFICIENCY = 10  
VEHICLE_RANGE = 500  

fuel_prices_df = pd.read_csv(FUEL_PRICE_FILE)

def get_route(start, end):
    api_key = '5b3ce3597851110001cf62481587fd80e7aa453b803bd839206cff9c'
    url = f'https://api.openrouteservice.org/v2/directions/driving-car?api_key={api_key}&start={start}&end={end}'

    # Send the GET request to the routing API
    response = requests.get(url)
    route_data = response.json()
    # print(route_data)
    distance = route_data['features'][0]['properties']['summary']['distance'] / 1609.34  # convert meters to miles 2704miles * 1.6 = ~4351km
    # print(distance)
    coordinates = route_data['features'][0]['geometry']['coordinates']
    # print(coordinates)
    steps = route_data['features'][0]['properties']['segments'][0]['steps']
    route_coordinates = [(coord[1], coord[0]) for coord in coordinates]
    # print(route_coordinates)
    
    return distance, route_coordinates

def haversine_distance(lat1, lon1, lat2, lon2):
    # Radius of the Earth in kilometers
    R = 6371.0
    # Convert degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c  # Distance in kilometers

def find_nearest_city(reference_point,csv_file_path):
    min_distance = float('inf')
    nearest_city_info = None

    with open(csv_file_path, mode='r') as file:
        reader = csv.DictReader(file)
        
        for row in reader:
            truck_id = row['OPIS Truckstop ID']
            city = row['City']
            lat = float(row['Latitude'])
            lon = float(row['Longitude'])
            
            # Calculate distance from the reference point
            distance = haversine_distance(reference_point[0], reference_point[1], lat, lon)
            
            if distance < min_distance:
                min_distance = distance
                nearest_city_info = {
                    "truckid": truck_id,
                    "city": city,
                    "latitude": lat,
                    "longitude": lon,
                    "distance_km": min_distance
                }

    return nearest_city_info

def find_nearest_coordinate_index(route_coords, start_coord):
    min_distance = float('inf')
    nearest_index = 0
    for i, coord in enumerate(route_coords):
        distance = geodesic(start_coord, coord).miles
        if distance < min_distance:
            min_distance = distance
            nearest_index = i
    return nearest_index

def find_coordinate_after_distance(route_coords, start_coord, target_distance_miles):
    # Step 1: Find the index of the route coordinate closest to the start_coord
    start_index = find_nearest_coordinate_index(route_coords, start_coord)
    
    # Step 2: Calculate cumulative distance from the closest starting point
    cumulative_distance = 0
    for i in range(start_index + 1, len(route_coords)):
        # Calculate the distance between consecutive points
        distance_segment = geodesic(route_coords[i-1], route_coords[i]).miles
        cumulative_distance += distance_segment

        # Check if the cumulative distance has reached or exceeded the target distance
        if cumulative_distance >= target_distance_miles:
            return route_coords[i]

    # If the target distance exceeds the route distance from the starting point, return the last coordinate
    return route_coords[-1]
def get_optimal_stops(route_distance,route_coordinates):
    # Calculate the required number of fuel stops along the route
    num_fuel_stops = int(route_distance // VEHICLE_RANGE)
    # Initialize list to store details about each fuel stop
    fuel_stops = []
    total_fuel_cost = 0
    # Loop to select optimal stops based on fuel price
    initial_route=route_coordinates[0]
    for i in range(num_fuel_stops):
        # Calculate fuel needed for each stop and corresponding cost
        fuel_needed = VEHICLE_RANGE / FUEL_EFFICIENCY  # Gallons required per stop
        if i==num_fuel_stops:
            distance_moved=route_distance%(i-1)            
        else:
            distance_moved=500
        coordinate = find_coordinate_after_distance(route_coordinates,initial_route, distance_moved)

        nearest_city = find_nearest_city(coordinate,'./fuel-prices-for-be-assessment.csv')
        city_df = fuel_prices_df[fuel_prices_df['City'] == nearest_city['city']]
        min_price_row = city_df[city_df['Retail Price'] == city_df['Retail Price'].min()]
        min_price=min_price_row['Retail Price'].values[0]
        initial_route=coordinate
        fuel_cost = fuel_needed * min_price
        total_fuel_cost += fuel_cost
        # Add fuel stop details to the list
        fuel_stop = {
            "Truckstop Name": min_price_row['Truckstop Name'].values[0],
            "Address": min_price_row['Address'].values[0],
            "City": min_price_row['City'].values[0],
            "State": min_price_row['State'].values[0],
            "Retail Price": min_price_row['Retail Price'].values[0],
            "Latitude": min_price_row['Latitude'].values[0],
            "Longitude": min_price_row['Longitude'].values[0],
            "Fuel Cost": fuel_cost
        }
        fuel_stops.append(fuel_stop)

    return fuel_stops,total_fuel_cost

# def calculate_fuel_cost(distance):
#     gallons_needed = distance / FUEL_EFFICIENCY
#     avg_fuel_price = fuel_prices_df['Retail Price'].mean()
    
#     return gallons_needed * avg_fuel_price

def route_view(request):
    start = request.GET.get('start')
    end = request.GET.get('end')
    
    if not start or not end:
        return JsonResponse({'error': 'Start and end locations are required'}, status=400)

    distance, route_coordinates = get_route(start, end)
    optimal_stops_data,total_fuel_cost = get_optimal_stops(distance,route_coordinates)
    # total_fuel_cost = calculate_fuel_cost(distance)

    
    return JsonResponse({
        'distance': distance,
        'fuel_stops': optimal_stops_data,
        'total_fuel_cost': total_fuel_cost,
        'route_coordinates': route_coordinates
    })





def geocode_address(address):
    url = 'https://nominatim.openstreetmap.org/search'
    params = {
        'q': address,
        'format': 'json',
        'limit': 1
    }
    response = requests.get(url, params=params)
    if response.status_code == 200 and response.json():
        result = response.json()[0]
        print(result)
        return (float(result['lat']), float(result['lon']))
    return None

def geocode_addresslocationiq(address):
    url = 'https://us1.locationiq.com/v1/search.php'
    params = {
        'key': 'pk.9df483e92c7e92ed981ab57ff377a5cb',  # Replace with your actual API key
        'q': address,
        'format': 'json',
        'limit': 1
    }
    response = requests.get(url, params=params)
    if response.status_code == 200 and response.json():
        result = response.json()[0]
        return float(result['lat']), float(result['lon'])
    return None

def get_unique_city(out_file='unique_cities.csv'):
    df = pd.read_csv(FUEL_PRICE_FILE)
    unique_cities = df['City'].unique()
    unique_cities_df = pd.DataFrame(unique_cities, columns=['City'])
    unique_cities_df.drop_duplicates(subset='City')
    sorted_city=unique_cities_df.sort_values(by='City')
    sorted_city.to_csv(out_file, index=False)
    return out_file
def enrich_fuel_data(output_file='enriched_fuel_prices.csv'):
    df = pd.read_csv('./unique_cities.csv')
    df['Latitude'] = None
    df['Longitude'] = None
    for index, row in df.iterrows():
        try:
            city = f"{row['City']}"
            coords = geocode_addresslocationiq(city)      
            if coords:
                df.loc[df['City'] == city, 'Latitude'] = coords[0]
                df.loc[df['City'] == city, 'Longitude'] = coords[1]
            else:
                df.loc[df['City'] == city, 'Latitude'] = None
                df.loc[df['City'] == city, 'Longitude'] = None
            time.sleep(1.5)
        except Exception as e:
            print(f"Error fetching coordinates for city: {city}. Error: {e}")

    # # Save the enriched CSV
    df.to_csv(output_file, index=False)
    return output_file

def enrich_fuel_data_with_coordinates(request):   
    # Enrich the CSV and save it as a new file
    enriched_csv_path = enrich_fuel_data()
    # Open the enriched file and prepare it for download
    file_path = os.path.join(enriched_csv_path)
    with open(file_path, 'rb') as f:
        response = HttpResponse(f.read(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
        return response
def mergecsv(request):
    # Load both CSV files
    df1 = pd.read_csv('./fuel-prices-for-be-assessment.csv')
    df2 = pd.read_csv('./enriched_fuel_prices_originl.csv')

    # Merge based on the city column
    df_merged = pd.merge(df1, df2[['City', 'Latitude', 'Longitude']], on='City', how='left')

    # Save the updated first file with latitude and longitude
    df_merged.to_csv('./fuel-prices-for-be-assessment.csv', index=False)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="fuel-prices-for-be-assessment.csv"'
    
    return response
