from django.db import models
from core.models import TimeStampedModel
from users.models import User


class Ride(TimeStampedModel):
    rider = models.ForeignKey(User, related_name="rides", on_delete=models.CASCADE)
    driver = models.ForeignKey(
        User, related_name="drives", on_delete=models.SET_NULL, null=True, blank=True
    )
    pickup_location = models.CharField(max_length=255)
    dropoff_location = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("accepted", "Accepted"),
            ("completed", "Completed"),
        ],
    )

    def __str__(self):
        return f"Ride {self.id} from {self.pickup_location} to {self.dropoff_location} - Status: {self.status}"
    



class RideRequest(models.Model):
    ride = models.ForeignKey(Ride, on_delete=models.CASCADE)
    request_time = models.DateTimeField(auto_now_add=True)
    requested_by = models.ForeignKey(
        User, related_name="ride_requests", on_delete=models.CASCADE
    )
    status = models.CharField(
        max_length=20, choices=[("pending", "Pending"), ("completed", "Completed")]
    )

    def __str__(self):
        return f"Request for Ride {self.ride.id} by {self.requested_by.username} - Status: {self.status}"


class Location(models.Model):
    name = models.CharField(max_length=255)
    latitude = models.FloatField()
    longitude = models.FloatField()

    def __str__(self):
        return self.name
