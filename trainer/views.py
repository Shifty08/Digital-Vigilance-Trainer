import random
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.models import User
from django.db import models
from .models import Scenario, GameResult, UserProfile
from django.shortcuts import render, get_object_or_404
from django.views.decorators.cache import never_cache
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.db.models import Max, Avg
import random, csv
from django.core.mail import send_mail
from django.conf import settings
from django.http import HttpResponse
from django.contrib.admin.views.decorators import staff_member_required


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
                request.session['pending_user'] = {
                    'username': user_id,
                    'password': access_key,
                }
                generate_simulated_otp(request, user_id)           
                return redirect('verify_otp')

            except Exception as e:
                error_msg = f"REGISTRATION_FAILED: {str(e)}"

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
            profile, created = UserProfile.objects.get_or_create(user=user)
            
            if profile.mfa_enabled:
                request.session['mfa_user_id'] = user.id
                generate_simulated_otp(request, user.username)
                return redirect('verify_otp')
            else:
                login(request, user)
                return redirect('index')
        else:
            return render(request, 'trainer/login.html', {'error': True})
            
    return render(request, 'trainer/login.html')

def verify_otp(request):
    """MFA / Pre-Registration Step 2: Validates OTP before creating account or logging in."""
    stored_otp = request.session.get('mfa_otp')
    pending_user = request.session.get('pending_user')
    user_id_for_login = request.session.get('mfa_user_id')

    
    print(f"\n--- [DEBUG VERIFY OTP] ---")
    print(f"Stored OTP: {stored_otp}")
    print(f"Pending User: {pending_user}")
    print(f"User ID for Login: {user_id_for_login}")

    
    if not stored_otp or (not pending_user and not user_id_for_login):
        print("--> CRITICAL: Missing session data! Redirecting to login...")
        return redirect('login')

    
    if pending_user:
        display_username = pending_user.get('username', 'Operative')
        display_email = pending_user.get('email', '')
    else:
        try:
            existing_user = User.objects.get(id=user_id_for_login)
            display_username = existing_user.username
            display_email = existing_user.email
        except User.DoesNotExist:
            return redirect('login')

    if request.method == 'POST':
        entered_otp = request.POST.get('otp_code', '').strip()
        print(f"Entered OTP: '{entered_otp}' vs Stored OTP: '{stored_otp}'")

        if entered_otp == str(stored_otp):
            try:
                if pending_user:
                   
                    print("OTP Match! Creating new user in DB...")
                    new_user = User.objects.create_user(
                        username=pending_user['username'],
                        password=pending_user['password']
                    )
                    UserProfile.objects.create(user=new_user, mfa_enabled=True)
                    
                   
                    login(request, new_user)

        
                    if 'pending_user' in request.session:
                        del request.session['pending_user']
                else:
                    
                    print("OTP Match! Logging in existing user...")
                    user_to_login = User.objects.get(id=user_id_for_login)
                    login(request, user_to_login)
                    if 'mfa_user_id' in request.session:
                        del request.session['mfa_user_id']

                
                if 'mfa_otp' in request.session:
                    del request.session['mfa_otp']

                print("--> SUCCESS! Redirecting to index...")
                return redirect('index')

            except Exception as e:
                print(f"--> ERROR DURING USER CREATION/LOGIN: {str(e)}")
                return render(request, 'trainer/verify_otp.html', {
                    'username': display_username,
                    'email': display_email,
                    'error': f"SYSTEM_ERROR: {str(e)}"
                })
        else:
            print("--> INVALID OTP MATCH!")
            return render(request, 'trainer/verify_otp.html', {
                'username': display_username,
                'email': display_email,
                'error': "INVALID_PASSCODE: The passcode entered does not match."
            })

    return render(request, 'trainer/verify_otp.html', {
        'username': display_username,
        'email': display_email
    })

def generate_simulated_otp(request, username):
    """Generates a 6-digit OTP and simulates it on-screen."""
    otp_code = str(random.randint(100000, 999999))
    request.session['mfa_otp'] = otp_code
    messages.info(request, f"INCOMING TRANSMISSION: Your security passcode is {otp_code}")
    print(f"\n[SIMULATED OTP] Code {otp_code} generated for {username}\n")

def user_logout(request):
    logout(request)
    return redirect('index')

