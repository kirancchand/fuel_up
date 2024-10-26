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

def get_route(start, end):
    api_key = '<api key>'
    url = f'https://api.openrouteservice.org/v2/directions/driving-car?api_key={api_key}&start={start}&end={end}'
    

    
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
def get_optimal_fuel_stops(route_distance):
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
    optimal_stops = get_optimal_fuel_stops(distance)
    total_fuel_cost = calculate_fuel_cost(distance)

    
    return JsonResponse({
        'distance': distance,
        'fuel_stops': optimal_stops,
        'total_fuel_cost': total_fuel_cost,
        'route_coordinates': route_coordinates
    })
