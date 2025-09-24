from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpRequest, JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import AuthenticationForm
import requests
import json
from datetime import datetime, timedelta

from .models import (
    Tender, Team, CustomUser, CompanyProfile, ReadinessScore,
    WorkspaceItem, Note, Task, DocumentSummary, Certification,
    SearchLog, CompanyDocument
)
from .forms import UserRegistrationForm
from .utils import extract_province_from_buyer
from .plan_features import require_feature_access, require_search_limit, check_team_size_limit, check_feature_access

# API Base URL
API_BASE_URL = "http://localhost:8000"

# Search limit reached view
@login_required
def search_limit_reached(request):
    return render(request, 'tenders/search_limit_reached.html')

# Original search function
@login_required
@require_search_limit()
def search_results(request: HttpRequest):
    keywords = request.GET.get("keywords", "")
    province = request.GET.get('province', '')
    buyer = request.GET.get('buyer', '')
    budget_range = request.GET.get('budget_range', '')
    deadline = request.GET.get('deadline', '')
    
    # Log this search for tracking weekly limits
    if keywords or province or buyer or budget_range or deadline:
        SearchLog.objects.create(
            user=request.user,
            query=json.dumps({
                'keywords': keywords,
                'province': province,
                'buyer': buyer,
                'budget_range': budget_range,
                'deadline': deadline
            })
        )
    
    tenders_qs = Tender.objects.all()

    if keywords:
        tenders_qs = tenders_qs.filter(
            Q(title__icontains=keywords) | Q(description__icontains=keywords)
        )
    
    if province:
        tenders_qs = tenders_qs.filter(province=province)
    
    if buyer:
        tenders_qs = tenders_qs.filter(buyer_name=buyer)
    
    # Pagination
    paginator = Paginator(tenders_qs, 10)  # 10 tenders per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    return render(request, "tenders/results.html", {
        "tenders": page_obj,
        "is_paginated": page_obj.has_other_pages(),
        "page_obj": page_obj,
        "keywords": keywords,
        "selected_province": province,
        "selected_buyer": buyer,
        "selected_budget_range": budget_range,
        "selected_deadline": deadline
    })

# Home page view
def home(request):
    context = {
        'is_public': not request.user.is_authenticated,
    }
    
    return render(request, 'tenders/home.html', context)

# Register view
def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=password)
            login(request, user)
            messages.success(request, f"Account created for {username}. Welcome to Tender Insight Hub!")
            return redirect('tenders:dashboard')
    else:
        form = UserRegistrationForm()
    return render(request, 'tenders/register.html', {'form': form})

# Login view
def user_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome back, {username}!")
                return redirect('tenders:dashboard')
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
    return render(request, 'tenders/login.html', {'form': form})

# Logout view
def user_logout(request):
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect('tenders:home')

# Dashboard view
@login_required
def dashboard(request):
    from django.db.models import Count, Q
    from datetime import datetime, timedelta
    
    # Get user's team
    team = request.user.team
    
    if not team:
        messages.error(request, "You are not assigned to a team. Please contact an administrator.")
        return redirect('home')
    
    # Get workspace items for the team
    workspace_items = WorkspaceItem.objects.filter(team=team).order_by('-created_at')
    
    # Get company profile
    try:
        company_profile = CompanyProfile.objects.get(team=team)
        profile_complete = True
    except CompanyProfile.DoesNotExist:
        company_profile = None
        profile_complete = False
    
    # Calculate dashboard statistics
    workspace_count = workspace_items.count()
    
    # Get workspace items by status for charts
    workspace_stats = workspace_items.values('status').annotate(count=Count('id'))
    status_data = {stat['status']: stat['count'] for stat in workspace_stats}
    
    # Get recent activity (workspace items created in last 30 days)
    thirty_days_ago = datetime.now() - timedelta(days=30)
    recent_activity = []
    for item in workspace_items.filter(created_at__gte=thirty_days_ago)[:5]:
        recent_activity.append({
            'title': f"Added {item.tender.title[:50]}..." if item.tender.title else "Added tender to workspace",
            'description': f"Status: {item.status}",
            'timestamp': item.created_at,
            'user': item.updated_by.username if item.updated_by else 'System'
        })
    
    # Calculate upcoming deadlines (tenders closing in next 7 days)
    seven_days_from_now = datetime.now() + timedelta(days=7)
    upcoming_deadlines_count = Tender.objects.filter(
        tender_period_end_date__lte=seven_days_from_now,
        tender_period_end_date__gte=datetime.now()
    ).count()
    
    # Get pending tasks count (assuming tasks are related to workspace items)
    pending_tasks_count = 0
    for item in workspace_items:
        pending_tasks_count += item.tasks.filter(status='pending').count()
    
    # Calculate readiness scores distribution for charts
    readiness_scores = ReadinessScore.objects.filter(team=team)
    high_matches = readiness_scores.filter(suitability_score__gte=80).count()
    medium_matches = readiness_scores.filter(suitability_score__gte=50, suitability_score__lt=80).count()
    low_matches = readiness_scores.filter(suitability_score__lt=50).count()
    
    context = {
        'workspace_items': workspace_items[:5],  # Show only 5 most recent items
        'company_profile': company_profile,
        'profile_complete': profile_complete,
        'team': team,
        'workspace_count': workspace_count,
        'pending_tasks_count': pending_tasks_count,
        'upcoming_deadlines_count': upcoming_deadlines_count,
        'recent_activity': recent_activity,
        # Chart data
        'high_matches': high_matches,
        'medium_matches': medium_matches,
        'low_matches': low_matches,
        'interested_count': status_data.get('interested', 0),
        'not_eligible_count': status_data.get('not_eligible', 0),
        'submitted_count': status_data.get('submitted', 0),
        'pending_count': status_data.get('pending', 0),
        'won_count': status_data.get('won', 0),
        'lost_count': status_data.get('lost', 0),
        # Chart data for JavaScript
        'workspace_status_labels': ['Pending', 'Interested', 'Not Eligible', 'Submitted', 'Won', 'Lost'],
        'workspace_status_data': [
            status_data.get('pending', 0),
            status_data.get('interested', 0),
            status_data.get('not_eligible', 0),
            status_data.get('submitted', 0),
            status_data.get('won', 0),
            status_data.get('lost', 0)
        ],
        'readiness_score_labels': ['High (80-100)', 'Medium (50-79)', 'Low (0-49)'],
        'readiness_score_data': [high_matches, medium_matches, low_matches],
    }
    
    return render(request, 'tenders/dashboard.html', context)

