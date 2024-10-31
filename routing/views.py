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



def optimal_data(target_waypoint):
    print("target_waypoint",target_waypoint)
    search_radius_miles = 100 
    lat, lon = target_waypoint
    search_radius_km = search_radius_miles * 1.60934
    overpass_url = f"https://overpass-api.de/api/interpreter?data=[out:json];node(around:{search_radius_km*1000},{lat},{lon})['amenity'='fuel'];out;"
    overpass_response = requests.get(overpass_url)
    fuel_stations = overpass_response.json().get('elements', [])

    # Step 4: Calculate the nearest fuel station
    nearest_station = None
    min_distance = float('inf')
    for station in fuel_stations:
        station_coords = (station['lat'], station['lon'])
        distance_to_station = geodesic(target_waypoint, station_coords).miles
        if distance_to_station < min_distance:
            min_distance = distance_to_station
            nearest_station = station

    # Output the nearest fuel station details
    if nearest_station:
        print("Nearest Fuel Station After Desired Distance:")
        print(f"Name: {nearest_station.get('tags', {}).get('name', 'Unknown')}")
        print(f"Name: {nearest_station.get('tags', {}).get('addr:city', 'Unknown City')}")
        print(f"Location: {nearest_station['lat']}, {nearest_station['lon']}")
        print(f"Distance from Waypoint: {min_distance:.2f} miles")
        return nearest_station
    else:
        print("No fuel stations found within the specified radius.")
        return None
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
    print("num_fuel_stops",num_fuel_stops)
    # Sort truckstops by Retail Price in ascending order
    sorted_fuel_stops = fuel_prices_df.sort_values(by='Retail Price')
    
    # Initialize list to store details about each fuel stop
    fuel_stops = []
    total_fuel_cost = 0

    # Loop to select optimal stops based on fuel price
    initial_route=route_coordinates[0]
    for i in range(num_fuel_stops):
        
        stop = sorted_fuel_stops.iloc[i]
        # print("stop",stop)
        # print("initial_route",initial_route)
        # Calculate fuel needed for each stop and corresponding cost
        fuel_needed = VEHICLE_RANGE / FUEL_EFFICIENCY  # Gallons required per stop
        # print("fuel_needed",fuel_needed)
        if i==num_fuel_stops:
            # print("i",i)
            distance_moved=route_distance%(i-1)            
        else:
            distance_moved=500
        # print("distance_moved",distance_moved)
        coordinate = find_coordinate_after_distance(route_coordinates,initial_route, distance_moved)
        # print("coordinate",coordinate)
        initial_route=coordinate
        fuelstation=optimal_data(initial_route)
        # print("fuelstation",fuelstation)
        fuel_cost = fuel_needed * stop['Retail Price']
        total_fuel_cost += fuel_cost

        # Add fuel stop details to the list
        fuel_stop = {
            "Truckstop Name": stop['Truckstop Name'],
            "Address": stop['Address'],
            "City": stop['City'],
            "State": stop['State'],
            "Retail Price": stop['Retail Price'],
            "Fuel Cost": fuel_cost
        }
        fuel_stops.append(fuel_stop)

    return fuel_stops
