from rest_framework import serializers
from .models import User


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'phone', 'profile_picture', 'is_verified', 'role', 'bio', 'average_rating',
            'date_of_birth', 'address', 'home_address', 'workplace', 'workplace_address',
            'has_car', 'car_model', 'car_color', 'license_plate'
        ]
        read_only_fields = ['is_verified', 'average_rating']


class UserDetailSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'phone', 'profile_picture', 'bio', 'date_of_birth', 'address',
            'is_verified', 'role', 'average_rating', 'total_ratings',
            'workplace', 'home_address', 'home_latitude', 'home_longitude', 
            'workplace_address', 'workplace_latitude', 'workplace_longitude',
            'has_car', 'car_model', 'car_color', 'license_plate',
            'preferred_days', 'preferred_departure_times', 'preferred_music',
            'smoking_preference', 'ac_preference', 'chat_preference',
            'payment_methods'
        ]
        read_only_fields = ['is_verified', 'role', 'average_rating', 'total_ratings']


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'phone', 'profile_picture', 'bio', 
            'date_of_birth', 'address', 'home_address', 'home_latitude', 'home_longitude',
            'workplace', 'workplace_address', 'workplace_latitude', 'workplace_longitude',
            'has_car', 'car_model', 'car_color', 'license_plate',
            'preferred_days', 'preferred_departure_times', 'preferred_music',
            'smoking_preference', 'ac_preference', 'chat_preference',
            'payment_methods'
        ]
    
    def validate(self, data):
        # If user indicates they have a car, make sure car details are provided
        has_car = data.get('has_car', self.instance.has_car if self.instance else False)
        if has_car:
            car_model = data.get('car_model', self.instance.car_model if self.instance else '')
            car_color = data.get('car_color', self.instance.car_color if self.instance else '')
            license_plate = data.get('license_plate', self.instance.license_plate if self.instance else '')
            
            if not car_model or not car_color or not license_plate:
                raise serializers.ValidationError(
                    "Car model, color, and license plate are required if you have a car"
                )
                
        # Validate coordinates if provided
        home_lat = data.get('home_latitude')
        home_lng = data.get('home_longitude')
        
        if (home_lat is not None and home_lng is None) or (home_lat is None and home_lng is not None):
            raise serializers.ValidationError("Both home latitude and longitude must be provided together")
            
        workplace_lat = data.get('workplace_latitude')
        workplace_lng = data.get('workplace_longitude')
        
        if (workplace_lat is not None and workplace_lng is None) or (workplace_lat is None and workplace_lng is not None):
            raise serializers.ValidationError("Both workplace latitude and longitude must be provided together")
            
        return data


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    password_confirm = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'password_confirm',
            'first_name', 'last_name', 'phone'
        ]
        extra_kwargs = {
            'first_name': {'required': True},
            'last_name': {'required': True},
            'email': {'required': True}
        }
    
    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({"password_confirm": "Password fields don't match."})
        return data
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            phone=validated_data.get('phone')
        )
        
        return user


class UserRatingSerializer(serializers.Serializer):
    """Serializer for rating users"""
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(max_length=500, required=False, allow_blank=True)