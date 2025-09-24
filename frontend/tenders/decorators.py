"""
Decorators for feature access control based on team subscription plans.
"""
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse
from .plan_features import check_feature_access, get_team_from_request

def ai_summary_required(view_func):
    """Decorator to restrict access to AI summary feature."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        team = get_team_from_request(request)
        if not check_feature_access(team, 'ai_summary'):
            messages.error(
                request, 
                "AI summary feature is not available on your current plan. "
                "Please upgrade to Basic or Pro plan to access this feature."
            )
            return redirect('subscription_plans')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def export_required(view_func):
    """Decorator to restrict access to export feature."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        team = get_team_from_request(request)
        if not check_feature_access(team, 'export_reports'):
            messages.error(
                request, 
                "Export feature is only available on the Pro plan. "
                "Please upgrade your subscription to access this feature."
            )
            return redirect('subscription_plans')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def matched_tenders_required(view_func):
    """Decorator to restrict access to matched tenders feature."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        team = get_team_from_request(request)
        if not check_feature_access(team, 'matched_tenders'):
            messages.error(
                request, 
                "Matched tenders feature is not available on your current plan. "
                "Please upgrade to Basic or Pro plan to access this feature."
            )
            return redirect('subscription_plans')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def readiness_check_required(view_func):
    """Decorator to restrict access to readiness check feature."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        team = get_team_from_request(request)
        if not check_feature_access(team, 'readiness_check'):
            messages.error(
                request, 
                "Readiness check feature is not available on your current plan. "
                "Please upgrade to Basic or Pro plan to access this feature."
            )
            return redirect('subscription_plans')
        return view_func(request, *args, **kwargs)
    return _wrapped_view