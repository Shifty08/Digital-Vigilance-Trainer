import random
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.models import User
from django.db import models
from .models import Scenario, GameResult
from django.shortcuts import render, get_object_or_404
from django.views.decorators.cache import never_cache
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.db.models import Max, Avg
from .models import Scenario, GameResult


def signup(request):
    error_msg = None
    username_taken = False

    if request.method == 'POST':
        user_id = request.POST.get('username')
        access_key = request.POST.get('password')
        
        if User.objects.filter(username__iexact=user_id).exists():
            username_taken = True 
        else:
            try:
                user = User.objects.create_user(username=user_id, password=access_key)
                login(request, user)
                return redirect('index')
            except Exception:
                error_msg = "REGISTRATION_FAILED: SYSTEM_ERROR"

    return render(request, 'trainer/signup.html', {
        'username_taken': username_taken,
        'error_msg': error_msg
    })

def user_login(request):
    if request.method == 'POST':
        user_id = request.POST.get('username')
        access_key = request.POST.get('password')

        user = authenticate(request, username=user_id, password=access_key)

        if user is not None:
            login(request, user)
            return redirect('index') 
        else:
            messages.error(request, "ACCESS_DENIED: INVALID_CREDENTIALS")
            return render(request, 'trainer/login.html', {'error': True})
            
    return render(request, 'trainer/login.html')

def user_logout(request):
    logout(request)
    return redirect('index')

@login_required
@never_cache
def play_game(request, category):
    if 'round' not in request.session:
        request.session['round'] = 1
        request.session['score'] = 0
        request.session['last_result'] = None

    current_round = request.session.get('round', 1)

    # 2. THE BOUNCER
    if current_round > 10:
        final_score = request.session.get('score', 0)
        GameResult.objects.create(user=request.user, score=final_score, category=category)
        
        # Clean up session
        keys_to_del = ['round', 'score', 'last_result', 'current_scenario_id']
        for key in keys_to_del:
            if key in request.session: del request.session[key]
        
        return render(request, 'trainer/gameover.html', {'score': final_score, 'category': category})


    if request.method == 'POST':
        scenario_id = request.POST.get('scenario_id')
        user_choice = request.POST.get('choice')
        
        try:
                time_taken = float(request.POST.get('time_taken', 0))
        except ValueError:
                time_taken = 10.0

        current_scenario = get_object_or_404(Scenario, id=scenario_id)
        
        # Logic
        user_choice = request.POST.get('choice')
        is_malicious = current_scenario.is_malicious
        user_is_danger = (user_choice == 'Danger')

        if user_choice == "Timeout":
            is_correct = False
            pace_note = "TIMEOUT: Vigilance requires a decision."
        else:   
            user_is_danger = (user_choice == 'Danger')
            is_correct = (user_is_danger == is_malicious)

        round_score = 0
        pace_note = ""

        if is_correct:
            base_points = 100 
            
            
            if time_taken < 1.5:
                multiplier = 0.5
                pace_note = "TOO FAST: Precision requires observation."
            
            
            elif 1.5 <= time_taken <= 4.0:
                multiplier = 1.5
                pace_note = "ELITE: Perfect balance of speed and accuracy."
            
            
            elif 4.0 < time_taken <= 7.0:
                multiplier = 1.0
                pace_note = "SECURE: Good focus on the details."
            
            
            else:
                
                decay = (time_taken - 7) * 0.1
                multiplier = max(0.5, 1.0 - decay) 
                pace_note = "CAUTION: Delayed response increases risk."

            round_score = int(base_points * multiplier)
        else:
            pace_note = "BREACH: Incorrect assessment."
            round_score = 0

        
        request.session['score'] += round_score
        request.session['round'] += 1 
        
        
        if 'current_scenario_id' in request.session:
            del request.session['current_scenario_id']

        request.session['last_result'] = {
            'is_correct': is_correct,
            'round_score': round_score,
            'pace_note': pace_note,
            'explanation': current_scenario.explanation,
            'scenario_id': current_scenario.id,
            'image_url': current_scenario.image.url if current_scenario.image else None
        }
        
        return redirect('result', category=category)

    
    scenario_id = request.session.get('current_scenario_id')
    
    if scenario_id:
        
        scenario = get_object_or_404(Scenario, id=scenario_id)
    else:
        
        scenarios = Scenario.objects.filter(category=category)
        if not scenarios.exists():
            return redirect('index')
            
        scenario = random.choice(scenarios)
        
        request.session['current_scenario_id'] = scenario.id
    
    return render(request, 'trainer/play.html', {
        'scenario': scenario, 
        'round': current_round,
        'category': category
    })


@login_required
@never_cache
def round_result(request, category):
    result_data = request.session.get('last_result')
    
    if not result_data:
        return redirect('play_game', category=category)

    return render(request, 'trainer/result.html', {
        'is_correct': result_data['is_correct'],
        'round_score': result_data['round_score'],
        'pace_note': result_data['pace_note'],
        'explanation': result_data['explanation'],
        'image_url': result_data['image_url'],
        'category': category
    })

def index(request):
    if request.user.is_authenticated:
        return render(request, 'trainer/home.html')
    else:
        return render(request, 'trainer/landing.html')
def instructions(request, category):
    return render(request, 'trainer/instructions.html', {'category': category})

def module_select(request):
    return render(request, 'trainer/module_select.html')

def leaderboard(request):
    cat = request.GET.get('category', 'scam')
    
    
    top_scores = GameResult.objects.filter(category=cat).order_by('-score', '-timestamp')[:10]
    
    return render(request, 'trainer/leaderboard.html', {
        'top_scores': top_scores,
        'current_category': cat,
        'categories': ['scam', 'phishing', 'disinfo']
    })

@login_required
def profile(request):
    categories = ['scam', 'phishing', 'disinfo']
    stats = {}
    
    for cat in categories:
        user_cat_results = GameResult.objects.filter(user=request.user, category=cat)
        
        stats[cat] = {
            'total': user_cat_results.count(),
            'best': user_cat_results.aggregate(Max('score'))['score__max'] or 0,
            'average': user_cat_results.aggregate(Avg('score'))['score__avg'] or 0,
        }

    return render(request, 'trainer/profile.html', {
        'stats': stats,
    })