"""
Plan features and access control for the Tender Insight Hub.
This module defines the features available to different subscription tiers
and provides decorators to restrict access based on team plans.
"""
from functools import wraps
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count

# Define feature access by plan tier
PLAN_FEATURES = {
    'free': {
        'max_users': 1,
        'weekly_tender_search_limit': 3,
        'ai_summary': False,
        'export_reports': False,
        'matched_tenders': False,
        'readiness_check': False,
    },
    'basic': {
        'max_users': 3,
        'weekly_tender_search_limit': float('inf'),  # Unlimited
        'ai_summary': True,
        'export_reports': False,
        'matched_tenders': True,
        'readiness_check': True,
    },
    'pro': {
        'max_users': float('inf'),  # Unlimited
        'weekly_tender_search_limit': float('inf'),  # Unlimited
        'ai_summary': True,
        'export_reports': True,
        'matched_tenders': True,
        'readiness_check': True,
    }
}

def get_team_from_request(request):
    """Helper function to get the team from the request user."""
    if not request.user.is_authenticated:
        return None
    return request.user.team

def check_feature_access(team, feature_name):
    """
    Check if a team has access to a specific feature.
    
    Args:
        team: The team object
        feature_name: The name of the feature to check
        
    Returns:
        bool: True if the team has access, False otherwise
    """
    if not team:
        return False
    
    plan = team.subscription_tier
    if plan not in PLAN_FEATURES:
        return False
    
    return PLAN_FEATURES[plan].get(feature_name, False)

def require_feature_access(feature_name, redirect_url=None):
    """
    Decorator to restrict access to views based on team plan features.
    
    Args:
        feature_name: The name of the feature to check
        redirect_url: Optional URL name to redirect to if access is denied
        
    Returns:
        Function decorator
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            team = get_team_from_request(request)
            
            if not team:
                messages.error(request, "You must be part of a team to access this feature.")
                return redirect('login')
            
            if not check_feature_access(team, feature_name):
                messages.error(
                    request, 
                    f"Your current plan does not include access to this feature. "
                    f"Please upgrade your subscription to access {feature_name.replace('_', ' ')}."
                )
                if redirect_url:
                    return redirect(reverse(redirect_url))
                return HttpResponseForbidden("Access denied. Your plan does not include this feature.")
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

def check_search_limit(request):
    """
    Check if a user has exceeded their weekly tender search limit.
    
    Args:
        request: The HTTP request
        
    Returns:
        bool: True if the user can perform a search, False if they've reached their limit
    """
    team = get_team_from_request(request)
    if not team:
        return False
    
    plan = team.subscription_tier
    if plan not in PLAN_FEATURES:
        return False
    
    # If the plan has unlimited searches, return True
    weekly_limit = PLAN_FEATURES[plan].get('weekly_tender_search_limit', 0)
    if weekly_limit == float('inf'):
        return True
    
    # Check the number of searches in the past week
    from .models import SearchLog
    one_week_ago = timezone.now() - timedelta(days=7)
    search_count = SearchLog.objects.filter(
        user=request.user,
        timestamp__gte=one_week_ago
    ).count()
    
    return search_count < weekly_limit

def require_search_limit(redirect_url='search_limit_reached'):
    """
    Decorator to restrict tender searches based on the weekly limit.
    
    Args:
        redirect_url: URL name to redirect to if the limit is reached
        
    Returns:
        Function decorator
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not check_search_limit(request):
                messages.error(
                    request, 
                    "You have reached your weekly tender search limit. "
                    "Please upgrade your subscription for unlimited searches."
                )
                return redirect(reverse(redirect_url))
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

def check_team_size_limit(team):
    """
    Check if a team has reached its user limit.
    
    Args:
        team: The team object
        
    Returns:
        bool: True if the team can add more users, False if they've reached their limit
    """
    if not team:
        return False
    
    plan = team.subscription_tier
    if plan not in PLAN_FEATURES:
        return False
    
    max_users = PLAN_FEATURES[plan].get('max_users', 0)
    current_users = team.members.count()
    
    return current_users < max_users