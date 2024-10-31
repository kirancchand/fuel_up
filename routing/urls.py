from django.urls import path
from .views import route_view,enrich_fuel_data_with_coordinates,get_unique_city,mergecsv

urlpatterns = [
    path('route/', route_view, name='route'),
    path('enrich/', enrich_fuel_data_with_coordinates, name='enrich'),
    path('get_unique_city/', get_unique_city, name='get_unique_city'),
    path('mergecsv/', mergecsv, name='mergecsv'),
]
