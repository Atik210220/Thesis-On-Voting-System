from django import forms
from django.contrib.auth.hashers import make_password
from .models import Voter, Position, Election


class RegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = Voter
        fields = ['name', 'email', 'password', 'voter_image']

    def save(self, commit=True):
        voter = super().save(commit=False)
        voter.password_hash = make_password(self.cleaned_data['password'])
        if commit:
            voter.save()
        return voter


class LoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)


class PositionForm(forms.ModelForm):
    class Meta:
        model = Position
        fields = ['position_name', 'description']
        widgets = {
            'position_name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
