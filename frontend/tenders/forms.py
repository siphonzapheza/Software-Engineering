from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import Team, CustomUser

class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    team_name = forms.CharField(max_length=255, required=True)
    company_name = forms.CharField(max_length=255, required=True)
    terms_agreement = forms.BooleanField(required=True)
    
    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'password1', 'password2')
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.company_name = self.cleaned_data['company_name']
        user.terms_agreement = self.cleaned_data['terms_agreement']
        
        if commit:
            # Create a team for the user
            team = Team.objects.create(
                name=self.cleaned_data['team_name'],
                subscription_tier='free'  # Default to free tier
            )
            user.team = team
            user.is_team_admin = True  # First user is the team admin
            user.save()
        
        return user