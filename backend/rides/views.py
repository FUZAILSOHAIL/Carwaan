from django.shortcuts import render
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import models
from django.db.models import F, ExpressionWrapper, FloatField, Q
from django.contrib.postgres.expressions import ArraySubquery
from .models import Ride, RidePassenger, Location
from .serializers import (
    RideSerializer, 
    RideCreateSerializer, 
    RidePassengerSerializer,
    LocationSerializer,
    JoinRideSerializer
)
from users.models import User
import math
from datetime import timedelta


class IsDriverOrAdmin(permissions.BasePermission):
    """Permission to check if user is a driver or admin"""
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.has_car or request.user.is_admin()
        )


class IsRideDriver(permissions.BasePermission):
    """Permission to check if user is the ride driver"""
    
    def has_object_permission(self, request, view, obj):
        return obj.driver == request.user


class IsRidePassenger(permissions.BasePermission):
    """Permission to check if user is a passenger in the ride"""
    
    def has_object_permission(self, request, view, obj):
        return RidePassenger.objects.filter(ride=obj, passenger=request.user).exists()


class LocationViewSet(viewsets.ModelViewSet):
    """ViewSet for location instances"""
    serializer_class = LocationSerializer
    queryset = Location.objects.all()
    
    def get_permissions(self):
        """Set custom permissions for different actions"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [permissions.IsAdminUser]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=['get'])
    def workplaces(self, request):
        """Get all workplace locations"""
        workplaces = Location.objects.filter(is_workplace=True)
        serializer = self.get_serializer(workplaces, many=True)
        return Response(serializer.data)


class RideViewSet(viewsets.ModelViewSet):
    """ViewSet for viewing and editing ride instances"""
    queryset = Ride.objects.all()
    
    def get_serializer_class(self):
        """Return appropriate serializer class"""
        if self.action == 'create':
            return RideCreateSerializer
        if self.action == 'join':
            return JoinRideSerializer
        return RideSerializer
    
    def get_permissions(self):
        """Set custom permissions for different actions"""
        if self.action == 'create':
            permission_classes = [permissions.IsAuthenticated]
        elif self.action in ['update', 'partial_update', 'destroy', 'cancel_ride', 'manage_passengers']:
            permission_classes = [IsRideDriver]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    @action(detail=True, methods=['post'])
    def join(self, request, pk=None):
        """Request to join a ride as a passenger"""
        ride = self.get_object()
        
        if ride.status != 'scheduled':
            return Response(
                {"error": "You can only join scheduled rides"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(data=request.data, context={'request': request, 'ride': ride})
        serializer.is_valid(raise_exception=True)
        passenger = serializer.save()
        
        # Return the passenger information
        response_serializer = RidePassengerSerializer(passenger)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def cancel_ride(self, request, pk=None):
        """Driver cancels a ride"""
        ride = self.get_object()
        
        if ride.status not in ['scheduled', 'in_progress']:
            return Response(
                {"error": "You can only cancel scheduled or in-progress rides"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        ride.status = 'cancelled'
        ride.save()
        
        serializer = self.get_serializer(ride)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def leave_ride(self, request, pk=None):
        """Passenger leaves a ride"""
        ride = self.get_object()
        passenger = get_object_or_404(RidePassenger, ride=ride, passenger=request.user)
        
        if ride.status != 'scheduled':
            return Response(
                {"error": "You can only leave a ride that hasn't started yet"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Delete the passenger entry
        passenger.delete()
        
        # Update available seats
        ride.update_available_seats()
        
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['post'])
    def start_ride(self, request, pk=None):
        """Driver starts the ride"""
        ride = self.get_object()
        
        if not request.user == ride.driver:
            return Response(
                {"error": "Only the driver can start this ride"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if ride.status != 'scheduled':
            return Response(
                {"error": "Only scheduled rides can be started"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        ride.status = 'in_progress'
        ride.save()
        
        serializer = self.get_serializer(ride)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def complete_ride(self, request, pk=None):
        """Mark a ride as completed"""
        ride = self.get_object()
        
        if not request.user == ride.driver:
            return Response(
                {"error": "Only the driver can complete this ride"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if ride.status != 'in_progress':
            return Response(
                {"error": "Only in-progress rides can be completed"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        ride.status = 'completed'
        ride.save()
        
        serializer = self.get_serializer(ride)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def manage_passengers(self, request, pk=None):
        """Driver manages passenger requests"""
        ride = self.get_object()
        passenger_id = request.data.get('passenger_id')
        action = request.data.get('action')  # 'confirm' or 'reject'
        
        if action not in ['confirm', 'reject']:
            return Response(
                {"error": "Action must be either 'confirm' or 'reject'"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        passenger_request = get_object_or_404(
            RidePassenger, id=passenger_id, ride=ride, status='pending'
        )
        
        if action == 'confirm':
            if ride.is_full():
                return Response(
                    {"error": "This ride is already full"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            passenger_request.status = 'confirmed'
            passenger_request.save()
            
            # Update available seats
            ride.update_available_seats()
        else:  # reject
            passenger_request.status = 'rejected'
            passenger_request.save()
        
        serializer = RidePassengerSerializer(passenger_request)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def my_offered_rides(self, request):
        """Get rides offered by the current user"""
        rides = Ride.objects.filter(driver=request.user)
        serializer = self.get_serializer(rides, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def my_joined_rides(self, request):
        """Get rides joined by the current user"""
        ride_passengers = RidePassenger.objects.filter(
            passenger=request.user, 
            status='confirmed'
        ).values_list('ride', flat=True)
        
        rides = Ride.objects.filter(id__in=ride_passengers)
        serializer = self.get_serializer(rides, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def available_rides(self, request):
        """Get all available rides that aren't full"""
        rides = Ride.objects.filter(
            status='scheduled',
            departure_time__gt=timezone.now(),
            available_seats__gt=0
        )
        
        # Exclude rides where the user is already a passenger or the driver
        user = request.user
        
        # Exclude rides where the user is the driver
        rides = rides.exclude(driver=user)
        
        # Exclude rides where the user has already requested to join
        user_joined_rides = RidePassenger.objects.filter(
            passenger=user
        ).values_list('ride', flat=True)
        rides = rides.exclude(id__in=user_joined_rides)
        
        serializer = self.get_serializer(rides, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def search_rides(self, request):
        """Search for rides based on advanced criteria with smart matching"""
        # Get basic parameters
        pickup = request.query_params.get('pickup')
        dropoff = request.query_params.get('dropoff')
        date = request.query_params.get('date')  # Format: YYYY-MM-DD
        workplace = request.query_params.get('workplace')
        
        # Get coordinates if available
        lat = request.query_params.get('lat')
        lng = request.query_params.get('lng')
        dest_lat = request.query_params.get('dest_lat')
        dest_lng = request.query_params.get('dest_lng')
        
        # Get preference filters
        time_flexibility = request.query_params.get('time_flexibility', 30)  # Minutes
        try:
            time_flexibility = int(time_flexibility)
        except (ValueError, TypeError):
            time_flexibility = 30
            
        # Smart time filtering - look for rides within the flexible time window
        departure_time = request.query_params.get('departure_time')  # Format: HH:MM
        
        # Base query
        rides = Ride.objects.filter(
            status='scheduled',
            available_seats__gt=0
        )
        
        # Apply date filter if provided
        if date:
            rides = rides.filter(departure_time__date=date)
            
            # Apply smart time filtering if provided
            if departure_time:
                try:
                    # Parse time in format HH:MM
                    hour, minute = map(int, departure_time.split(':'))
                    # Create base datetime with today's date
                    base_time = timezone.now().replace(
                        hour=hour, minute=minute, second=0, microsecond=0
                    )
                    
                    # Update with the requested date
                    year, month, day = map(int, date.split('-'))
                    base_time = base_time.replace(year=year, month=month, day=day)
                    
                    # Calculate time window
                    time_window_start = base_time - timedelta(minutes=time_flexibility)
                    time_window_end = base_time + timedelta(minutes=time_flexibility)
                    
                    # Filter rides within time window
                    rides = rides.filter(
                        departure_time__gte=time_window_start,
                        departure_time__lte=time_window_end
                    )
                except (ValueError, TypeError, IndexError):
                    # If time parsing fails, use date only
                    pass
        
        # Basic location filtering
        if pickup:
            rides = rides.filter(pickup_location__icontains=pickup)
        
        if dropoff:
            rides = rides.filter(dropoff_location__icontains=dropoff)
            
        # Workplace filtering
        if workplace:
            rides = rides.filter(
                Q(pickup_location__icontains=workplace) | 
                Q(dropoff_location__icontains=workplace) |
                Q(driver__workplace__icontains=workplace)
            )
            
        # Exclude rides by/with the current user
        user = request.user
        rides = rides.exclude(driver=user)
        
        user_joined_rides = RidePassenger.objects.filter(
            passenger=user
        ).values_list('ride', flat=True)
        rides = rides.exclude(id__in=user_joined_rides)
        
        # Advanced matching with coordinates
        if lat and lng and dest_lat and dest_lng:
            try:
                lat = float(lat)
                lng = float(lng)
                dest_lat = float(dest_lat)
                dest_lng = float(dest_lng)
                
                # Score and sort rides
                scored_rides = []
                for ride in rides:
                    match_score = ride.match_score(
                        user, lat, lng, dest_lat, dest_lng
                    )
                    scored_rides.append((ride, match_score))
                
                # Sort by score (highest first)
                scored_rides.sort(key=lambda x: x[1], reverse=True)
                
                # Return serialized rides with scores
                result = []
                for ride, score in scored_rides:
                    ride_data = self.get_serializer(ride).data
                    ride_data['match_score'] = score
                    result.append(ride_data)
                
                return Response(result)
            
            except (ValueError, TypeError):
                # Fall back to basic sorting if coordinate parsing fails
                pass
        
        # Return rides in default order if no advanced matching
        serializer = self.get_serializer(rides, many=True)
        return Response(serializer.data)
        
    @action(detail=False, methods=['get'])
    def colleagues_rides(self, request):
        """Get rides offered by colleagues (users with the same workplace)"""
        user = request.user
        
        if not user.workplace:
            return Response(
                {"error": "You need to set your workplace to see colleagues' rides"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Find users with the same workplace
        colleagues = User.objects.filter(workplace=user.workplace).exclude(id=user.id)
        
        # Get rides offered by colleagues
        rides = Ride.objects.filter(
            driver__in=colleagues,
            status='scheduled',
            departure_time__gt=timezone.now(),
            available_seats__gt=0
        )
        
        # Exclude rides where the user has already requested to join
        user_joined_rides = RidePassenger.objects.filter(
            passenger=user
        ).values_list('ride', flat=True)
        rides = rides.exclude(id__in=user_joined_rides)
        
        serializer = self.get_serializer(rides, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def recommended_rides(self, request):
        """Get personalized ride recommendations based on user preferences and history"""
        user = request.user
        
        # Basic query: scheduled rides with available seats in the future
        rides = Ride.objects.filter(
            status='scheduled',
            departure_time__gt=timezone.now(),
            available_seats__gt=0
        )
        
        # Exclude rides where the user is already a passenger or the driver
        rides = rides.exclude(driver=user)
        user_joined_rides = RidePassenger.objects.filter(
            passenger=user
        ).values_list('ride', flat=True)
        rides = rides.exclude(id__in=user_joined_rides)
        
        # Extract request parameters
        lat = request.query_params.get('lat')
        lng = request.query_params.get('lng')
        dest_lat = request.query_params.get('dest_lat')
        dest_lng = request.query_params.get('dest_lng')
        
        # If we have valid coordinates, prioritize by proximity
        if lat and lng and dest_lat and dest_lng:
            try:
                lat = float(lat)
                lng = float(lng)
                dest_lat = float(dest_lat)
                dest_lng = float(dest_lng)
                
                # Calculate scores for each ride (we'll do this in Python for flexibility)
                scored_rides = []
                for ride in rides:
                    match_score = ride.match_score(
                        user, lat, lng, dest_lat, dest_lng
                    )
                    scored_rides.append((ride, match_score))
                
                # Sort by score (highest first)
                scored_rides.sort(key=lambda x: x[1], reverse=True)
                
                # Return serialized rides with scores
                result = []
                for ride, score in scored_rides:
                    ride_data = self.get_serializer(ride).data
                    ride_data['match_score'] = score
                    result.append(ride_data)
                
                return Response(result)
            
            except (ValueError, TypeError):
                # If coordinate parsing fails, fall back to basic filtering
                pass
        
        # Workplace-based matching
        if user.workplace:
            # First prioritize colleagues' rides (from same workplace)
            colleague_rides = rides.filter(
                driver__workplace=user.workplace
            )
            
            # Then rides to/from user's workplace
            workplace_rides = rides.filter(
                Q(pickup_location__icontains=user.workplace) | 
                Q(dropoff_location__icontains=user.workplace)
            ).exclude(id__in=colleague_rides.values_list('id', flat=True))
            
            # Combine and add remaining rides
            other_rides = rides.exclude(
                id__in=colleague_rides.values_list('id', flat=True)
            ).exclude(
                id__in=workplace_rides.values_list('id', flat=True)
            )
            
            # Combine the querysets in priority order
            rides = list(colleague_rides) + list(workplace_rides) + list(other_rides)
            serializer = self.get_serializer(rides, many=True)
            return Response(serializer.data)
            
        # If no workplace preference, just return all available rides
        serializer = self.get_serializer(rides, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def invite_connections(self, request, pk=None):
        """Invite colleagues or friends to join this ride"""
        ride = self.get_object()
        
        # Verify the user is the driver of this ride
        if request.user != ride.driver:
            return Response(
                {"error": "Only the driver can invite people to this ride"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get the list of user IDs to invite
        user_ids = request.data.get('user_ids', [])
        friend_group = request.data.get('friend_group', '')
        department = request.data.get('department', '')
        message = request.data.get('message', '')
        
        invited = []
        errors = []
        
        # Process individual invitations
        if user_ids:
            for user_id in user_ids:
                try:
                    user = User.objects.get(id=user_id)
                    
                    # Check if user is already in the ride
                    if RidePassenger.objects.filter(ride=ride, passenger=user).exists():
                        errors.append(f"{user.full_name} is already in this ride")
                        continue
                    
                    # Determine relationship type
                    relationship = 'other'
                    if user.workplace and request.user.workplace and user.workplace == request.user.workplace:
                        relationship = 'colleague'
                    elif request.user.connections.filter(id=user.id).exists():
                        relationship = 'friend'
                    
                    # Create a pending ride passenger entry
                    passenger = RidePassenger.objects.create(
                        ride=ride,
                        passenger=user,
                        status='pending',
                        invited_by=request.user,
                        relationship=relationship
                    )
                    
                    invited.append(user.full_name)
                    
                    # TODO: Send notification to user
                    
                except User.DoesNotExist:
                    errors.append(f"User with ID {user_id} not found")
        
        # Process friend group invitation
        if friend_group and hasattr(request.user, 'friend_groups') and request.user.friend_groups:
            try:
                group_members = request.user.friend_groups.get(friend_group, [])
                if group_members:
                    for user_id in group_members:
                        try:
                            user = User.objects.get(id=user_id)
                            
                            # Skip if already invited
                            if RidePassenger.objects.filter(ride=ride, passenger=user).exists():
                                continue
                                
                            # Create invitation
                            RidePassenger.objects.create(
                                ride=ride,
                                passenger=user,
                                status='pending',
                                invited_by=request.user,
                                relationship='friend'
                            )
                            
                            invited.append(user.full_name)
                            # TODO: Send notification
                            
                        except User.DoesNotExist:
                            continue
            except (KeyError, AttributeError):
                errors.append(f"Friend group '{friend_group}' not found")
        
        # Process department invitation (for workplace rides)
        if department and ride.is_workplace_ride:
            department_colleagues = User.objects.filter(
                workplace=request.user.workplace,
                department=department
            ).exclude(id=request.user.id)
            
            for colleague in department_colleagues:
                # Skip if already invited
                if RidePassenger.objects.filter(ride=ride, passenger=colleague).exists():
                    continue
                    
                # Create invitation
                RidePassenger.objects.create(
                    ride=ride,
                    passenger=colleague,
                    status='pending',
                    invited_by=request.user,
                    relationship='colleague'
                )
                
                invited.append(colleague.full_name)
                # TODO: Send notification
        
        return Response({
            "invited": invited,
            "errors": errors,
            "message": f"Successfully invited {len(invited)} people to the ride"
        })
    
    @action(detail=False, methods=['get'])
    def friend_group_rides(self, request):
        """Get rides shared with specific friend groups"""
        user = request.user
        friend_group = request.query_params.get('group')
        
        if not friend_group:
            return Response(
                {"error": "You must specify a friend group"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Find all rides that are marked with this friend group
        rides = Ride.objects.filter(
            status='scheduled',
            departure_time__gt=timezone.now(),
            available_seats__gt=0,
            friend_group=friend_group
        )
        
        # Add rides where the driver is part of requested friend group
        if hasattr(user, 'friend_groups') and user.friend_groups:
            try:
                group_members = user.friend_groups.get(friend_group, [])
                if group_members:
                    # Find rides offered by members of this group
                    group_rides = Ride.objects.filter(
                        driver_id__in=group_members,
                        status='scheduled',
                        departure_time__gt=timezone.now(),
                        available_seats__gt=0
                    )
                    # Combine with other rides
                    rides = rides | group_rides
            except (KeyError, AttributeError):
                pass
        
        # Exclude rides where user is already a passenger or driver
        rides = rides.exclude(driver=user)
        user_joined_rides = RidePassenger.objects.filter(
            passenger=user
        ).values_list('ride', flat=True)
        rides = rides.exclude(id__in=user_joined_rides)
        
        serializer = self.get_serializer(rides, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def social_connections_rides(self, request):
        """Get rides from connected users (friends or colleagues)"""
        user = request.user
        
        # Get IDs of all connected users
        connection_ids = user.connections.values_list('id', flat=True)
        
        # Add colleagues if workplace is set
        if user.workplace:
            colleague_ids = User.objects.filter(
                workplace=user.workplace
            ).exclude(id=user.id).values_list('id', flat=True)
            
            # Combine connection IDs
            all_connections = list(connection_ids) + list(colleague_ids)
            # Remove duplicates
            all_connections = list(set(all_connections))
        else:
            all_connections = list(connection_ids)
        
        # Find rides from connections
        rides = Ride.objects.filter(
            driver_id__in=all_connections,
            status='scheduled',
            departure_time__gt=timezone.now(),
            available_seats__gt=0
        )
        
        # Also include rides explicitly shared with friend groups user belongs to
        if hasattr(user, 'friend_groups') and user.friend_groups:
            user_groups = list(user.friend_groups.keys())
            if user_groups:
                group_rides = Ride.objects.filter(
                    friend_group__in=user_groups,
                    status='scheduled',
                    departure_time__gt=timezone.now(),
                    available_seats__gt=0
                )
                # Combine with connection rides
                rides = rides | group_rides
                
        # Exclude rides where user is already a passenger or driver
        rides = rides.exclude(driver=user)
        user_joined_rides = RidePassenger.objects.filter(
            passenger=user
        ).values_list('ride', flat=True)
        rides = rides.exclude(id__in=user_joined_rides)
        
        # Sort by departure time
        rides = rides.order_by('departure_time')
        
        serializer = self.get_serializer(rides, many=True)
        return Response(serializer.data)


class RidePassengerViewSet(viewsets.ModelViewSet):
    """ViewSet for ride passengers"""
    serializer_class = RidePassengerSerializer
    queryset = RidePassenger.objects.all()
    
    def get_permissions(self):
        """Set custom permissions for different actions"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """Limit passengers to those visible to the current user"""
        user = self.request.user
        
        # Admin can see all
        if user.is_admin():
            return RidePassenger.objects.all()
        
        # Users can see passengers for rides they drive or are passengers in
        return RidePassenger.objects.filter(
            models.Q(ride__driver=user) | models.Q(passenger=user)
        )
    
    @action(detail=False, methods=['get'])
    def my_ride_requests(self, request):
        """Get all ride requests made by the current user"""
        requests = RidePassenger.objects.filter(passenger=request.user)
        serializer = self.get_serializer(requests, many=True)
        return Response(serializer.data)
        
    @action(detail=False, methods=['get'])
    def pending_requests_for_my_rides(self, request):
        """Get all pending ride requests for rides offered by the current user"""
        requests = RidePassenger.objects.filter(
            ride__driver=request.user,
            status='pending'
        )
        serializer = self.get_serializer(requests, many=True)
        return Response(serializer.data)