def is_difficulty_unlocked(user, category, difficulty):
    if difficulty == 'easy':
        return True
        
    best_easy_score = GameResult.objects.filter(
        user=user, category=category, difficulty='easy'
    ).aggregate(Max('score'))['score__max'] or 0

    if difficulty == 'medium':
        return best_easy_score >= 600

    if difficulty == 'hard':
        best_medium_score = GameResult.objects.filter(
            user=user, category=category, difficulty='medium'
        ).aggregate(Max('score'))['score__max'] or 0
        
        return best_medium_score >= 1200

    return False

@login_required
def module_select(request):
    categories = ['scam', 'phishing', 'disinfo']
    unlock_status = {}

    for cat in categories:
        unlock_status[cat] = {
            'easy': True,
            'medium': is_difficulty_unlocked(request.user, cat, 'medium'),
            'hard': is_difficulty_unlocked(request.user, cat, 'hard'),
        }

    return render(request, 'trainer/module_select.html', {
        'unlock_status': unlock_status
    })

@login_required
@never_cache
def play_game(request, category, difficulty='easy'):

    if not is_difficulty_unlocked(request.user, category, difficulty):
        return redirect('module_select')
    
    if 'round' not in request.session:
        request.session['round'] = 1
        request.session['score'] = 0
        request.session['last_result'] = None
        request.session['seen_scenarios'] = []  

    current_round = request.session.get('round', 1)

    if current_round > 10:
        final_score = request.session.get('score', 0)
        GameResult.objects.create(
            user=request.user, 
            score=final_score, 
            category=category,
            difficulty=difficulty
        )
        
        keys_to_del = ['round', 'score', 'last_result', 'current_scenario_id', 'seen_scenarios']
        for key in keys_to_del:
            if key in request.session: 
                del request.session[key]
        
        return render(request, 'trainer/gameover.html', {
            'score': final_score, 
            'category': category,
            'difficulty': difficulty
        })

    if request.method == 'POST':
        scenario_id = request.POST.get('scenario_id')
        user_choice = request.POST.get('choice', '').strip()
        
        try:
            time_taken = float(request.POST.get('time_taken', 0))
        except ValueError:
            time_taken = 10.0

        current_scenario = get_object_or_404(Scenario, id=scenario_id)


        choice_lower = user_choice.lower()
        is_correct = False
        pace_note = ""
        round_score = 0

        difficulty_base = {
            'easy': 100,
            'medium': 200,
            'hard': 300
        }
        base_points = difficulty_base.get(difficulty, 100)

        defensive_actions = ['ignore', 'delete', 'fake', 'report']


        if user_choice == "Timeout" or choice_lower == "timeout":
            is_correct = False
            pace_note = "TIMEOUT: Vigilance requires a decision."
            round_score = 0

        elif choice_lower == current_scenario.optimal_action:
            is_correct = True
            
            if time_taken < 1.5:
                round_score = int(base_points * 0.5)
                pace_note = "TOO FAST:guessing detected. Slow down for full points!"
            else:
                time_penalty = int(time_taken) * 2
                round_score = max(base_points - time_penalty, int(base_points * 0.7))
                pace_note = "OPTIMAL: Great balance of analysis and decision making."

        elif choice_lower in defensive_actions and current_scenario.is_malicious:
            is_correct = True 
            round_score = int(base_points * 0.4)
            pace_note = f"SUB-OPTIMAL: Good reflex! But the BEST action was to {current_scenario.optimal_action.upper()}."

        else:
            is_correct = False
            round_score = 0
            pace_note = f"BREACH: Incorrect assessment. The best action was to {current_scenario.optimal_action.upper()}."


        request.session['score'] += round_score
        request.session['round'] += 1 
        
        if 'current_scenario_id' in request.session:
            del request.session['current_scenario_id']

        request.session['last_result'] = {
            'is_correct': is_correct,
            'round_score': round_score,
            'pace_note': pace_note,
            'user_choice': user_choice,
            'explanation': current_scenario.explanation,
            'scenario_id': current_scenario.id,
            'image_url': current_scenario.image.url if current_scenario.image else None
        }
        
        return redirect('result_diff', category=category, difficulty=difficulty)

    scenario_id = request.session.get('current_scenario_id')
    
    if scenario_id:
        scenario = get_object_or_404(Scenario, id=scenario_id)
    else:
        seen_ids = request.session.get('seen_scenarios', [])

        scenarios = Scenario.objects.filter(
            category=category, 
            difficulty=difficulty
        ).exclude(id__in=seen_ids)
        

        if not scenarios.exists():
            seen_ids = []
            request.session['seen_scenarios'] = []
            scenarios = Scenario.objects.filter(category=category, difficulty=difficulty)
            
            if not scenarios.exists():
                return redirect('index')

        scenario = random.choice(list(scenarios))
        
        request.session['current_scenario_id'] = scenario.id
        seen_ids.append(scenario.id)
        request.session['seen_scenarios'] = seen_ids
        
        request.session.modified = True 
    
    return render(request, 'trainer/play.html', {
        'scenario': scenario, 
        'round': current_round,
        'category': category,
        'difficulty': difficulty
    })

