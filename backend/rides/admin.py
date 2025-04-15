from django.contrib import admin
from .models import Ride, RidePassenger, Location


@admin.register(Ride)
class RideAdmin(admin.ModelAdmin):
    list_display = ('id', 'driver', 'pickup_location', 'dropoff_location', 'departure_time', 'available_seats', 'status', 'created_at')
    list_filter = ('status', 'created_at', 'departure_time', 'recurring')
    search_fields = ('driver__username', 'pickup_location', 'dropoff_location', 'notes')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('driver',)
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('driver')


@admin.register(RidePassenger)
class RidePassengerAdmin(admin.ModelAdmin):
    list_display = ('id', 'ride', 'passenger', 'status', 'joined_at')
    list_filter = ('status', 'joined_at')
    search_fields = ('ride__id', 'passenger__username', 'pickup_note')
    raw_id_fields = ('ride', 'passenger')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('ride', 'passenger')


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'city', 'is_workplace', 'latitude', 'longitude')
    list_filter = ('is_workplace', 'city')
    search_fields = ('name', 'address', 'city')
