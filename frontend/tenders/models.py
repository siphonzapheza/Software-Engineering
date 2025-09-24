from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import uuid

def generate_tender_id():
    return str(uuid.uuid4())

class Team(models.Model):
    PLAN_CHOICES = [
        ('free', 'Free'),
        ('basic', 'Basic'),
        ('pro', 'Pro'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    subscription_tier = models.CharField(max_length=20, choices=PLAN_CHOICES, default='free')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    
    @property
    def max_users(self):
        """Return the maximum number of users allowed for this team's plan."""
        if self.subscription_tier == 'free':
            return 1
        elif self.subscription_tier == 'basic':
            return 3
        elif self.subscription_tier == 'pro':
            return float('inf')  # Unlimited users
        return 1  # Default fallback
    
    @property
    def seats_used(self):
        """Return the number of seats currently used by the team."""
        return self.members.count()
    
    @property
    def has_available_seats(self):
        """Check if the team has available seats."""
        return self.seats_used < self.max_users
    
    def __str__(self):
        return self.name

class CustomUser(AbstractUser):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='members', null=True)
    is_team_admin = models.BooleanField(default=False)
    company_name = models.CharField(max_length=255, blank=True, null=True)
    terms_agreement = models.BooleanField(default=False)
    password_reset_required = models.BooleanField(default=False)
    
    def __str__(self):
        return self.username

class Tender(models.Model):
    ocid = models.CharField(max_length=255, unique=True)
    tender_id = models.CharField(max_length=255, unique=True, default=generate_tender_id)
    title = models.TextField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    buyer_name = models.TextField(null=True, blank=True)
    province = models.TextField(null=True, blank=True)
    budget_min = models.FloatField(null=True, blank=True)
    budget_max = models.FloatField(null=True, blank=True)
    value_currency = models.CharField(max_length=10, null=True, blank=True, default='ZAR')
    tender_period_end_date = models.DateTimeField(null=True, blank=True)
    summary = models.TextField(null=True, blank=True)  # AI-generated summary
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.title or self.ocid

class Certification(models.Model):
    name = models.CharField(max_length=255)
    level = models.CharField(max_length=50, null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    
    def __str__(self):
        return self.name

class CompanyProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.OneToOneField(Team, on_delete=models.CASCADE, related_name='profile')
    industry_sector = models.CharField(max_length=255)
    services_provided = models.JSONField(default=list)  # List of services
    certifications = models.ManyToManyField(Certification, blank=True)
    geographic_coverage = models.JSONField(default=list)  # List of provinces
    years_experience = models.IntegerField(default=0)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=20, null=True, blank=True)
    website = models.URLField(null=True, blank=True)
    bbbee_level = models.IntegerField(null=True, blank=True)
    cidb_grade = models.CharField(max_length=20, null=True, blank=True)
    company_size = models.CharField(max_length=50, null=True, blank=True)
    company_registration_number = models.CharField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.team.name}'s Profile"

class CompanyDocument(models.Model):
    DOCUMENT_TYPE_CHOICES = [
        ('tax_clearance', 'Tax Clearance Certificate'),
        ('company_registration', 'Company Registration'),
        ('bbbee_certificate', 'B-BBEE Certificate'),
        ('cidb_registration', 'CIDB Registration'),
        ('letter_of_good_standing', 'Letter of Good Standing'),
        ('financial_statements', 'Financial Statements'),
        ('other', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='company_documents')
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPE_CHOICES)
    document_file = models.FileField(upload_to='company_documents/')
    description = models.CharField(max_length=255, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey('CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='uploaded_documents')
    
    def __str__(self):
        return f"{self.get_document_type_display()} - {self.team.name}"

class ReadinessScore(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tender = models.ForeignKey(Tender, on_delete=models.CASCADE, related_name='readiness_scores')
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='readiness_scores')
    suitability_score = models.IntegerField()  # 0-100
    checklist = models.JSONField(default=list)  # List of checklist items
    recommendation = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        unique_together = ('tender', 'team')
    
    def __str__(self):
        return f"{self.team.name} - {self.tender.title} - Score: {self.suitability_score}"

class SearchLog(models.Model):
    """Model to track tender searches for enforcing plan limits."""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='search_logs')
    query = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.user.username} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

class WorkspaceItem(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('interested', 'Interested'),
        ('not_eligible', 'Not Eligible'),
        ('submitted', 'Submitted'),
        ('won', 'Won'),
        ('lost', 'Lost'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tender = models.ForeignKey(Tender, on_delete=models.CASCADE, related_name='workspace_items')
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='workspace_items')
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey('CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='workspace_updates')
    
    class Meta:
        unique_together = ('tender', 'team')
    
    def __str__(self):
        return f"{self.team.name} - {self.tender.title} - {self.status}"

class Note(models.Model):
    workspace_item = models.ForeignKey(WorkspaceItem, on_delete=models.CASCADE, related_name='notes')
    content = models.TextField()
    created_by = models.ForeignKey('CustomUser', on_delete=models.CASCADE, related_name='notes')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Note by {self.created_by.username} on {self.workspace_item.tender.title}"

class Task(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ]
    
    workspace_item = models.ForeignKey(WorkspaceItem, on_delete=models.CASCADE, related_name='tasks')
    description = models.TextField()
    assigned_to = models.ForeignKey('CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tasks')
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_by = models.ForeignKey('CustomUser', on_delete=models.CASCADE, related_name='created_tasks')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Task: {self.description[:30]}... for {self.workspace_item.tender.title}"

class DocumentSummary(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tender = models.ForeignKey(Tender, on_delete=models.CASCADE, related_name='document_summaries', null=True, blank=True)
    filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    text_content = models.TextField()  # Full extracted text
    summary = models.TextField()  # AI-generated summary
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey('CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='document_summaries')
    
    def __str__(self):
        return self.filename
