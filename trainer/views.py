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
import random
from django.core.mail import send_mail
from django.conf import settings


def signup(request):
    error_msg = None
    username_taken = False

    if request.method == 'POST':
        user_id = request.POST.get('username')
        email = request.POST.get('email')
        access_key = request.POST.get('password')
        
        if User.objects.filter(username__iexact=user_id).exists():
            username_taken = True 
        else:
            try:
                request.session['pending_user'] = {
                    'username': user_id,
                    'email': email,
                    'password': access_key,
                }
                
                
                send_otp_to_email(request, email=email, username=user_id)
                
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
                send_otp_to_email(request, email=user.email, username=user.username)
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
                        email=pending_user['email'],
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

def send_otp_to_email(request, email, username):
    """Generates a 6-digit OTP, stores it in session, and emails it safely."""
    otp_code = str(random.randint(100000, 999999))
    

    request.session['mfa_otp'] = otp_code
    
    subject = "OPERATIVE VERIFICATION: Your Security Passcode"
    message = (
        f"Agent {username},\n\n"
        f"Your 6-digit One-Time Passcode for Digital Vigilance Trainer is: {otp_code}\n\n"
        f"Enter this code on the verification screen to complete your account registration."
    )
    
    try:

        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
        print(f"\n[SUCCESS] OTP {otp_code} sent to {email}")
    except Exception as e:
        print(f"\n[SMTP ERROR] Could not send email: {str(e)}")
        
        print(f"--> FALLBACK OTP FOR {username}: {otp_code}\n")

def user_logout(request):
    logout(request)
    return redirect('index')

def is_difficulty_unlocked(user, category, difficulty):
    if not user.is_authenticated:
        return False
    if difficulty == 'easy':
        return True
    if difficulty == 'medium':
       
        return GameResult.objects.filter(
            user=user, category=category, difficulty='easy', score__gte=800
        ).exists()
    if difficulty == 'hard':
        
        return GameResult.objects.filter(
            user=user, category=category, difficulty='medium', score__gte=1100
        ).exists()
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
        is_malicious = current_scenario.is_malicious

        is_correct = False
        is_optimal_report = False
        pace_note = ""

        choice_lower = user_choice.lower()

        if user_choice == "Timeout":
            is_correct = False
            pace_note = "TIMEOUT: Vigilance requires a decision."

        elif choice_lower == 'report':
            if is_malicious:
                is_correct = True
                is_optimal_report = True
                pace_note = "OPTIMAL DEFENSE: Threat escalated to Security Operations!"
            else:
                is_correct = False
                pace_note = "FALSE ALARM: Legitimate item reported to security."


        else:
            user_is_danger = choice_lower in ['danger', 'delete', 'ignore', 'fake']
            is_correct = (user_is_danger == is_malicious)

        round_score = 0

        if is_correct:
            difficulty_multipliers = {
                'easy': 1.0,
                'medium': 1.5,
                'hard': 2.0
            }
            diff_multiplier = difficulty_multipliers.get(difficulty, 1.0)
            base_points = 100 * diff_multiplier
            
            if time_taken < 1.5:
                pace_multiplier = 0.5
                if not is_optimal_report:
                    pace_note = "TOO FAST: Precision requires observation."
            elif 1.5 <= time_taken <= 4.0:
                pace_multiplier = 1.5
                if not is_optimal_report:
                    pace_note = "ELITE: Perfect balance of speed and accuracy."
            elif 4.0 < time_taken <= 7.0:
                pace_multiplier = 1.0
                if not is_optimal_report:
                    pace_note = "SECURE: Good focus on the details."
            else:
                decay = (time_taken - 7) * 0.1
                pace_multiplier = max(0.5, 1.0 - decay) 
                if not is_optimal_report:
                    pace_note = "CAUTION: Delayed response increases risk."

            report_bonus = 1.2 if is_optimal_report else 1.0

            round_score = int(base_points * pace_multiplier * report_bonus)
        else:
            if user_choice != "Timeout" and choice_lower != 'report':
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
        
        if not scenarios.exists() and not Scenario.objects.filter(category=category, difficulty=difficulty).exists():
            scenarios = Scenario.objects.filter(category=category).exclude(id__in=seen_ids)
            
        if not scenarios.exists():
            seen_ids = []
            request.session['seen_scenarios'] = []
            scenarios = Scenario.objects.filter(category=category, difficulty=difficulty)
            if not scenarios.exists():
                scenarios = Scenario.objects.filter(category=category)
        
        if not scenarios.exists():
            return redirect('index')
        
        scenario = random.choice(list(scenarios))
        
        request.session['current_scenario_id'] = scenario.id
        seen_ids.append(scenario.id)
        request.session['seen_scenarios'] = seen_ids
    
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

    return render(request, 'trainer/landing.html', {
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