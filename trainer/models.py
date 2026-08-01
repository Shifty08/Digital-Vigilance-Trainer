from django.db import models
from django.contrib.auth.models import User
import random

class Scenario(models.Model):
    CATEGORY_CHOICES = [
        ('scam', 'Scam'),
        ('phishing', 'Phishing'),
        ('disinfo', 'Disinformation'),
    ]

    DIFFICULTY_CHOICES = [
        ('easy', 'Easy (3+ obvious signs)'),
        ('medium', 'Medium (2 signs)'),
        ('hard', 'Hard (1 subtle hint)'),
    ]
    
    text = models.TextField()
    is_malicious = models.BooleanField()
    explanation = models.TextField(default="No explanation provided.") 
    image = models.ImageField(upload_to='scenarios/', blank=True, null=True) 
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES)

    # NEW FIELDS:
    difficulty = models.CharField(
        max_length=10, 
        choices=DIFFICULTY_CHOICES, 
        default='easy'
    )
    # Track the explicit red flags/hints for feedback and validation
    indicators = models.JSONField(
        default=list, 
        blank=True, 
        help_text="List of specific threat signs/red flags present in this scenario."
    )

    def __str__(self):
        return f"{self.category.capitalize()}: {self.text[:30]}..."

class GameResult(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    score = models.IntegerField()
    category = models.CharField(max_length=50)
    difficulty = models.CharField(
        max_length=10, 
        choices=Scenario.DIFFICULTY_CHOICES, 
        default='easy'
    )
    timestamp = models.DateTimeField(auto_now_add=True) 

    def __str__(self):
        return f"{self.user.username} - {self.score}"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    mfa_enabled = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"