@login_required
def index(request):
    categories = ['phishing', 'scam', 'disinfo']
    unlock_status = {}

    for cat in categories:
        unlock_status[cat] = {
            'easy': True,
            'medium': is_difficulty_unlocked(request.user, cat, 'medium'),
            'hard': is_difficulty_unlocked(request.user, cat, 'hard'),
        }

    return render(request, 'trainer/home.html', {
        'unlock_status': unlock_status
    })

@login_required
@never_cache
def round_result(request, category,  difficulty='easy'):
    result_data = request.session.get('last_result')
    
    if not result_data:
        return redirect('play_game', category=category)

    return render(request, 'trainer/result.html', {
        'is_correct': result_data['is_correct'],
        'round_score': result_data['round_score'],
        'pace_note': result_data['pace_note'],
        'explanation': result_data['explanation'],
        'image_url': result_data['image_url'],
        'category': category,
        'difficulty': difficulty,
    })

    
def instructions(request, category, difficulty='easy'):
    return render(request, 'trainer/instructions.html', {'category': category, 'difficulty': difficulty})


def leaderboard(request):
    cat = request.GET.get('category', 'scam')
    diff = request.GET.get('difficulty', 'easy') 
    
    
    top_scores = GameResult.objects.filter(
        category=cat, 
        difficulty=diff
    ).order_by('-score', '-timestamp')[:10]
    
    return render(request, 'trainer/leaderboard.html', {
        'top_scores': top_scores,
        'current_category': cat,
        'current_difficulty': diff,
        'categories': ['scam', 'phishing', 'disinfo'],
        'difficulties': ['easy', 'medium', 'hard'],
    })

@login_required
def profile(request):
    categories = ['scam', 'phishing', 'disinfo']
    difficulties = ['easy', 'medium', 'hard']
    
    stats = {}
    
    for cat in categories:
        stats[cat] = {}
        for diff in difficulties:
            
            user_results = GameResult.objects.filter(
                user=request.user, 
                category=cat, 
                difficulty=diff
            ).order_by('timestamp')
            
            total_count = user_results.count()
            
            if total_count > 0:
                baseline_entry = user_results.first()
                baseline_score = baseline_entry.score if baseline_entry else 0
                
                running_entry = user_results.last()
                running_score = running_entry.score if running_entry else 0
                
                best_score = user_results.aggregate(Max('score'))['score__max'] or 0
                avg_score = round(user_results.aggregate(Avg('score'))['score__avg'] or 0, 1)
                
                progression = running_score - baseline_score
            else:
                baseline_score = 0
                running_score = 0
                best_score = 0
                avg_score = 0
                progression = 0

            stats[cat][diff] = {
                'total': total_count,
                'baseline_score': baseline_score,
                'running_score': running_score,
                'best_score': best_score,
                'avg_score': avg_score,
                'progression': progression,
            }

    return render(request, 'trainer/profile.html', {
        'stats': stats,
        'categories': categories,
        'difficulties': difficulties,
    })

@staff_member_required
def export_results_csv(request):
    """Exports all GameResults to a CSV file for capstone data analysis."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="vigilance_results_export.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Username', 'Category', 'Difficulty', 'Score'])
    
    results = GameResult.objects.all().order_by('-id')
    
    for result in results:
        writer.writerow([
            result.user.username,
            result.category,
            result.difficulty,
            result.score,
        ])
        
    return response