# Enhanced search view
@login_required
def search_tenders(request):
    keywords = request.GET.get('keywords', '')
    province = request.GET.get('province', '')
    buyer = request.GET.get('buyer', '')
    budget_range = request.GET.get('budget_range', '')
    deadline = request.GET.get('deadline', '')
    
    # Check if user has performed any search
    has_search_params = bool(keywords or province or buyer or budget_range or deadline)
    
    # Only show tenders if user has performed a search
    if has_search_params:
        # Start with all tenders
        tenders_qs = Tender.objects.all()
    else:
        # No search performed, return empty queryset
        tenders_qs = Tender.objects.none()
    
    # Apply filters
    if keywords:
        tenders_qs = tenders_qs.filter(
            Q(title__icontains=keywords) | 
            Q(description__icontains=keywords) |
            Q(buyer_name__icontains=keywords)
        )
    
    if province:
        tenders_qs = tenders_qs.filter(province__icontains=province)
    
    if buyer:
        tenders_qs = tenders_qs.filter(buyer_name__icontains=buyer)
    
    # Budget range filtering
    if budget_range:
        if budget_range == 'under_100k':
            tenders_qs = tenders_qs.filter(value_amount__lt=100000)
        elif budget_range == '100k_1m':
            tenders_qs = tenders_qs.filter(value_amount__gte=100000, value_amount__lt=1000000)
        elif budget_range == '1m_10m':
            tenders_qs = tenders_qs.filter(value_amount__gte=1000000, value_amount__lt=10000000)
        elif budget_range == 'over_10m':
            tenders_qs = tenders_qs.filter(value_amount__gte=10000000)
    
    # Deadline filtering
    if deadline:
        today = datetime.now().date()
        if deadline == 'next_7_days':
            end_date = today + timedelta(days=7)
            tenders_qs = tenders_qs.filter(tender_period_end_date__gte=today, tender_period_end_date__lte=end_date)
        elif deadline == 'next_30_days':
            end_date = today + timedelta(days=30)
            tenders_qs = tenders_qs.filter(tender_period_end_date__gte=today, tender_period_end_date__lte=end_date)
        elif deadline == 'next_90_days':
            end_date = today + timedelta(days=90)
            tenders_qs = tenders_qs.filter(tender_period_end_date__gte=today, tender_period_end_date__lte=end_date)
    
    # Order by relevance (most recent first)
    tenders_qs = tenders_qs.order_by('-tender_period_end_date')
    
    # Extract provinces from buyer names for tenders with 'Not specified' province
    for tender in tenders_qs.filter(province__in=['Not specified', '', None]):
        extracted_province = extract_province_from_buyer(tender.buyer_name)
        if extracted_province:
            tender.province = extracted_province
            tender.save()
    
    # Get filter options from database
    provinces = list(Tender.objects.values_list('province', flat=True).distinct().exclude(province__isnull=True).exclude(province=''))
    buyers = list(Tender.objects.values_list('buyer_name', flat=True).distinct().exclude(buyer_name__isnull=True).exclude(buyer_name='')[:50])  # Limit to 50 for performance
    
    budget_ranges = [
        ('under_100k', 'Under R100,000'),
        ('100k_1m', 'R100,000 - R1,000,000'),
        ('1m_10m', 'R1,000,000 - R10,000,000'),
        ('over_10m', 'Over R10,000,000')
    ]
    
    deadline_ranges = [
        ('next_7_days', 'Next 7 days'),
        ('next_30_days', 'Next 30 days'),
        ('next_90_days', 'Next 90 days')
    ]
    
    # Pagination
    paginator = Paginator(tenders_qs, 10)  # 10 tenders per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'tenders': page_obj,
        'keywords': keywords,
        'provinces': provinces,
        'buyers': buyers,
        'budget_ranges': budget_ranges,
        'deadline_ranges': deadline_ranges,
        'selected_province': province,
        'selected_buyer': buyer,
        'selected_budget_range': budget_range,
        'selected_deadline': deadline,
        'total_results': tenders_qs.count()
    }
    
    return render(request, 'tenders/search.html', context)


def public_search_tenders(request):
    """Public search view that allows anonymous users to search tenders"""
    
    keywords = request.GET.get('keywords', '')
    province = request.GET.get('province', '')
    buyer = request.GET.get('buyer', '')
    budget_range = request.GET.get('budget_range', '')
    deadline = request.GET.get('deadline', '')
    
    # Check if user has performed any search
    has_search_params = bool(keywords or province or buyer or budget_range or deadline)
    
    # Only show tenders if user has performed a search
    if has_search_params:
        # Start with all tenders
        tenders_qs = Tender.objects.all()
    else:
        # No search performed, return empty queryset
        tenders_qs = Tender.objects.none()
    
    # Apply filters
    if keywords:
        tenders_qs = tenders_qs.filter(
            Q(title__icontains=keywords) | 
            Q(description__icontains=keywords) |
            Q(buyer_name__icontains=keywords)
        )
    
    if province:
        tenders_qs = tenders_qs.filter(province__icontains=province)
    
    if buyer:
        tenders_qs = tenders_qs.filter(buyer_name__icontains=buyer)
    
    # Budget range filtering
    if budget_range:
        if budget_range == 'under_100k':
            tenders_qs = tenders_qs.filter(value_amount__lt=100000)
        elif budget_range == '100k_1m':
            tenders_qs = tenders_qs.filter(value_amount__gte=100000, value_amount__lt=1000000)
        elif budget_range == '1m_10m':
            tenders_qs = tenders_qs.filter(value_amount__gte=1000000, value_amount__lt=10000000)
        elif budget_range == 'over_10m':
            tenders_qs = tenders_qs.filter(value_amount__gte=10000000)
    
    # Deadline filtering
    if deadline:
        today = datetime.now().date()
        if deadline == 'next_7_days':
            end_date = today + timedelta(days=7)
            tenders_qs = tenders_qs.filter(tender_period_end_date__gte=today, tender_period_end_date__lte=end_date)
        elif deadline == 'next_30_days':
            end_date = today + timedelta(days=30)
            tenders_qs = tenders_qs.filter(tender_period_end_date__gte=today, tender_period_end_date__lte=end_date)
        elif deadline == 'next_90_days':
            end_date = today + timedelta(days=90)
            tenders_qs = tenders_qs.filter(tender_period_end_date__gte=today, tender_period_end_date__lte=end_date)
    
    # Order by relevance (most recent first)
    tenders_qs = tenders_qs.order_by('-tender_period_end_date')
    
    # Extract provinces from buyer names for tenders with 'Not specified' province
    for tender in tenders_qs.filter(province__in=['Not specified', '', None]):
        extracted_province = extract_province_from_buyer(tender.buyer_name)
        if extracted_province:
            tender.province = extracted_province
            tender.save()
    
    # Get filter options from database
    provinces = list(Tender.objects.values_list('province', flat=True).distinct().exclude(province__isnull=True).exclude(province=''))
    buyers = list(Tender.objects.values_list('buyer_name', flat=True).distinct().exclude(buyer_name__isnull=True).exclude(buyer_name='')[:50])  # Limit to 50 for performance
    
    budget_ranges = [
        ('under_100k', 'Under R100,000'),
        ('100k_1m', 'R100,000 - R1,000,000'),
        ('1m_10m', 'R1,000,000 - R10,000,000'),
        ('over_10m', 'Over R10,000,000')
    ]
    
    deadline_ranges = [
        ('next_7_days', 'Next 7 days'),
        ('next_30_days', 'Next 30 days'),
        ('next_90_days', 'Next 90 days')
    ]
    
    # Pagination
    paginator = Paginator(tenders_qs, 10)  # 10 tenders per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Get workspace items from session for anonymous users
    session_workspace = request.session.get('workspace_tender_ids', [])
    workspace_tender_ids = set(session_workspace)
    
    context = {
        'tenders': page_obj,
        'keywords': keywords,
        'provinces': provinces,
        'buyers': buyers,
        'budget_ranges': budget_ranges,
        'deadline_ranges': deadline_ranges,
        'selected_province': province,
        'selected_buyer': buyer,
        'selected_budget_range': budget_range,
        'selected_deadline': deadline,
        'total_results': tenders_qs.count(),
        'workspace_tender_ids': workspace_tender_ids,
        'is_public': True,  # Flag to indicate this is public view
        'has_search_params': has_search_params,  # Flag to indicate if search was performed
    }
    
    return render(request, 'tenders/public_search.html', context)


