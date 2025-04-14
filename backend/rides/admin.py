from django.contrib import admin
from .models import Ride, RideRequest, Location


@admin.register(Ride)
class RideAdmin(admin.ModelAdmin):
    list_display = ('id', 'rider', 'driver', 'pickup_location', 'dropoff_location', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('pickup_location', 'dropoff_location', 'rider__username', 'driver__username')
    raw_id_fields = ('rider', 'driver')
    date_hierarchy = 'created_at'


@admin.register(RideRequest)
class RideRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'ride', 'requested_by', 'request_time', 'status')
    list_filter = ('status', 'request_time')
    search_fields = ('ride__id', 'requested_by__username')
    raw_id_fields = ('ride', 'requested_by')
    date_hierarchy = 'request_time'


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'latitude', 'longitude')
    search_fields = ('name',)
