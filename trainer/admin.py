from django.contrib import admin
from .models import Scenario, GameResult  


@admin.register(Scenario)
class ScenarioAdmin(admin.ModelAdmin):
    # 1. Display key fields directly in the admin table view
    list_display = (
        'short_text', 
        'category', 
        'difficulty', 
        'is_malicious', 
        'has_image'
    )
    
    # 2. Add sidebar filters so you can filter scenarios quickly
    list_filter = ('category', 'difficulty', 'is_malicious')
    
    # 3. Add search capability for scenario text or explanations
    search_fields = ('text', 'explanation')
    
    # 4. Group fields cleanly on the detail/edit form page
    fieldsets = (
        ('Scenario Content', {
            'fields': ('text', 'image', 'explanation')
        }),
        ('Classification & Threat Level', {
            'fields': ('category', 'difficulty', 'is_malicious', 'indicators')
        }),
    )

# Custom helper method to show if an image is present
    @admin.display(boolean=True, description='Has Image?')
    def has_image(self, obj):
        return bool(obj.image)

    # Custom helper method to truncate long scenario text in list view
    @admin.display(description='Scenario Text')
    def short_text(self, obj):
        return obj.text[:50] + "..." if len(obj.text) > 50 else obj.text

@admin.register(GameResult)
class GameResultAdmin(admin.ModelAdmin):
    # Display user, score, category, difficulty, and timestamp
    list_display = ('user', 'score', 'category', 'difficulty', 'timestamp')
    
    # Add filters for quick analysis
    list_filter = ('category', 'difficulty', 'timestamp')
        
    # Enable searching by username
    search_fields = ('user__username',)
    
    # Keep results read-only to prevent tampering in admin
    readonly_fields = ('user', 'score', 'category', 'difficulty', 'timestamp')