# API endpoint for search
@csrf_exempt
def api_search_tenders(request):
    if request.method == 'GET':
        # Get search parameters from query string
        query = request.GET.get('query', '')
        province = request.GET.get('province', '')
        buyer = request.GET.get('buyer', '')
        budget_range = request.GET.get('budget_range', '')
        deadline = request.GET.get('deadline', '')
        
        # Prepare search parameters
        search_params = {
            'query': query
        }
        
        if province:
            search_params['province'] = province
        if buyer:
            search_params['buyer'] = buyer
        if budget_range:
            search_params['budget_range'] = budget_range
        if deadline:
            search_params['deadline'] = deadline
        
        # Call the external search API
        try:
            response = requests.get(f"{API_BASE_URL}/api/search", params=search_params)
            response.raise_for_status()
            search_results = response.json()
            
            return JsonResponse({
                'success': True,
                'results': search_results.get('results', []),
                'total': len(search_results.get('results', [])),
                'query': query
            })
            
        except requests.exceptions.RequestException as e:
            # If external API fails, return mock data for now
            mock_results = [
                {
                    'id': 'tender_001',
                    'title': 'IT Services for Government Department',
                    'description': 'Provision of comprehensive IT services including software development and maintenance.',
                    'budget': 500000,
                    'deadline': '2024-03-15',
                    'province': 'Western Cape',
                    'buyer': 'Department of Technology'
                },
                {
                    'id': 'tender_002', 
                    'title': 'Construction Services',
                    'description': 'Building construction and renovation services for public facilities.',
                    'budget': 1200000,
                    'deadline': '2024-04-20',
                    'province': 'Gauteng',
                    'buyer': 'Department of Public Works'
                }
            ]
            
            # Filter mock results based on query
            if query:
                filtered_results = []
                for result in mock_results:
                    if (query.lower() in result['title'].lower() or 
                        query.lower() in result['description'].lower()):
                        filtered_results.append(result)
                mock_results = filtered_results
            
            return JsonResponse({
                'success': True,
                'results': mock_results,
                'total': len(mock_results),
                'query': query,
                'note': 'Using mock data - external API unavailable'
            })
    
    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

# Tender detail view
@login_required
def tender_detail(request, tender_id):
    # Try to get tender from database
    try:
        tender = Tender.objects.get(tender_id=tender_id)
    except Tender.DoesNotExist:
        # If not in database, fetch from API
        try:
            response = requests.get(f"{API_BASE_URL}/api/OCDSReleases/{tender_id}")
            response.raise_for_status()
            tender_data = response.json()
            
            # Create tender in database
            tender = Tender(
                ocid=tender_data.get('ocid'),
                tender_id=tender_id,
                title=tender_data.get('title'),
                description=tender_data.get('description'),
                buyer_name=tender_data.get('buyer_name'),
                province=tender_data.get('province'),
                budget_min=tender_data.get('budget_min'),
                budget_max=tender_data.get('budget_max'),
                value_currency=tender_data.get('value_currency', 'ZAR'),
                tender_period_end_date=datetime.fromisoformat(tender_data.get('deadline')) if tender_data.get('deadline') else None,
                summary=tender_data.get('summary')
            )
            tender.save()
            
        except requests.RequestException as e:
            messages.error(request, f"Error fetching tender details: {str(e)}")
            return redirect('search_tenders')
    
    # Get team
    team = request.user.team
    
    # Check if tender is in workspace
    try:
        workspace_item = WorkspaceItem.objects.get(tender=tender, team=team)
        in_workspace = True
    except WorkspaceItem.DoesNotExist:
        workspace_item = None
        in_workspace = False
    
    # Get readiness score if available
    try:
        readiness_score = ReadinessScore.objects.get(tender=tender, team=team)
    except ReadinessScore.DoesNotExist:
        readiness_score = None
    
    # Get document summaries
    document_summaries = DocumentSummary.objects.filter(tender=tender)
    
    context = {
        'tender': tender,
        'workspace_item': workspace_item,
        'in_workspace': in_workspace,
        'readiness_score': readiness_score,
        'document_summaries': document_summaries
    }
    
    return render(request, 'tenders/tender_detail.html', context)


def public_tender_detail(request, tender_id):
    """Public tender detail view for anonymous users"""
    # Try to get tender from database
    try:
        tender = Tender.objects.get(tender_id=tender_id)
    except Tender.DoesNotExist:
        # If not in database, fetch from API
        try:
            response = requests.get(f"{API_BASE_URL}/api/OCDSReleases/{tender_id}")
            response.raise_for_status()
            tender_data = response.json()
            
            # Create tender in database
            tender = Tender(
                ocid=tender_data.get('ocid'),
                tender_id=tender_id,
                title=tender_data.get('title'),
                description=tender_data.get('description'),
                buyer_name=tender_data.get('buyer_name'),
                province=tender_data.get('province'),
                budget_min=tender_data.get('budget_min'),
                budget_max=tender_data.get('budget_max'),
                value_currency=tender_data.get('value_currency', 'ZAR'),
                tender_period_end_date=datetime.fromisoformat(tender_data.get('deadline')) if tender_data.get('deadline') else None,
                summary=tender_data.get('summary')
            )
            tender.save()
            
        except requests.RequestException as e:
            messages.error(request, f"Error fetching tender details: {str(e)}")
            return redirect('tenders:public_search_tenders')
    
    # Check if tender is in session workspace
    session_workspace = request.session.get('workspace_tender_ids', [])
    in_workspace = tender.id in session_workspace
    
    # Get status from session if in workspace
    workspace_status = None
    if in_workspace:
        session_statuses = request.session.get('workspace_statuses', {})
        workspace_status = session_statuses.get(str(tender.id), 'interested')
    
    context = {
        'tender': tender,
        'in_workspace': in_workspace,
        'workspace_status': workspace_status,
        'is_public': True,
        'status_choices': WorkspaceItem.STATUS_CHOICES,
    }
    
    return render(request, 'tenders/public_tender_detail.html', context)


# Add to workspace
@login_required
@require_POST
def add_to_workspace(request, tender_id):
    tender = get_object_or_404(Tender, tender_id=tender_id)
    team = request.user.team
    
    # Check if already in workspace
    workspace_item, created = WorkspaceItem.objects.get_or_create(
        tender=tender,
        team=team,
        defaults={'updated_by': request.user}
    )
    
    if created:
        messages.success(request, f"Added '{tender.title}' to your workspace.")
    else:
        messages.info(request, f"'{tender.title}' is already in your workspace.")
    
    return redirect('tenders:tender_detail', tender_id=tender_id)

# Remove from workspace
@login_required
@require_POST
def remove_from_workspace(request, tender_id):
    tender = get_object_or_404(Tender, tender_id=tender_id)
    team = request.user.team
    
    try:
        workspace_item = WorkspaceItem.objects.get(tender=tender, team=team)
        workspace_item.delete()
        messages.success(request, f"Removed '{tender.title}' from your workspace.")
    except WorkspaceItem.DoesNotExist:
        messages.error(request, "This tender is not in your workspace.")
    
    return redirect('tenders:tender_detail', tender_id=tender_id)


@require_POST
def public_add_to_workspace(request, tender_id):
    """Public version of add_to_workspace that uses session storage"""
    tender = get_object_or_404(Tender, tender_id=tender_id)
    
    # Get or create session workspace
    session_workspace = request.session.get('workspace_tender_ids', [])
    
    if tender.id not in session_workspace:
        session_workspace.append(tender.id)
        request.session['workspace_tender_ids'] = session_workspace
        request.session.modified = True
        messages.success(request, f"Added '{tender.title}' to your workspace.")
    else:
        messages.info(request, f"'{tender.title}' is already in your workspace.")
    
    return redirect('tenders:public_tender_detail', tender_id=tender_id)


@require_POST
def public_remove_from_workspace(request, tender_id):
    """Public version of remove_from_workspace that uses session storage"""
    tender = get_object_or_404(Tender, tender_id=tender_id)
    
    # Get session workspace
    session_workspace = request.session.get('workspace_tender_ids', [])
    
    if tender.id in session_workspace:
        session_workspace.remove(tender.id)
        request.session['workspace_tender_ids'] = session_workspace
        
        # Also remove from statuses
        session_statuses = request.session.get('workspace_statuses', {})
        if str(tender.id) in session_statuses:
            del session_statuses[str(tender.id)]
            request.session['workspace_statuses'] = session_statuses
        
        request.session.modified = True
        messages.success(request, f"Removed '{tender.title}' from your workspace.")
    else:
        messages.error(request, "This tender is not in your workspace.")
    
    return redirect('tenders:public_tender_detail', tender_id=tender_id)


