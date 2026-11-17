from django.contrib import admin
from .models import Scenario, GameResult  


@admin.register(Scenario)
class ScenarioAdmin(admin.ModelAdmin):
    list_display = (
        'short_text', 
        'category', 
        'difficulty', 
        'is_malicious', 
        'has_image'
    )
    
    list_filter = ('category', 'difficulty', 'is_malicious')
    
    search_fields = ('text', 'explanation')
 
    fieldsets = (
        ('Scenario Content', {
            'fields': ('text', 'image', 'explanation')
        }),
        ('Classification & Threat Level', {
            'fields': ('category', 'difficulty', 'is_malicious','optimal_action')
        }),
    )

    @admin.display(boolean=True, description='Has Image?')
    def has_image(self, obj):
        return bool(obj.image)

  
    @admin.display(description='Scenario Text')
    def short_text(self, obj):
        return obj.text[:50] + "..." if len(obj.text) > 50 else obj.text

@admin.register(GameResult)
class GameResultAdmin(admin.ModelAdmin):
    list_display = ('user', 'score', 'category', 'difficulty')
    
    list_filter = ('category', 'difficulty', 'timestamp')
    
    search_fields = ('user__username',)

    readonly_fields = ('user', 'score', 'category', 'difficulty', 'timestamp')
