from django.db import models
from django.contrib.auth.models import User

class Scenario(models.Model):
    CATEGORY_CHOICES = [
        ('scam', 'Scam'),
        ('phishing', 'Phishing'),
        ('disinfo', 'Disinformation'),
    ]
    
    text = models.TextField()
    is_malicious = models.BooleanField()
    explanation = models.TextField(default="No explanation provided.") 
    image = models.ImageField(upload_to='scenarios/', blank=True, null=True) 
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES)

    def __str__(self):
        return f"{self.category.capitalize()}: {self.text[:30]}..."

class GameResult(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    score = models.IntegerField()
    category = models.CharField(max_length=50)
    timestamp = models.DateTimeField(auto_now_add=True) 

    def __str__(self):
        return f"{self.user.username} - {self.score}"