@require_POST
def public_update_workspace_status(request, tender_id):
    """Public version of update_workspace_status that uses session storage"""
    tender = get_object_or_404(Tender, tender_id=tender_id)
    new_status = request.POST.get('status')
    
    # Check if tender is in session workspace
    session_workspace = request.session.get('workspace_tender_ids', [])
    if tender.id not in session_workspace:
        messages.error(request, "This tender is not in your workspace.")
        return redirect('tenders:public_tender_detail', tender_id=tender_id)
    
    if new_status in dict(WorkspaceItem.STATUS_CHOICES).keys():
        # Update status in session
        session_statuses = request.session.get('workspace_statuses', {})
        session_statuses[str(tender.id)] = new_status
        request.session['workspace_statuses'] = session_statuses
        request.session.modified = True
        
        messages.success(request, f"Updated status for '{tender.title}' to {new_status}.")
    else:
        messages.error(request, "Invalid status.")
    
    return redirect('tenders:public_workspace')


# Update workspace item status
@login_required
@require_POST
def update_workspace_status(request, tender_id):
    # Get workspace item by tender_id and team
    workspace_item = get_object_or_404(WorkspaceItem, tender__tender_id=tender_id, team=request.user.team)
    new_status = request.POST.get('status')
    
    if new_status in dict(WorkspaceItem.STATUS_CHOICES).keys():
        workspace_item.status = new_status
        workspace_item.updated_by = request.user
        workspace_item.save()
        messages.success(request, f"Status updated to '{new_status}'.")
    else:
        messages.error(request, "Invalid status.")
    
    return redirect('tenders:workspace_detail', workspace_item_id=workspace_item.id)

# Workspace view
@login_required
def workspace(request):
    team = request.user.team
    status_filter = request.GET.get('status', '')
    
    workspace_items = WorkspaceItem.objects.filter(team=team)
    
    if status_filter and status_filter != 'All':
        workspace_items = workspace_items.filter(status=status_filter)
    
    # Sort by readiness score (highest first)
    workspace_items = sorted(
        workspace_items,
        key=lambda item: getattr(item.tender.readiness_scores.filter(team=team).first(), 'suitability_score', 0),
        reverse=True
    )
    
    context = {
        'workspace_items': workspace_items,
        'status_filter': status_filter,
        'status_choices': WorkspaceItem.STATUS_CHOICES
    }
    
    return render(request, 'tenders/workspace.html', context)


def public_workspace(request):
    """Public workspace view that uses session storage for anonymous users"""
    
    # Get workspace items from session
    session_workspace = request.session.get('workspace_tender_ids', [])
    status_filter = request.GET.get('status', '')
    
    if not session_workspace:
        # No items in workspace
        context = {
            'workspace_items': [],
            'status_filter': status_filter,
            'status_choices': WorkspaceItem.STATUS_CHOICES,
            'is_public': True,
        }
        return render(request, 'tenders/public_workspace.html', context)
    
    # Get tender objects for the IDs in session
    tenders = Tender.objects.filter(id__in=session_workspace)
    
    # Create workspace-like items from session data
    workspace_items = []
    session_statuses = request.session.get('workspace_statuses', {})
    
    for tender in tenders:
        # Create a simple object to mimic WorkspaceItem
        class SessionWorkspaceItem:
            def __init__(self, tender, status='interested'):
                self.tender = tender
                self.status = status
                self.id = tender.id
                self.created_at = None
        
        status = session_statuses.get(str(tender.id), 'interested')
        workspace_item = SessionWorkspaceItem(tender, status)
        
        # Apply status filter
        if status_filter and status_filter != 'All' and status != status_filter:
            continue
            
        workspace_items.append(workspace_item)
    
    # Sort by tender deadline (most recent first)
    workspace_items = sorted(
        workspace_items,
        key=lambda item: item.tender.tender_period_end_date or datetime.now().date(),
        reverse=True
    )
    
    context = {
        'workspace_items': workspace_items,
        'status_filter': status_filter,
        'status_choices': WorkspaceItem.STATUS_CHOICES,
        'is_public': True,
    }
    
    return render(request, 'tenders/public_workspace.html', context)


# Workspace item detail view
@login_required
def workspace_detail(request, workspace_item_id):
    try:
        workspace_item = WorkspaceItem.objects.get(id=workspace_item_id, team=request.user.team)
        notes = Note.objects.filter(workspace_item=workspace_item).order_by('-created_at')
        tasks = Task.objects.filter(workspace_item=workspace_item).order_by('due_date')
    except WorkspaceItem.DoesNotExist:
        messages.error(request, "Workspace item not found.")
        return redirect('workspace')
    
    # Get team members for task assignment
    team_members = CustomUser.objects.filter(team=request.user.team)
    
    context = {
        'workspace_item': workspace_item,
        'notes': notes,
        'tasks': tasks,
        'team_members': team_members,
        'status_choices': WorkspaceItem.STATUS_CHOICES
    }
    
    return render(request, 'tenders/workspace_detail.html', context)

# Add note to workspace item
@login_required
@require_POST
def add_note(request, workspace_item_id):
    workspace_item = get_object_or_404(WorkspaceItem, id=workspace_item_id, team=request.user.team)
    content = request.POST.get('content')
    
    if content:
        note = Note(
            workspace_item=workspace_item,
            content=content,
            created_by=request.user
        )
        note.save()
        messages.success(request, "Note added successfully.")
    else:
        messages.error(request, "Note content cannot be empty.")
    
    return redirect('workspace_detail', workspace_item_id=workspace_item_id)

# Add task to workspace item
@login_required
@require_POST
def add_task(request, workspace_item_id):
    workspace_item = get_object_or_404(WorkspaceItem, id=workspace_item_id, team=request.user.team)
    description = request.POST.get('description')
    assigned_to_id = request.POST.get('assigned_to')
    due_date_str = request.POST.get('due_date')
    
    if not description:
        messages.error(request, "Task description cannot be empty.")
        return redirect('workspace_detail', workspace_item_id=workspace_item_id)
    
    # Create task
    task = Task(
        workspace_item=workspace_item,
        description=description,
        created_by=request.user
    )
    
    # Set assigned user if provided
    if assigned_to_id:
        try:
            assigned_user = CustomUser.objects.get(id=assigned_to_id, team=request.user.team)
            task.assigned_to = assigned_user
        except CustomUser.DoesNotExist:
            messages.warning(request, "Selected user not found in your team.")
    
    # Set due date if provided
    if due_date_str:
        try:
            task.due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
        except ValueError:
            messages.warning(request, "Invalid date format. Using no due date.")
    
    task.save()
    messages.success(request, "Task added successfully.")
    
    return redirect('workspace_detail', workspace_item_id=workspace_item_id)

# Update task status
@login_required
@require_POST
def update_task_status(request, task_id):
    task = get_object_or_404(Task, id=task_id, workspace_item__team=request.user.team)
    new_status = request.POST.get('status')
    
    if new_status in dict(Task.STATUS_CHOICES).keys():
        task.status = new_status
        task.save()
        messages.success(request, f"Task status updated to '{new_status}'.")
    else:
        messages.error(request, "Invalid status.")
    
    return redirect('workspace_detail', workspace_item_id=task.workspace_item.id)

