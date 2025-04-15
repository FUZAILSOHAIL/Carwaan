from django.db import models
from django.conf import settings
from core.models import TimeStampedModel
from users.models import User
import math
from django.utils import timezone


class Location(models.Model):
    """Model for common locations like universities, workplaces, and landmarks"""

    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255, blank=True, null=True)
    latitude = models.FloatField()
    longitude = models.FloatField()
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    is_workplace = models.BooleanField(default=False)
    is_landmark = models.BooleanField(default=False)
    is_university = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class Ride(TimeStampedModel):
    """Model for carpooling rides among colleagues and friends"""

    STATUS_CHOICES = (
        ("scheduled", "Scheduled"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    )

    RIDE_TYPE_CHOICES = (
        ("commute", "Work Commute"),
        ("event", "Event/Meeting"),
        ("social", "Social Gathering"),
        ("errand", "Errand Run"),
        ("other", "Other"),
    )

    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="offered_rides"
    )
    departure_time = models.DateTimeField(default=timezone.now)
    pickup_location = models.CharField(max_length=255)
    dropoff_location = models.CharField(max_length=255)
    total_seats = models.PositiveIntegerField(default=2)
    available_seats = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="scheduled"
    )
    notes = models.TextField(blank=True)

    # Enhanced fields for colleague/friend carpooling
    ride_type = models.CharField(
        max_length=20, choices=RIDE_TYPE_CHOICES, default="commute"
    )
    route_description = models.TextField(
        blank=True, help_text="Description of route, landmarks, etc."
    )
    price_per_seat = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    cost_splitting = models.BooleanField(
        default=True, help_text="Whether to split costs among passengers"
    )

    # Social aspects for colleague/friend carpooling
    is_private = models.BooleanField(
        default=False, help_text="If true, only visible to connections/colleagues"
    )
    friend_group = models.CharField(
        max_length=100, blank=True, help_text="Specific friend group for this ride"
    )
    workplace_department = models.CharField(
        max_length=100, blank=True, help_text="Specific department for workplace rides"
    )

    # Coordinates for calculating distance
    pickup_latitude = models.FloatField(null=True, blank=True)
    pickup_longitude = models.FloatField(null=True, blank=True)
    dropoff_latitude = models.FloatField(null=True, blank=True)
    dropoff_longitude = models.FloatField(null=True, blank=True)

    # Ride preferences
    recurring = models.BooleanField(
        default=False, help_text="Is this a recurring ride?"
    )
    recurring_days = models.JSONField(
        null=True,
        blank=True,
        help_text="Days on which this ride recurs [0-6] where 0 is Monday",
    )

    time_flexibility_minutes = models.PositiveIntegerField(
        default=10, help_text="Flexibility in departure time (minutes)"
    )

    is_workplace_ride = models.BooleanField(
        default=False, help_text="Is this ride to/from a workplace?"
    )

    # Comfort features
    comfort_features = models.JSONField(
        null=True, blank=True, help_text="Features like AC, music, smoking policy, etc."
    )

    # Rating
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    total_ratings = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Ride from {self.pickup_location} to {self.dropoff_location} at {self.departure_time}"

    def is_full(self):
        """Check if the ride is full"""
        return self.available_seats <= 0

    def update_available_seats(self):
        """Update the available seats based on confirmed passengers"""
        confirmed_passengers_count = RidePassenger.objects.filter(
            ride=self, status="confirmed"
        ).count()

        self.available_seats = max(0, self.total_seats - confirmed_passengers_count)
        self.save()

    def update_rating(self, new_rating):
        """Update average rating with a new rating (1-5)"""
        if new_rating < 1 or new_rating > 5:
            raise ValueError("Rating must be between 1 and 5")

        if self.total_ratings == 0:
            self.average_rating = new_rating
        else:
            total = self.average_rating * self.total_ratings
            self.average_rating = (total + new_rating) / (self.total_ratings + 1)

        self.total_ratings += 1
        self.save()

    def calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two points using Haversine formula"""
        # Earth radius in kilometers
        R = 6371.0

        # Convert to radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)

        # Differences
        dlon = lon2_rad - lon1_rad
        dlat = lat2_rad - lat1_rad

        # Haversine formula
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = R * c

        return distance

    def match_score(self, user, user_lat, user_lng, user_dest_lat, user_dest_lng):
        """Calculate a match score for a user and this ride based on multiple factors"""
        score = 0.0

        # Base score starts at 50
        score = 50.0

        # 1. Distance matching (contributes up to 40 points)
        if (
            self.pickup_latitude
            and self.pickup_longitude
            and self.dropoff_latitude
            and self.dropoff_longitude
        ):
            # Calculate pickup distance (10km or less is ideal)
            pickup_distance = self.calculate_distance(
                user_lat, user_lng, self.pickup_latitude, self.pickup_longitude
            )
            # Calculate dropoff distance (10km or less is ideal)
            dropoff_distance = self.calculate_distance(
                user_dest_lat,
                user_dest_lng,
                self.dropoff_latitude,
                self.dropoff_longitude,
            )

            # Score based on pickup distance (closer is better)
            if pickup_distance <= 1:  # Within 1km
                score += 20
            elif pickup_distance <= 3:  # Within 3km
                score += 15
            elif pickup_distance <= 5:  # Within 5km
                score += 10
            elif pickup_distance <= 10:  # Within 10km
                score += 5

            # Score based on dropoff distance (closer is better)
            if dropoff_distance <= 1:  # Within 1km
                score += 20
            elif dropoff_distance <= 3:  # Within 3km
                score += 15
            elif dropoff_distance <= 5:  # Within 5km
                score += 10
            elif dropoff_distance <= 10:  # Within 10km
                score += 5

        # 2. Time matching (contributes up to 20 points)
        if (
            hasattr(user, "preferred_departure_times")
            and user.preferred_departure_times
        ):
            # Convert ride departure time to HH:MM format
            ride_hour = self.departure_time.hour
            ride_minute = self.departure_time.minute

            # Check if ride time is within user's preferred times
            for time_range in user.preferred_departure_times:
                try:
                    # Parse time range as "HH:MM-HH:MM"
                    start_time, end_time = time_range.split("-")
                    start_hour, start_minute = map(int, start_time.split(":"))
                    end_hour, end_minute = map(int, end_time.split(":"))

                    # Convert to minutes for easier comparison
                    ride_time_minutes = ride_hour * 60 + ride_minute
                    start_time_minutes = start_hour * 60 + start_minute
                    end_time_minutes = end_hour * 60 + end_minute

                    # Check if ride time is within this preferred range
                    if start_time_minutes <= ride_time_minutes <= end_time_minutes:
                        score += 20
                        break
                except (ValueError, IndexError):
                    continue

        # 3. User rating matching (contributes up to 10 points)
        # Higher ratings are better matches
        if self.driver.average_rating > 0:
            driver_rating = float(self.driver.average_rating)
            score += min(10, driver_rating * 2)  # Up to 10 points for a 5-star driver

        # 4. Preferences matching (contributes up to 20 points)
        preference_score = 0

        # Check comfort features
        if (
            self.comfort_features
            and hasattr(user, "smoking_preference")
            and hasattr(user, "ac_preference")
            and hasattr(user, "chat_preference")
        ):
            # Smoking preference
            if user.smoking_preference != "no_preference":
                if (
                    user.smoking_preference == "no_smoking"
                    and self.comfort_features.get("smoking_allowed", False) == False
                ):
                    preference_score += 5
                elif (
                    user.smoking_preference == "smoking_allowed"
                    and self.comfort_features.get("smoking_allowed", False) == True
                ):
                    preference_score += 5
            else:
                preference_score += 3

            # AC preference
            if user.ac_preference != "no_preference":
                if (
                    user.ac_preference == "ac_required"
                    and self.comfort_features.get("has_ac", False) == True
                ):
                    preference_score += 5
                elif (
                    user.ac_preference == "no_ac"
                    and self.comfort_features.get("has_ac", False) == False
                ):
                    preference_score += 5
            else:
                preference_score += 3

            # Chat preference
            if user.chat_preference != "no_preference":
                if user.chat_preference == "chatty" and self.comfort_features.get(
                    "chat_level", "moderate"
                ) in ["chatty", "moderate"]:
                    preference_score += 5
                elif user.chat_preference == "quiet" and self.comfort_features.get(
                    "chat_level", "moderate"
                ) in ["quiet", "moderate"]:
                    preference_score += 5
            else:
                preference_score += 3

            # Music preference
            if (
                hasattr(user, "preferred_music")
                and user.preferred_music
                and "music_genres" in self.comfort_features
            ):
                ride_genres = self.comfort_features.get("music_genres", [])
                user_genres = user.preferred_music

                # Check for overlap in music preferences
                if set(user_genres) & set(ride_genres):
                    preference_score += 5

        # Add preference score to total (max 20)
        score += min(20, preference_score)

        # 5. Additional bonuses for special cases (up to 10 bonus points)

        # Bonus for workplace rides if user has workplace set
        if self.is_workplace_ride and hasattr(user, "workplace") and user.workplace:
            if (
                user.workplace.lower() in self.pickup_location.lower()
                or user.workplace.lower() in self.dropoff_location.lower()
            ):
                score += 5

        # Bonus for colleague rides (driver from same workplace)
        if (
            hasattr(user, "workplace")
            and user.workplace
            and hasattr(self.driver, "workplace")
            and self.driver.workplace
        ):
            if user.workplace.lower() == self.driver.workplace.lower():
                score += 5

        # Bonus for recurring rides that match user's preferred days
        if (
            self.recurring
            and self.recurring_days
            and hasattr(user, "preferred_days")
            and user.preferred_days
        ):
            # Convert to sets for intersection
            ride_days = set(self.recurring_days)
            user_days = set(user.preferred_days)

            # Check overlap
            if ride_days & user_days:
                score += len(ride_days & user_days)  # 1 point per matching day

        # Cap the score at 100
        return min(100, score)


class RidePassenger(TimeStampedModel):
    """Model for passengers joining rides among colleagues and friends"""

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
    )

    RELATIONSHIP_TYPE = (
        ("colleague", "Colleague"),
        ("friend", "Friend"),
        ("family", "Family Member"),
        ("acquaintance", "Acquaintance"),
        ("other", "Other"),
    )

    ride = models.ForeignKey(Ride, on_delete=models.CASCADE)
    passenger = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="joined_rides"
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    pickup_note = models.CharField(
        max_length=255, blank=True, help_text="Special instructions for pickup"
    )

    # Enhanced fields for colleague/friend carpooling
    relationship = models.CharField(
        max_length=20,
        choices=RELATIONSHIP_TYPE,
        default="colleague",
        help_text="Relationship with the driver",
    )
    contribution_amount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0.00,
        help_text="Amount contributed to trip costs",
    )
    has_contributed = models.BooleanField(
        default=False, help_text="Whether the passenger has paid their contribution"
    )

    # Social aspects
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invited_passengers",
    )
    regular_passenger = models.BooleanField(
        default=False,
        help_text="Whether this is a regular passenger for recurring rides",
    )

    class Meta:
        unique_together = ("ride", "passenger")

    def __str__(self):
        return f"{self.passenger.username} - {self.ride}"