def get_optimal_fuel_stops(route_distance,route_coordinates):
    # Calculate the required number of fuel stops along the route
    num_fuel_stops = int(route_distance // VEHICLE_RANGE)
    
    # Sort truckstops by Retail Price in ascending order
    sorted_fuel_stops = fuel_prices_df.sort_values(by='Retail Price')
    
    # Initialize list to store details about each fuel stop
    fuel_stops = []
    total_fuel_cost = 0

    # Loop to select optimal stops based on fuel price
    initial_route=route_coordinates[0]
    for i in range(num_fuel_stops):
        
        stop = sorted_fuel_stops.iloc[i]
        # Calculate fuel needed for each stop and corresponding cost
        fuel_needed = VEHICLE_RANGE / FUEL_EFFICIENCY  # Gallons required per stop
        fuel_cost = fuel_needed * stop['Retail Price']
        total_fuel_cost += fuel_cost

        # Add fuel stop details to the list
        fuel_stop = {
            "Truckstop Name": stop['Truckstop Name'],
            "Address": stop['Address'],
            "City": stop['City'],
            "State": stop['State'],
            "Retail Price": stop['Retail Price'],
            "Fuel Cost": fuel_cost,
            "Nearest Station":nearest_station
        }
        fuel_stops.append(fuel_stop)

    return fuel_stops

def calculate_fuel_cost(distance):
    gallons_needed = distance / FUEL_EFFICIENCY
    avg_fuel_price = fuel_prices_df['Retail Price'].mean()
    
    return gallons_needed * avg_fuel_price

def route_view(request):
    start = request.GET.get('start')
    end = request.GET.get('end')
    
    if not start or not end:
        return JsonResponse({'error': 'Start and end locations are required'}, status=400)

    distance, route_coordinates = get_route(start, end)
    optimal_stops_data = get_optimal_stops(distance,route_coordinates)
    # optimal_stops = get_optimal_fuel_stops(distance,route_coordinates)
    total_fuel_cost = calculate_fuel_cost(distance)

    
    return JsonResponse({
        'distance': distance,
        # 'fuel_stops': optimal_stops,
        'fuel_stops': optimal_stops_data,
        'total_fuel_cost': total_fuel_cost,
        'route_coordinates': route_coordinates
    })





















def address_view(request):
   # Load your CSV file
    # file_path = 'your_file.csv'  # Replace with your file path
    df = pd.read_csv(FUEL_PRICE_FILE)

    # Initialize the geocoder
    # geolocator = Nominatim(user_agent="geoapiExercises")
    # geocode = RateLimiter(geolocator.geocode, min_delay_seconds=2)
    geolocator = Nominatim(user_agent="geoapiExercises", domain="overpass-api.de/api/")
    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=2)

    # Add latitude and longitude columns
    df['location'] = df['Address'].apply(geocode)  # Replace 'address_column' with your actual column name
    df['latitude'] = df['location'].apply(lambda loc: loc.latitude if loc else None)
    df['longitude'] = df['location'].apply(lambda loc: loc.longitude if loc else None)

    # Drop the intermediate 'location' column
    df = df.drop(columns=['location'])

    # Save the results to a new CSV file
    output_path = 'output_with_lat_long.csv'
    df.to_csv(output_path, index=False)

    print("Latitude and Longitude added to the CSV file.")





























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
    # get_unique_city()
    df = pd.read_csv('./unique_cities.csv')
    # latitudes = []
    # longitudes = []
    df['Latitude'] = None
    df['Longitude'] = None
    for index, row in df.iterrows():
        try:
            city = f"{row['City']}"
            print(city)  
            # coords = geocode_address(city)
            coords = geocode_addresslocationiq(city)
            print(coords)        
            if coords:
                df.loc[df['City'] == city, 'Latitude'] = coords[0]
                df.loc[df['City'] == city, 'Longitude'] = coords[1]
                # latitudes.append(coords[0])
                # longitudes.append(coords[1])
            else:
                df.loc[df['City'] == city, 'Latitude'] = None
                df.loc[df['City'] == city, 'Longitude'] = None
                df.to_csv(output_file, index=False)
                return output_file
                # latitudes.append(None)
                # longitudes.append(None)
            time.sleep(1.5)
        except Exception as e:
            print(f"Error fetching coordinates for city: {city}. Error: {e}")
    # # df['latitude'] = latitudes
    # # df['longitude'] = longitudes
    
    # # Save the enriched CSV
    df.to_csv(output_file, index=False)
    return output_file

    # for index, city in unique_cities():
    #     print(index)
    #     address = f"{row['Address']}, {row['City']}, {row['State']}"
    #     coords = geocode_address(city)
    #     print(coords)
    #     if coords:
    #         latitudes.append(coords[0])
    #         longitudes.append(coords[1])
    #     else:
    #         latitudes.append(None)
    #         longitudes.append(None)
    # for index, row in df.iterrows():
    #     print(index)
    #     address = f"{row['Address']}, {row['City']}, {row['State']}"
    #     coords = geocode_address(address)
    #     print(coords)
    #     if coords:
    #         latitudes.append(coords[0])
    #         longitudes.append(coords[1])
    #     else:
    #         latitudes.append(None)
    #         longitudes.append(None)
    
    # df['latitude'] = latitudes
    # df['longitude'] = longitudes
    
    # # Save the enriched CSV
    # df.to_csv(output_file, index=False)
    # return output_file

def enrich_fuel_data_with_coordinates(request):
    # Path to the original CSV file    
    # Enrich the CSV and save it as a new file
    # get_unique_city_csv_path=get_unique_city()
    # enriched_csv_path = enrich_fuel_data(get_unique_city_csv_path)
    # get_unique_city_path=get_unique_city()
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
    
    # Convert merged DataFrame to CSV and write to response
    # df_merged.to_csv(path_or_buf=response, index=False)

    return response
