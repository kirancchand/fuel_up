import requests
import pandas as pd
from django.http import JsonResponse
from geopy.distance import geodesic
import math
import requests
FUEL_PRICE_FILE = './fuel-prices-for-be-assessment.csv'
FUEL_EFFICIENCY = 10  
VEHICLE_RANGE = 500  

fuel_prices_df = pd.read_csv(FUEL_PRICE_FILE)



# def geocode_address(address):
#     url = 'https://nominatim.openstreetmap.org/search'
#     params = {
#         'q': address,
#         'format': 'json',
#         'limit': 1
#     }
#     response = requests.get(url, params=params)
#     if response.status_code == 200 and response.json():
#         result = response.json()[0]
#         print(result)
#         return (float(result['lat']), float(result['lon']))
#     return None

# def enrich_fuel_data_with_coordinates(csv_file):
#     df = pd.read_csv(csv_file)
#     latitudes = []
#     longitudes = []
    
#     for _, row in df.iterrows():
#         address = f"{row['Address']}, {row['City']}, {row['State']}"
#         coords = geocode_address(address)
#         if coords:
#             latitudes.append(coords[0])
#             longitudes.append(coords[1])
#         else:
#             latitudes.append(None)
#             longitudes.append(None)
    
#     df['latitude'] = latitudes
#     df['longitude'] = longitudes
#     df.to_csv(output_file, index=False)
#     return df
# fuel_prices_df = enrich_fuel_data_with_coordinates(FUEL_PRICE_FILE)

def get_route(start, end):
    api_key = '5b3ce3597851110001cf62481587fd80e7aa453b803bd839206cff9c'
    url = f'https://api.openrouteservice.org/v2/directions/driving-car?api_key={api_key}&start={start}&end={end}'
    
    # Coordinates for the start and end locations need to be passed in the correct format (longitude, latitude)
    # start_str = f"{start[1]},{start[0]}"  # Start: [latitude, longitude] -> API requires [longitude, latitude]
    # end_str = f"{end[1]},{end[0]}"        # End: [latitude, longitude] -> API requires [longitude, latitude]

    # # Include coordinates and API key in the GET request URL
    # params = {
    #     'api_key': api_key,
    #     'start': start_str,
    #     'end': end_str,
    #     'format': 'json'
    # }
    
    # Send the GET request to the routing API
    response = requests.get(url)
    route_data = response.json()
    # print(route_data)
    distance = route_data['features'][0]['properties']['summary']['distance'] / 1609.34  # convert meters to miles 2704 * 1.6 = 4351km
    # print(distance)
    coordinates = route_data['features'][0]['geometry']['coordinates']
    # print(coordinates)
    steps = route_data['features'][0]['properties']['segments'][0]['steps']
    route_coordinates = [(coord[1], coord[0]) for coord in coordinates]
    # print(route_coordinates)
    
    return distance, route_coordinates
# def haversine(coord1, coord2):
#     # Coordinates are in the form (lat, lon)
#     lat1, lon1 = coord1
#     lat2, lon2 = coord2
    
#     R = 3959.87433  # Radius of Earth in miles
#     lat1 = math.radians(lat1)
#     lon1 = math.radians(lon1)
#     lat2 = math.radians(lat2)
#     lon2 = math.radians(lon2)
    
#     dlon = lon2 - lon1
#     dlat = lat2 - lat1
    
#     a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
#     c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
#     return R * c 
# def get_optimal_fuel_stops(route_coordinates, max_stop_distance=10):
#     fuel_stops = []
#     print(route_coordinates)
#     for coord in route_coordinates:
#         # Find all fuel stations within max_stop_distance miles from the route
#         nearby_stations = []
#         for _, station in fuel_prices_df.iterrows():
#             # address = f"{row['Address']}, {row['City']}, {row['State']}"
#             # coords = geocode_address(address)
#             station_coord = (station['latitude'], station['longitude'])
#             if pd.notna(station_coord[0]) and pd.notna(station_coord[1]): 
#                 distance_to_route = haversine(coord, station_coord)
#                 if distance_to_route <= max_stop_distance:
#                     nearby_stations.append(station)
        
#         # Sort by price to get the most cost-effective station
#         if nearby_stations:
#             optimal_station = min(nearby_stations, key=lambda x: x['price'])
#             fuel_stops.append(optimal_station.to_dict())
    
#     return fuel_stops
def get_optimal_fuel_stops(route_distance):
    """
    Calculates optimal fuel stops along a route.
    
    :param route_distance: Total route distance in miles.
    :param fuel_prices_csv: Path to the CSV file with truckstop data and fuel prices.
    :param mpg: Vehicle miles per gallon.
    :param vehicle_range: Vehicle range on a full tank in miles.
    :return: Total fuel cost and list of optimal fuel stops with details.
    """
    # Load CSV file with truckstop data
    # fuel_prices_df = pd.read_csv(fuel_prices_csv)
    
    # Calculate the required number of fuel stops along the route
    num_fuel_stops = int(route_distance // VEHICLE_RANGE)
    
    # Sort truckstops by Retail Price in ascending order
    sorted_fuel_stops = fuel_prices_df.sort_values(by='Retail Price')
    
    # Initialize list to store details about each fuel stop
    fuel_stops = []
    total_fuel_cost = 0

    # Loop to select optimal stops based on fuel price
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
            "Fuel Cost": fuel_cost
        }
        fuel_stops.append(fuel_stop)

    # return total_fuel_cost, fuel_stops
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
    start_coords = tuple(map(float, start.split(',')))
    end_coords = tuple(map(float, end.split(',')))

    # distance, route_coordinates = get_route(start_coords, end_coords)
    distance, route_coordinates = get_route(start, end)
    # optimal_stops = get_optimal_fuel_stops(route_coordinates)
    optimal_stops = get_optimal_fuel_stops(distance)
    total_fuel_cost = calculate_fuel_cost(distance)

    # distance, steps = get_route(start, end)
    # route_coordinates = [(step['start_location']['coordinates'][1], step['start_location']['coordinates'][0]) for step in steps]
    # optimal_stops = get_optimal_fuel_stops(route_coordinates, max_fuel_stops)

    # optimal_stops = get_optimal_fuel_stops(distance)
    # total_fuel_cost = calculate_fuel_cost(distance)
    
    return JsonResponse({
        'distance': distance,
        'fuel_stops': optimal_stops,
        'total_fuel_cost': total_fuel_cost,
        'route_coordinates': route_coordinates
    })
