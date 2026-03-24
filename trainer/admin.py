from django.contrib import admin
from .models import Scenario, GameResult  


@admin.register(Scenario)
class ScenarioAdmin(admin.ModelAdmin):
    
    list_display = ['text', 'is_malicious', 'category', ]

@admin.register(GameResult)
class GameResultAdmin(admin.ModelAdmin):
    list_display = ('user', 'score', 'timestamp', 'category')