# Company profile view and edit
def calculate_profile_completeness(profile):
    """Calculate profile completeness percentage and missing items."""
    if not profile:
        return 0, [
            {'name': 'Company Profile', 'importance': 'Critical'},
            {'name': 'Industry Sector', 'importance': 'High'},
            {'name': 'Services Provided', 'importance': 'High'},
            {'name': 'Geographic Coverage', 'importance': 'Medium'},
            {'name': 'Years of Experience', 'importance': 'Medium'},
            {'name': 'Contact Information', 'importance': 'High'},
            {'name': 'Company Size', 'importance': 'Medium'},
            {'name': 'Registration Number', 'importance': 'High'},
        ]
    
    # Define required fields with their importance
    required_fields = [
        ('industry_sector', 'Industry Sector', 'High', 15),
        ('services_provided', 'Services Provided', 'High', 15),
        ('geographic_coverage', 'Geographic Coverage', 'Medium', 10),
        ('years_experience', 'Years of Experience', 'Medium', 10),
        ('contact_email', 'Contact Email', 'High', 15),
        ('contact_phone', 'Contact Phone', 'Medium', 10),
        ('company_size', 'Company Size', 'Medium', 10),
        ('company_registration_number', 'Registration Number', 'High', 15),
    ]
    
    total_weight = sum(field[3] for field in required_fields)
    completed_weight = 0
    missing_items = []
    
    for field_name, display_name, importance, weight in required_fields:
        field_value = getattr(profile, field_name, None)
        
        # Check if field is completed
        is_completed = False
        if field_name in ['services_provided', 'geographic_coverage']:
            # These are list fields
            is_completed = field_value and len(field_value) > 0
        elif field_name == 'years_experience':
            # Numeric field
            is_completed = field_value is not None and field_value > 0
        else:
            # String fields
            is_completed = field_value and field_value.strip()
        
        if is_completed:
            completed_weight += weight
        else:
            missing_items.append({
                'name': display_name,
                'importance': importance
            })
    
    # Check certifications (optional but adds to completeness)
    if profile.certifications.exists():
        completed_weight += 10  # Bonus for having certifications
        total_weight += 10
    else:
        missing_items.append({
            'name': 'Certifications',
            'importance': 'Medium'
        })
        total_weight += 10
    
    # Check BBBEE level (optional but adds to completeness)
    if profile.bbbee_level:
        completed_weight += 5  # Bonus for BBBEE level
        total_weight += 5
    else:
        missing_items.append({
            'name': 'BBBEE Level',
            'importance': 'Low'
        })
        total_weight += 5
    
    # Check CIDB grade (optional but adds to completeness)
    if profile.cidb_grade:
        completed_weight += 5  # Bonus for CIDB grade
        total_weight += 5
    else:
        missing_items.append({
            'name': 'CIDB Grade',
            'importance': 'Low'
        })
        total_weight += 5
    
    # Check website (optional but adds to completeness)
    if profile.website and profile.website.strip():
        completed_weight += 5  # Bonus for website
        total_weight += 5
    else:
        missing_items.append({
            'name': 'Website',
            'importance': 'Low'
        })
        total_weight += 5
    
    # Calculate percentage
    completeness_percentage = round((completed_weight / total_weight) * 100) if total_weight > 0 else 0
    
    return completeness_percentage, missing_items

@login_required
def company_profile(request):
    team = request.user.team
    
    try:
        profile = CompanyProfile.objects.get(team=team)
    except CompanyProfile.DoesNotExist:
        profile = None
    
    # Get all certifications
    certifications = Certification.objects.all()
    
    if request.method == 'POST':
        # Handle form submission
        if profile:
            # Update existing profile
            profile.industry_sector = request.POST.get('industry_sector', 'Other')  # Default to 'Other' if not provided
            profile.services_provided = request.POST.getlist('services_provided')
            profile.geographic_coverage = request.POST.getlist('geographic_coverage')
            profile.years_experience = int(request.POST.get('years_experience', 0))
            profile.contact_email = request.POST.get('contact_email') or request.user.email
            profile.contact_phone = request.POST.get('contact_phone')
            profile.website = request.POST.get('website')
            profile.bbbee_level = int(request.POST.get('bbbee_level', 0)) if request.POST.get('bbbee_level') else None
            profile.cidb_grade = request.POST.get('cidb_grade')
            profile.company_size = request.POST.get('company_size')
            profile.company_registration_number = request.POST.get('company_registration_number')
            
            # Handle certifications
            selected_certs = request.POST.getlist('certifications')
            profile.certifications.clear()
            for cert_id in selected_certs:
                # Clean the ID - remove whitespace, newlines, etc.
                if cert_id and isinstance(cert_id, str):
                    # Split by newlines or other whitespace and process each part
                    parts = cert_id.strip().split()
                    for part in parts:
                        try:
                            # Try to get certification by ID if it's numeric
                            if part.isdigit():
                                cert = Certification.objects.get(id=int(part))
                                profile.certifications.add(cert)
                        except (ValueError, Certification.DoesNotExist):
                            # If ID is not valid, try to get by name
                            try:
                                cert = Certification.objects.filter(name__icontains=part).first()
                                if cert:
                                    profile.certifications.add(cert)
                            except Exception:
                                pass
            
            profile.save()
            messages.success(request, "Company profile updated successfully.")
        else:
            # Create new profile
            profile = CompanyProfile(
                team=team,
                industry_sector=request.POST.get('industry_sector', 'Other'),  # Default to 'Other' if not provided
                services_provided=request.POST.getlist('services_provided'),
                geographic_coverage=request.POST.getlist('geographic_coverage'),
                years_experience=int(request.POST.get('years_experience', 0)),
                contact_email=request.POST.get('contact_email') or request.user.email,
                contact_phone=request.POST.get('contact_phone'),
                website=request.POST.get('website'),
                bbbee_level=int(request.POST.get('bbbee_level', 0)) if request.POST.get('bbbee_level') else None,
                cidb_grade=request.POST.get('cidb_grade'),
                company_size=request.POST.get('company_size'),
                company_registration_number=request.POST.get('company_registration_number')
            )
            profile.save()
            
            # Handle certifications
            selected_certs = request.POST.getlist('certifications')
            for cert_id in selected_certs:
                # Clean the ID - remove whitespace, newlines, etc.
                if cert_id and isinstance(cert_id, str):
                    # Split by newlines or other whitespace and process each part
                    parts = cert_id.strip().split()
                    for part in parts:
                        try:
                            # Try to get certification by ID if it's numeric
                            if part.isdigit():
                                cert = Certification.objects.get(id=int(part))
                                profile.certifications.add(cert)
                        except (ValueError, Certification.DoesNotExist):
                            # If ID is not valid, try to get by name
                            try:
                                cert = Certification.objects.filter(name__icontains=part).first()
                                if cert:
                                    profile.certifications.add(cert)
                            except Exception:
                                pass
            
            messages.success(request, "Company profile created successfully.")
        
        return redirect('tenders:company_profile')
    
    # South African provinces
    provinces = [
        'Eastern Cape', 'Free State', 'Gauteng', 'KwaZulu-Natal', 'Limpopo',
        'Mpumalanga', 'North West', 'Northern Cape', 'Western Cape'
    ]
    
    # Common industry sectors
    industry_sectors = [
        'Construction', 'Information Technology', 'Professional Services',
        'Manufacturing', 'Retail', 'Healthcare', 'Education', 'Transportation',
        'Agriculture', 'Mining', 'Energy', 'Financial Services', 'Tourism',
        'Security Services', 'Telecommunications', 'Other'
    ]
    
    # CIDB grades
    cidb_grades = [
        '1', '2', '3', '4', '5', '6', '7', '8', '9'
    ]
    
    # Calculate profile completeness
    profile_completeness, missing_items = calculate_profile_completeness(profile)
    
    # Get company documents
    company_documents = CompanyDocument.objects.filter(team=request.user.team).order_by('-uploaded_at')
    
    context = {
        'profile': profile,
        'provinces': provinces,
        'industry_sectors': industry_sectors,
        'cidb_grades': cidb_grades,
        'certifications': certifications,
        'profile_completeness': profile_completeness,
        'missing_items': missing_items,
        'company_documents': company_documents
    }
    
    return render(request, 'tenders/company_profile.html', context)

@login_required
@require_POST
def upload_company_document(request):
    """Handle company document uploads"""
    if request.method == 'POST':
        # Get the uploaded file
        uploaded_file = request.FILES.get('document_file')
        if not uploaded_file:
            messages.error(request, "No file was uploaded.")
            return redirect('tenders:company_profile')
        
        # Get form data
        document_type = request.POST.get('document_type')
        description = request.POST.get('document_description', '')
        
        if not document_type:
            messages.error(request, "Please select a document type.")
            return redirect('tenders:company_profile')
        
        try:
            # Create the company document
            company_document = CompanyDocument.objects.create(
                team=request.user.team,
                document_type=document_type,
                document_file=uploaded_file,
                description=description,
                uploaded_by=request.user
            )
            
            messages.success(request, f"Document '{uploaded_file.name}' uploaded successfully.")
            
        except Exception as e:
            messages.error(request, f"Error uploading document: {str(e)}")
        
    return redirect('tenders:company_profile')

