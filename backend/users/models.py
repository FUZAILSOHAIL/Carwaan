from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator
from core.models import TimeStampedModel


class User(AbstractUser, TimeStampedModel):
    ROLE_CHOICES = (
        ("admin", "Admin"),
        ("user", "User"),
    )
    
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="user")
    phone = models.CharField(validators=[phone_regex], max_length=15, unique=True, null=True, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.CharField(max_length=255, blank=True)
    is_verified = models.BooleanField(default=False)
    
    # New fields for carpooling
    workplace = models.CharField(max_length=255, blank=True, help_text="Company or institution where you work/study")
    department = models.CharField(max_length=100, blank=True, help_text="Department or team within the workplace")
    has_car = models.BooleanField(default=False, help_text="Whether the user has a car to offer rides")
    car_model = models.CharField(max_length=100, blank=True, help_text="Model of the user's car")
    car_color = models.CharField(max_length=50, blank=True, help_text="Color of the user's car")
    license_plate = models.CharField(max_length=20, blank=True, help_text="License plate of the user's car")
    
    # Social connections for carpooling
    connections = models.ManyToManyField('self', blank=True, symmetrical=False,
                                       related_name='connected_by',
                                       help_text="Colleagues, friends, etc.")
    friend_groups = models.JSONField(null=True, blank=True, 
                                   help_text="Groups of friends for organizing carpools")
    trusted_drivers = models.ManyToManyField('self', blank=True, symmetrical=False,
                                           related_name='trusted_by',
                                           help_text="Drivers you trust and prefer to ride with")
    
    # Enhanced fields for ride matching
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00, 
                                        help_text="User's average rating as driver/passenger")
    total_ratings = models.PositiveIntegerField(default=0, help_text="Number of ratings received")
    
    # User preferences for ride matching
    preferred_days = models.JSONField(null=True, blank=True, 
                               help_text="Preferred days for commuting [0-6], where 0 is Monday")
    preferred_departure_times = models.JSONField(null=True, blank=True, 
                                         help_text="Preferred departure times in 24h format")
    preferred_music = models.JSONField(null=True, blank=True, 
                                     help_text="Music preferences for rides")
    
    smoking_preference = models.CharField(max_length=20, choices=[
        ("no_smoking", "No Smoking"),
        ("smoking_allowed", "Smoking Allowed"),
        ("no_preference", "No Preference"),
    ], default="no_smoking")
    
    ac_preference = models.CharField(max_length=20, choices=[
        ("ac_required", "AC Required"),
        ("no_ac", "No AC"),
        ("no_preference", "No Preference"),
    ], default="no_preference")
    
    chat_preference = models.CharField(max_length=20, choices=[
        ("chatty", "Enjoy Conversation"),
        ("quiet", "Prefer Quiet"),
        ("no_preference", "No Preference"),
    ], default="no_preference")
    
    home_address = models.CharField(max_length=255, blank=True, 
                                   help_text="Home address for better ride matching")
    home_latitude = models.FloatField(null=True, blank=True)
    home_longitude = models.FloatField(null=True, blank=True)
    
    workplace_address = models.CharField(max_length=255, blank=True, 
                                        help_text="Complete workplace address")
    workplace_latitude = models.FloatField(null=True, blank=True)
    workplace_longitude = models.FloatField(null=True, blank=True)
    
    # Payment info
    payment_methods = models.JSONField(null=True, blank=True, 
                                      help_text="User's saved payment methods")
    
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def is_admin(self):
        return self.role == "admin"
    
    def is_driver(self):
        """Check if user can offer rides (has a car)"""
        return self.has_car

    def can_offer_rides(self):
        return self.has_car

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

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["username"]
