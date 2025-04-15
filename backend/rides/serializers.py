from rest_framework import serializers
from .models import Ride, RidePassenger, Location
from users.models import User
from users.serializers import UserSerializer
from django.utils import timezone


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ['id', 'name', 'address', 'latitude', 'longitude', 
                  'is_workplace', 'is_landmark', 'is_university']


class RidePassengerSerializer(serializers.ModelSerializer):
    passenger_name = serializers.ReadOnlyField(source='passenger.full_name')
    passenger_rating = serializers.ReadOnlyField(source='passenger.average_rating')
    passenger_picture = serializers.SerializerMethodField()
    
    class Meta:
        model = RidePassenger
        fields = [
            'id', 'ride', 'passenger', 'joined_at', 'status', 'pickup_note',
            'passenger_name', 'passenger_rating', 'passenger_picture'
        ]
        read_only_fields = ['joined_at']
    
    def get_passenger_picture(self, obj):
        if obj.passenger.profile_picture:
            return obj.passenger.profile_picture.url
        return None


class RideSerializer(serializers.ModelSerializer):
    driver = UserSerializer(read_only=True)
    driver_rating = serializers.ReadOnlyField(source='driver.average_rating')
    passengers = RidePassengerSerializer(source='ridepassenger_set', many=True, read_only=True)
    is_full = serializers.SerializerMethodField()
    match_score = serializers.FloatField(read_only=True, required=False)
    available_seats_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Ride
        fields = [
            'id', 'driver', 'driver_rating', 'departure_time', 'pickup_location', 'dropoff_location',
            'total_seats', 'available_seats', 'available_seats_display',
            'status', 'recurring', 'notes', 'route_description', 'price_per_seat', 'passengers', 'is_full',
            'pickup_latitude', 'pickup_longitude', 'dropoff_latitude', 'dropoff_longitude',
            'time_flexibility_minutes', 'is_workplace_ride', 'recurring_days',
            'comfort_features', 'average_rating', 'match_score'
        ]
        read_only_fields = ['driver', 'available_seats', 'status', 'average_rating']
        
    def get_available_seats_display(self, obj):
        return f"{obj.available_seats}/{obj.total_seats}"
        
    def get_is_full(self, obj):
        return obj.is_full()


class RideCreateSerializer(serializers.ModelSerializer):
    # Define explicitly to handle nested validation
    pickup_latitude = serializers.FloatField(required=False, allow_null=True)
    pickup_longitude = serializers.FloatField(required=False, allow_null=True)
    dropoff_latitude = serializers.FloatField(required=False, allow_null=True)
    dropoff_longitude = serializers.FloatField(required=False, allow_null=True)
    recurring_days = serializers.ListField(child=serializers.CharField(), required=False, allow_null=True)
    comfort_features = serializers.JSONField(required=False, allow_null=True)
    
    class Meta:
        model = Ride
        fields = [
            'departure_time', 'pickup_location', 'dropoff_location',
            'total_seats', 'recurring', 'notes', 'route_description', 'price_per_seat',
            'pickup_latitude', 'pickup_longitude', 'dropoff_latitude', 
            'dropoff_longitude', 'time_flexibility_minutes', 'is_workplace_ride', 
            'recurring_days', 'comfort_features'
        ]
    
    def validate_departure_time(self, value):
        """Validate that departure time is in the future"""
        if value < timezone.now():
            raise serializers.ValidationError("Departure time must be in the future")
        return value
    
    def validate_total_seats(self, value):
        """Validate that total seats is at least 1"""
        if value < 1:
            raise serializers.ValidationError("Total seats must be at least 1")
        return value

    def validate_price_per_seat(self, value):
        """Validate that price is non-negative"""
        if value < 0:
            raise serializers.ValidationError("Price cannot be negative")
        return value
        
    def validate(self, data):
        """Validate coordinate data"""
        # If any coordinates are provided, all should be provided
        pickup_lat = data.get('pickup_latitude')
        pickup_lng = data.get('pickup_longitude')
        dropoff_lat = data.get('dropoff_latitude')
        dropoff_lng = data.get('dropoff_longitude')
        
        if any([pickup_lat, pickup_lng, dropoff_lat, dropoff_lng]) and not all([pickup_lat, pickup_lng, dropoff_lat, dropoff_lng]):
            raise serializers.ValidationError("If providing coordinates, all coordinates are required")
            
        # Validate recurring ride data
        recurring = data.get('recurring')
        recurring_days = data.get('recurring_days')
        
        if recurring and not recurring_days:
            raise serializers.ValidationError("Recurring rides must specify recurring days")
            
        # Make sure pickup and dropoff locations are not the same
        if data['pickup_location'] == data['dropoff_location']:
            raise serializers.ValidationError("Pickup and dropoff locations cannot be the same")
        
        # Validate comfort_features format if provided
        comfort_features = data.get('comfort_features')
        if comfort_features:
            # Check if it's a proper JSON object
            if not isinstance(comfort_features, dict):
                raise serializers.ValidationError("Comfort features must be a valid JSON object")
                
            # Check for valid keys
            valid_keys = {'smoking_allowed', 'has_ac', 'chat_level', 'music_genres'}
            invalid_keys = set(comfort_features.keys()) - valid_keys
            
            if invalid_keys:
                raise serializers.ValidationError(f"Invalid comfort feature keys: {', '.join(invalid_keys)}")
            
            # Validate chat_level if provided
            if 'chat_level' in comfort_features:
                valid_levels = {'quiet', 'moderate', 'chatty'}
                if comfort_features['chat_level'] not in valid_levels:
                    raise serializers.ValidationError(
                        f"Invalid chat level. Must be one of: {', '.join(valid_levels)}"
                    )
                    
            # Validate music_genres if provided
            if 'music_genres' in comfort_features:
                if not isinstance(comfort_features['music_genres'], list):
                    raise serializers.ValidationError("Music genres must be a list")
        
        return data
    
    def create(self, validated_data):
        """Create a new ride with the current user as driver"""
        user = self.context['request'].user
        
        # Check if user has a car
        if not user.has_car:
            raise serializers.ValidationError("You must have a car to offer rides")
        
        # Create the ride with the current user as driver
        ride = Ride.objects.create(
            driver=user,
            available_seats=validated_data['total_seats'],
            **validated_data
        )
        
        return ride


class RideUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ride
        fields = [
            'departure_time', 'pickup_location', 'dropoff_location',
            'total_seats', 'status', 'notes', 'route_description',
            'price_per_seat', 'pickup_latitude', 'pickup_longitude',
            'dropoff_latitude', 'dropoff_longitude', 'recurring',
            'recurring_days', 'time_flexibility_minutes', 'is_workplace_ride',
            'comfort_features'
        ]


class JoinRideSerializer(serializers.ModelSerializer):
    pickup_note = serializers.CharField(required=False, allow_blank=True, max_length=255)
    
    class Meta:
        model = RidePassenger
        fields = ['pickup_note']
    
    def validate(self, data):
        """Validate that the user can join the ride"""
        user = self.context['request'].user
        ride = self.context['ride']
        
        # Check if ride is full
        if ride.is_full():
            raise serializers.ValidationError("This ride is full")
        
        # Check if user is already a passenger
        if RidePassenger.objects.filter(ride=ride, passenger=user).exists():
            raise serializers.ValidationError("You already requested to join this ride")
            
        # Check if user is the driver
        if ride.driver == user:
            raise serializers.ValidationError("You are the driver of this ride")
            
        return data
    
    def create(self, validated_data):
        """Create a new ride passenger for the user and the given ride"""
        user = self.context['request'].user
        ride = self.context['ride']
        
        # Create the ride passenger
        passenger = RidePassenger.objects.create(
            ride=ride,
            passenger=user,
            status='pending',
            **validated_data
        )
        
        return passenger


class RidePassengerCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RidePassenger
        fields = ['ride', 'pickup_note']
        
    def validate_ride(self, ride):
        # Check if the ride is already full
        if ride.is_full():
            raise serializers.ValidationError("This ride is already full")
            
        # Check if user is already a passenger in this ride
        user = self.context['request'].user
        if RidePassenger.objects.filter(ride=ride, passenger=user).exists():
            raise serializers.ValidationError("You are already a passenger in this ride")
            
        # Check if user is the driver
        if ride.driver == user:
            raise serializers.ValidationError("You cannot join your own ride as a passenger")
            
        return ride


class RidePassengerUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RidePassenger
        fields = ['status', 'pickup_note']


class RideRatingSerializer(serializers.Serializer):
    """Serializer for rating rides"""
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(max_length=500, required=False, allow_blank=True)