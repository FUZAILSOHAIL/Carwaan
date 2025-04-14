from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator
from core.models import TimeStampedModel


class User(AbstractUser, TimeStampedModel):
    ROLE_CHOICES = (
        ("admin", "Admin"),
        ("driver", "Driver"),
        ("passenger", "Passenger"),
    )
    
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="passenger")
    phone = models.CharField(validators=[phone_regex], max_length=15, unique=True, null=True, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.CharField(max_length=255, blank=True)
    is_verified = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def is_admin(self):
        return self.role == "admin"
    
    def is_driver(self):
        return self.role == "driver"
    
    def is_passenger(self):
        return self.role == "passenger"

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["username"]