@login_required
@require_POST
def delete_company_document(request, document_id):
    """Handle company document deletion"""
    try:
        document = get_object_or_404(CompanyDocument, id=document_id, team=request.user.team)
        document_name = document.document_file.name
        document.delete()
        messages.success(request, f"Document '{document_name}' deleted successfully.")
    except Exception as e:
        messages.error(request, f"Error deleting document: {str(e)}")
    
    return redirect('tenders:company_profile')

# Check tender readiness
@login_required
@require_POST
def check_readiness(request, tender_id):
    tender = get_object_or_404(Tender, tender_id=tender_id)
    team = request.user.team
    
    # Check if company profile exists
    try:
        company_profile = CompanyProfile.objects.get(team=team)
    except CompanyProfile.DoesNotExist:
        messages.error(request, "You need to complete your company profile before checking readiness.")
        return redirect('tenders:company_profile')
    
    # Call readiness check API
    try:
        # Prepare company profile data
        profile_data = {
            'team_id': str(team.id),
            'industry_sector': company_profile.industry_sector,
            'services_provided': company_profile.services_provided,
            'geographic_coverage': company_profile.geographic_coverage,
            'years_experience': company_profile.years_experience,
            'bbbee_level': company_profile.bbbee_level,
            'cidb_grade': company_profile.cidb_grade
        }
        
        # Get certifications
        certifications = []
        for cert in company_profile.certifications.all():
            certifications.append({
                'name': cert.name,
                'level': cert.level
            })
        profile_data['certifications'] = certifications
        
        # Call API
        response = requests.post(
            f"{API_BASE_URL}/api/readiness/check",
            json={
                'tender_id': tender_id,
                'company_profile': profile_data
            }
        )
        response.raise_for_status()
        result = response.json()
        
        # Save or update readiness score
        readiness_score, created = ReadinessScore.objects.update_or_create(
            tender=tender,
            team=team,
            defaults={
                'suitability_score': result.get('suitability_score', 0),
                'checklist': result.get('checklist', []),
                'recommendation': result.get('recommendation', '')
            }
        )
        
        # Add to workspace if not already there
        workspace_item, created = WorkspaceItem.objects.get_or_create(
            tender=tender,
            team=team,
            defaults={'updated_by': request.user}
        )
        
        messages.success(request, "Readiness check completed successfully.")
        
    except requests.RequestException as e:
        messages.error(request, f"Error checking readiness: {str(e)}")
    
    return redirect('tenders:tender_detail', tender_id=tender_id)

# Document upload and summarization
@login_required
@require_POST
def upload_document(request, tender_id):
    tender = get_object_or_404(Tender, tender_id=tender_id)
    
    if 'document' not in request.FILES:
        messages.error(request, "No document uploaded.")
        return redirect('tenders:tender_detail', tender_id=tender_id)
    
    document = request.FILES['document']
    
    # Check file type
    allowed_types = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/zip']
    if document.content_type not in allowed_types:
        messages.error(request, "Only PDF, DOCX, and ZIP files are supported.")
        return redirect('tenders:tender_detail', tender_id=tender_id)
    
    try:
        # Create multipart form data
        files = {'file': (document.name, document, document.content_type)}
        
        # Call document processing API
        response = requests.post(
            f"{API_BASE_URL}/api/summary/extract",
            files=files
        )
        response.raise_for_status()
        result = response.json()
        
        # Save document summary
        document_summary = DocumentSummary(
            tender=tender,
            filename=document.name,
            content_type=document.content_type,
            text_content=result.get('text_content', ''),
            summary=result.get('summary', ''),
            created_by=request.user
        )
        document_summary.save()
        
        messages.success(request, "Document processed and summarized successfully.")
        
    except requests.RequestException as e:
        messages.error(request, f"Error processing document: {str(e)}")
    
    return redirect('tenders:tender_detail', tender_id=tender_id)

# Document summary view
@login_required
def document_summary(request, tender_id, document_id):
    tender = get_object_or_404(Tender, tender_id=tender_id)
    document = get_object_or_404(DocumentSummary, id=document_id, tender=tender)
    
    # Get related documents
    related_documents = DocumentSummary.objects.filter(tender=tender).exclude(id=document_id)[:5]
    
    # Calculate dates for status badges
    today = datetime.now().date().strftime('%Y-%m-%d')
    week_from_now = (datetime.now() + timedelta(days=7)).date().strftime('%Y-%m-%d')
    
    # Parse the summary JSON
    try:
        summary_data = json.loads(document.summary)
    except (json.JSONDecodeError, TypeError):
        # If summary is not valid JSON, create a basic structure
        summary_data = {
            "executive_summary": "Summary could not be generated. Please try regenerating the summary.",
            "key_requirements": [],
            "important_dates": [],
            "detailed_analysis": {
                "scope": "Not available",
                "eligibility": "Not available",
                "evaluation": "Not available",
                "submission": "Not available"
            }
        }
    
    # Add document type and color
    document_types = {
        'application/pdf': {'name': 'PDF', 'color': 'danger'},
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': {'name': 'DOCX', 'color': 'primary'},
        'application/zip': {'name': 'ZIP', 'color': 'warning'}
    }
    
    document_type_info = document_types.get(document.content_type, {'name': 'Unknown', 'color': 'secondary'})
    document.document_type = document_type_info['name']
    document.document_type_color = document_type_info['color']
    
    # Add document type and color to related documents
    for doc in related_documents:
        doc_type_info = document_types.get(doc.content_type, {'name': 'Unknown', 'color': 'secondary'})
        doc.document_type = doc_type_info['name']
        doc.document_type_color = doc_type_info['color']
    
    # Calculate file size
    document.file_size = len(document.text_content.encode('utf-8'))
    
    context = {
        'tender': tender,
        'document': document,
        'summary': summary_data,
        'related_documents': related_documents,
        'today': today,
        'week_from_now': week_from_now
    }
    
    return render(request, 'tenders/document_summary.html', context)

# Regenerate document summary
@login_required
@require_POST
def regenerate_summary(request, tender_id, document_id):
    tender = get_object_or_404(Tender, tender_id=tender_id)
    document = get_object_or_404(DocumentSummary, id=document_id, tender=tender)
    
    focus_areas = request.POST.get('focus_areas', '')
    
    try:
        # Call document processing API with existing text content
        payload = {
            'text_content': document.text_content,
            'focus_areas': focus_areas
        }
        
        response = requests.post(
            f"{API_BASE_URL}/api/summary/generate",
            json=payload
        )
        response.raise_for_status()
        result = response.json()
        
        # Update document summary
        document.summary = result.get('summary', '')
        document.save()
        
        messages.success(request, "Document summary regenerated successfully.")
        
    except requests.RequestException as e:
        messages.error(request, f"Error regenerating summary: {str(e)}")
    
    return redirect('tenders:document_summary', tender_id=tender_id, document_id=document_id)

