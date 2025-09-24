from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

app_name = "tenders"

urlpatterns = [
    # API endpoints
    path('api/search', views.api_search_tenders, name='api_search'),
    path('api/analytics/spend-by-buyer', views.api_spend_by_buyer, name='api_spend_by_buyer'),
    path('api/analytics/spend-by-province', views.api_spend_by_province, name='api_spend_by_province'),
    path('api/analytics/tender-trends', views.api_tender_trends, name='api_tender_trends'),
    path('api/summary/extract', views.api_summary_extract, name='api_summary_extract'),
    
    # Home and search
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('search/', views.search_tenders, name='search'),
    path('results/', views.search_results, name='results'),
    
    # Public access routes
    path('public/search/', views.public_search_tenders, name='public_search'),
    path('public/workspace/', views.public_workspace, name='public_workspace'),
    path('public/tender/<str:tender_id>/', views.public_tender_detail, name='public_tender_detail'),
    path('public/workspace/add/<str:tender_id>/', views.public_add_to_workspace, name='public_add_to_workspace'),
    path('public/workspace/remove/<str:tender_id>/', views.public_remove_from_workspace, name='public_remove_from_workspace'),
    path('public/workspace/status/<str:tender_id>/', views.public_update_workspace_status, name='public_update_workspace_status'),
    
    # Authentication
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    
    # Password Reset
    path('password_reset/', auth_views.PasswordResetView.as_view(template_name='tenders/password_reset.html'), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='tenders/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='tenders/password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='tenders/password_reset_complete.html'), name='password_reset_complete'),
    
    # Tender details
    path('tender/<str:tender_id>/', views.tender_detail, name='tender_detail'),
    
    # Workspace management
    path('workspace/', views.workspace, name='workspace'),
    path('workspace/<str:workspace_item_id>/', views.workspace_detail, name='workspace_detail'),
    path('workspace/add/<str:tender_id>/', views.add_to_workspace, name='add_to_workspace'),
    path('workspace/remove/<str:tender_id>/', views.remove_from_workspace, name='remove_from_workspace'),
    path('workspace/status/<str:tender_id>/', views.update_workspace_status, name='update_workspace_status'),
    
    # Notes and tasks
    path('workspace/note/add/<str:workspace_item_id>/', views.add_note, name='add_note'),
    path('workspace/task/add/<str:workspace_item_id>/', views.add_task, name='add_task'),
    path('workspace/task/status/<int:task_id>/', views.update_task_status, name='update_task_status'),
    
    # Company profile
    path('profile/', views.company_profile, name='company_profile'),
    
    # Readiness check
    path('readiness/<str:tender_id>/', views.check_readiness, name='check_readiness'),
    
    # Document management
    path('document/upload/<str:tender_id>/', views.upload_document, name='upload_document'),
    path('company/document/upload/', views.upload_company_document, name='upload_company_document'),
    path('company/document/delete/<uuid:document_id>/', views.delete_company_document, name='delete_company_document'),
    path('document/summary/<str:tender_id>/<uuid:document_id>/', views.document_summary, name='document_summary'),
    path('document/regenerate/<str:tender_id>/<uuid:document_id>/', views.regenerate_summary, name='regenerate_summary'),
    path('document/download/<str:tender_id>/<uuid:document_id>/', views.download_document, name='download_document'),
    
    # Analytics
    path('analytics/', views.analytics, name='analytics'),
    
    # Terms and Privacy
    path('terms/', views.terms, name='terms'),
    path('privacy/', views.privacy, name='privacy'),
]