# Download document
# API endpoint for document summary extraction
@require_http_methods(["POST"])
@csrf_exempt
def api_summary_extract(request):
    if 'file' not in request.FILES:
        return JsonResponse({'error': 'No file provided'}, status=400)
    
    document = request.FILES['file']
    
    # Check file type
    allowed_types = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/zip']
    if document.content_type not in allowed_types:
        return JsonResponse({'error': 'Unsupported file type'}, status=400)
    
    try:
        # Process the document (extract text)
        text_content = f"Extracted text from {document.name}"
        
        # Generate a summary
        summary = f"Summary of {document.name}: This is a document related to tenders and procurement."
        
        return JsonResponse({
            'text_content': text_content,
            'summary': summary
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def download_document(request, tender_id, document_id):
    tender = get_object_or_404(Tender, tender_id=tender_id)
    document = get_object_or_404(DocumentSummary, id=document_id, tender=tender)
    
    # Create a response with the document content
    response = HttpResponse(content_type=document.content_type)
    response['Content-Disposition'] = f'attachment; filename="{document.filename}"'
    
    # For this implementation, we'll use a mock file content since we don't have actual file storage
    # In a real implementation, you would retrieve the file from storage (S3, local filesystem, etc.)
    
    # Mock file content based on content type
    if document.content_type == 'application/pdf':
        # Generate a simple PDF
        try:
            from reportlab.pdfgen import canvas
            from io import BytesIO
            
            buffer = BytesIO()
            p = canvas.Canvas(buffer)
            p.drawString(100, 750, f"Tender Document: {document.filename}")
            p.drawString(100, 700, f"Tender ID: {tender.tender_id}")
            p.drawString(100, 650, "This is a placeholder for the actual document content.")
            p.drawString(100, 600, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            p.showPage()
            p.save()
            
            pdf = buffer.getvalue()
            buffer.close()
            response.write(pdf)
        except ImportError:
            # If reportlab is not available, return plain text
            response = HttpResponse(content_type='text/plain')
            response['Content-Disposition'] = f'attachment; filename="{document.filename}.txt"'
            response.write(f"Tender Document: {document.filename}\n")
            response.write(f"Tender ID: {tender.tender_id}\n\n")
            response.write("This is a placeholder for the actual document content.\n")
            response.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        # For other file types, return the text content as a plain text file
        response = HttpResponse(content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename="{document.filename}.txt"'
        response.write(document.text_content[:1000])  # Limit to first 1000 chars for demo
        response.write("\n\n[... Content truncated for demonstration purposes ...]")
    
    return response

# Analytics view
@login_required
def analytics(request):
    from django.db.models import Sum, Count, Avg, Q, F, Value, Case, When, DecimalField
    from django.db.models.functions import TruncMonth, TruncWeek, Coalesce
    from datetime import datetime, timedelta
    from functools import reduce
    import json
    
    # Get user's team
    team = request.user.team
    
    if not team:
        messages.error(request, "You are not assigned to a team. Please contact an administrator.")
        return redirect('dashboard')
    
    try:
        # Get workspace items for the team
        workspace_items = WorkspaceItem.objects.filter(team=team)
        
        # Get workspace item count
        workspace_count = workspace_items.count()
        status_data = {'total': workspace_count}
        
        # Get budget data where available
        tenders_with_budget = Tender.objects.filter(
            budget_min__isnull=False, 
            budget_max__isnull=False
        )
        
        # Calculate average budget for tenders
        avg_budget = tenders_with_budget.aggregate(
            avg_budget=Avg((F('budget_min') + F('budget_max')) / 2)
        )['avg_budget'] or 0
        
        # Get top buyers by tender count only (removed budget/revenue)
        top_buyers = workspace_items.values('tender__buyer_name').annotate(
            tender_count=Count('id')
        ).filter(
            tender__buyer_name__isnull=False
        ).order_by('-tender_count')[:10]
        
        # Format for template (without revenue/budget data)
        spend_by_buyer_data = []
        for item in top_buyers:
            spend_by_buyer_data.append({
                'buyer': item['tender__buyer_name'],
                'tender_count': item['tender_count'],
                'total_spend': 0  # Adding with zero value to prevent errors
            })
        
        # Extract province from tender data or buyer_name
        province_mapping = {
            'Eastern Cape': ['Eastern Cape'],
            'Western Cape': ['Western Cape', 'Cape Town', 'Cape Agulhas', 'Cape Winelands', 'Swellendam'],
            'Gauteng': ['Johannesburg', 'Ekurhuleni', 'Tshwane', 'Gauteng'],
            'KwaZulu-Natal': ['KwaZulu-Natal', 'eThekwini', 'Durban'],
            'Limpopo': ['Limpopo'],
            'Mpumalanga': ['Mpumalanga'],
            'North West': ['North West'],
            'Northern Cape': ['Northern Cape'],
            'Free State': ['Free State']
        }
        
        # Get province data directly from the database
        province_data = {}
        
        # Get provinces with direct values
        province_counts = Tender.objects.values('province').exclude(province__isnull=True).exclude(province='').annotate(
            count=Count('id'),
            total_budget=Sum(
                Case(
                    When(
                        budget_min__isnull=False,
                        budget_max__isnull=False,
                        then=(F('budget_min') + F('budget_max')) / 2
                    ),
                    default=Value(0),
                    output_field=DecimalField()
                )
            )
        )
        
        # Add provinces with direct values to the data
        for item in province_counts:
            province = item['province']
            province_data[province] = {
                'count': item['count'],
                'budget': item['total_budget'] or 0
            }
        
        # Handle national entities
        national_entities = ['ESKOM', 'Transnet', 'PRASA', 'Passenger Rail', 'Independent Development Trust']
        national_tenders = Tender.objects.filter(
            Q(province__isnull=True) | Q(province=''),
            reduce(lambda x, y: x | y, [Q(buyer_name__icontains=entity) for entity in national_entities])
        ).annotate(
            avg_budget=Case(
                When(
                    budget_min__isnull=False,
                    budget_max__isnull=False,
                    then=(F('budget_min') + F('budget_max')) / 2
                ),
                default=Value(0),
                output_field=DecimalField()
            )
        )
        
        if national_tenders.exists():
            province_data['National'] = {
                'count': national_tenders.count(),
                'budget': national_tenders.aggregate(Sum('avg_budget'))['avg_budget__sum'] or 0
            }
        
        # Handle remaining tenders with no province
        unknown_tenders = Tender.objects.filter(
            Q(province__isnull=True) | Q(province='')
        ).exclude(
            reduce(lambda x, y: x | y, [Q(buyer_name__icontains=entity) for entity in national_entities], Q())
        ).annotate(
            avg_budget=Case(
                When(
                    budget_min__isnull=False,
                    budget_max__isnull=False,
                    then=(F('budget_min') + F('budget_max')) / 2
                ),
                default=Value(0),
                output_field=DecimalField()
            )
        )
        
        if unknown_tenders.exists():
            province_data['Other/Unknown'] = {
                'count': unknown_tenders.count(),
                'budget': unknown_tenders.aggregate(Sum('avg_budget'))['avg_budget__sum'] or 0
            }
        
        # Format province data for template
        spend_by_province_data = []
        for province, data in sorted(province_data.items(), key=lambda x: x[1]['count'], reverse=True):
            spend_by_province_data.append({
                'province': province,
                'total_spend': data['budget'],
                'tender_count': data['count'],
                'avg_budget': data['budget'] / data['count'] if data['count'] > 0 else 0
            })
        
        # Get tender trends by creation date (weekly trends for last 12 weeks)
        twelve_weeks_ago = datetime.now() - timedelta(weeks=12)
        tender_trends = Tender.objects.filter(
            created_at__gte=twelve_weeks_ago
        ).annotate(
            week=TruncWeek('created_at'),
            avg_budget=Case(
                When(
                    budget_min__isnull=False,
                    budget_max__isnull=False,
                    then=(F('budget_min') + F('budget_max')) / 2
                ),
                default=Value(0),
                output_field=DecimalField()
            )
        ).values('week').annotate(
            count=Count('id'),
            total_budget=Sum('avg_budget')
        ).order_by('week')
        
        # Format for template
        tender_trends_data = []
        for item in tender_trends:
            tender_trends_data.append({
                'period': item['week'].strftime('%Y-%m-%d') if item['week'] else 'Unknown',
                'count': item['count'],
                'avg_budget': item['total_budget'] / item['count'] if item['count'] > 0 else 0
            })
        
        # Additional analytics for the template
        total_tenders = Tender.objects.count()
        total_value = tenders_with_budget.aggregate(
            total=Sum((F('budget_min') + F('budget_max')) / 2)
        )['total'] or 0
        
        # Get deadline distribution for charts (tenders by closing date)
        now = datetime.now()
        deadline_ranges = [
            ('Closed', Q(tender_period_end_date__lt=now)),
            ('This Week', Q(tender_period_end_date__gte=now, tender_period_end_date__lt=now + timedelta(days=7))),
            ('This Month', Q(tender_period_end_date__gte=now + timedelta(days=7), tender_period_end_date__lt=now + timedelta(days=30))),
            ('Next 3 Months', Q(tender_period_end_date__gte=now + timedelta(days=30), tender_period_end_date__lt=now + timedelta(days=90))),
            ('Future', Q(tender_period_end_date__gte=now + timedelta(days=90))),
        ]
        
        deadline_labels = []
        deadline_data = []
        for label, query in deadline_ranges:
            count = Tender.objects.filter(query, tender_period_end_date__isnull=False).count()
            deadline_labels.append(label)
            deadline_data.append(count)
        
        # Calculate tender status counts based on tender_period_end_date
        now = datetime.now()
        status_counts = {
            'open_count': Tender.objects.filter(tender_period_end_date__gt=now).count(),
            'closed_count': Tender.objects.filter(tender_period_end_date__lte=now).count(),
            'cancelled_count': 0,  # No longer tracking cancelled status
            'awarded_count': 0,    # No longer tracking awarded status
        }
        
        # Prepare data for charts
        spend_by_buyer_labels = [item['buyer'][:30] + '...' if len(item['buyer']) > 30 else item['buyer'] for item in spend_by_buyer_data[:10]]
        spend_by_buyer_chart_data = [item['tender_count'] for item in spend_by_buyer_data[:10]]
        # Removed budget data
        spend_by_buyer_budget_data = [0 for _ in spend_by_buyer_data[:10]]
        
        # Use the province data we already calculated
        spend_by_province_labels = [province for province in province_data.keys()]
        spend_by_province_chart_data = [data['count'] for data in province_data.values()]
        
        tender_trends_labels = [item['period'] for item in tender_trends_data]
        tender_trends_chart_data = [item['count'] for item in tender_trends_data]
        tender_trends_budget_data = [float(item['avg_budget']) for item in tender_trends_data]
        
        # Calculate activity metrics
        recent_tenders = Tender.objects.filter(
            created_at__gte=datetime.now() - timedelta(days=30)
        ).count()
        
        upcoming_deadlines = Tender.objects.filter(
            tender_period_end_date__gte=now,
            tender_period_end_date__lte=now + timedelta(days=7)
        ).count()
        
        # Get top buyers for table (using tender count only - removed revenue)
        top_buyers_table = []
        for item in spend_by_buyer_data[:5]:
            top_buyers_table.append({
                'name': item['buyer'],
                'count': item['tender_count']
            })
        
        # Prepare context for template
        context = {
            'total_tenders': total_tenders,
            'status_counts': status_counts,
            'recent_tenders': recent_tenders,
            'upcoming_deadlines': upcoming_deadlines,
            
            # Province distribution data
            'province_data': {
                'labels': json.dumps([p for p in province_data.keys()]),
                'values': json.dumps([p['count'] for p in province_data.values()])
            },
            
            # Monthly trends data
            'monthly_trends': {
                'labels': json.dumps(tender_trends_labels),
                'values': json.dumps(tender_trends_chart_data)
            },
            
            # Top buyers data (removed revenue/budget information)
            'top_buyers': [
                {
                    'name': item['buyer'],
                    'province': next((p for p, keywords in province_mapping.items() 
                                    if any(keyword.lower() in item['buyer'].lower() for keyword in keywords)), 'N/A'),
                    'count': item['tender_count']
                } for item in spend_by_buyer_data[:10]  # Show top 10 buyers
            ]
        }
        
        return render(request, 'tenders/analytics.html', context)
        
    except Exception as e:
        messages.error(request, f"Error calculating analytics: {str(e)}")
        context = {
            'total_tenders': 0,
            'status_counts': {'open_count': 0, 'closed_count': 0, 'awarded_count': 0, 'cancelled_count': 0, 'draft_count': 0},
            'recent_tenders': 0,
            'upcoming_deadlines': 0,
            
            # Province distribution data
            'province_data': {
                'labels': json.dumps([]),
                'values': json.dumps([])
            },
            
            # Top buyers data
            'top_buyers': []
        }
        
        return render(request, 'tenders/analytics.html', context)
        spend_by_province_chart_data = []
        tender_trends_labels = []
        tender_trends_chart_data = []
    
    context = {
        'total_tenders': total_tenders,
        'status_counts': status_counts,
        'recent_tenders': recent_tenders,
        'upcoming_deadlines': upcoming_deadlines,
        
        # Province distribution data
        'province_data': {
            'labels': json.dumps(spend_by_province_labels),
            'values': json.dumps(spend_by_province_chart_data)
        },
        
        # Top buyers data
        'top_buyers': top_buyers_table,
    }
    
    return render(request, 'tenders/analytics.html', context)

# Analytics API endpoints
@csrf_exempt
def api_spend_by_buyer(request):
    """API endpoint for spend by buyer analytics"""
    try:
        from django.db.models import Count
        
        # Get aggregated data from database using tender count (since budget data is not available)
        buyer_data = Tender.objects.values('buyer_name').annotate(
            tender_count=Count('id')
        ).filter(
            buyer_name__isnull=False
        ).order_by('-tender_count')[:10]
        
        # Format data for response (removed budget/revenue data)
        result = []
        for item in buyer_data:
            result.append({
                'buyer': item['buyer_name'],
                'tender_count': item['tender_count']
            })
        
        return JsonResponse(result, safe=False)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def api_spend_by_province(request):
    """API endpoint for spend by province analytics"""
    try:
        from django.db.models import Count
        
        # Extract province from buyer name and get aggregated data
        province_data = []
        buyers = Tender.objects.values('buyer_name').annotate(
            tender_count=Count('id')
        ).filter(buyer_name__isnull=False)
        
        province_counts = {}
        for item in buyers:
            buyer_name = item['buyer_name']
            # Extract province from buyer name
            if ' - ' in buyer_name:
                province = buyer_name.split(' - ')[0]
            else:
                province = 'Other'
            
            if province in province_counts:
                province_counts[province] += item['tender_count']
            else:
                province_counts[province] = item['tender_count']
        
        # Format data for response
        result = []
        for province, count in sorted(province_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            result.append({
                'province': province,
                'total_spend': 0,  # No budget data available
                'tender_count': count,
                'avg_budget': 0  # No budget data available
            })
        
        return JsonResponse(result, safe=False)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def api_summary_extract(request):
    """API endpoint for document summary extraction"""
    if 'file' not in request.FILES:
        return JsonResponse({'error': 'No file provided'}, status=400)
    
    document = request.FILES['file']
    
    # Check file type
    allowed_types = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/zip']
    if document.content_type not in allowed_types:
        return JsonResponse({'error': 'Unsupported file type'}, status=400)
    
    try:
        # Process the document (extract text)
        text_content = f"Extracted text from {document.name}"
        
        # Generate a summary
        summary = f"Summary of {document.name}: This is a document related to tenders and procurement."
        
        return JsonResponse({
            'text_content': text_content,
            'summary': summary
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def api_tender_trends(request):
    """API endpoint for tender trends analytics"""
    try:
        from django.db.models import Count
        from django.db.models.functions import TruncWeek
        from datetime import datetime, timedelta
        
        # Get weekly tender trends for the last 12 weeks
        twelve_weeks_ago = datetime.now() - timedelta(weeks=12)
        trends_data = Tender.objects.filter(
            tender_period_start_date__isnull=False,
            tender_period_start_date__gte=twelve_weeks_ago
        ).annotate(
            week=TruncWeek('tender_period_start_date')
        ).values('week').annotate(
            count=Count('id')
        ).order_by('week')
        
        # Format data for response
        result = []
        for item in trends_data:
            result.append({
                'period': item['week'].strftime('%Y-%m-%d') if item['week'] else 'Unknown',
                'count': item['count'],
                'avg_budget': 0  # No budget data available
            })
        
        return JsonResponse(result, safe=False)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# Terms and Conditions view
def terms(request):
    return render(request, 'tenders/terms.html')

# Privacy Policy view
def privacy(request):
    return render(request, 'tenders/privacy.html')
