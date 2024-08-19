from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, Quiz
from django.contrib.auth import get_user_model, authenticate

User = get_user_model()

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name']

class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    role = forms.ChoiceField(choices=CustomUser.ROLE_CHOICES, required=True)
    registration_number = forms.CharField(max_length=255, required=True)

    class Meta:
        model = CustomUser
        fields = ['registration_number', 'first_name', 'last_name', 'username', 'email', 'role', 'password1', 'password2']

class UserLoginForm(forms.Form):
    registration_number = forms.CharField(label='Registration Number', required=True)
    password = forms.CharField(widget=forms.PasswordInput, required=True)

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super(UserLoginForm, self).__init__(*args, **kwargs)
        self.user_cache = None

    def clean(self):
        registration_number = self.cleaned_data.get('registration_number')
        password = self.cleaned_data.get('password')

        if registration_number and password:
            self.user_cache = authenticate(self.request, registration_number=registration_number, password=password)
            if self.user_cache is None:
                raise forms.ValidationError('Invalid registration number or password.')
        else:
            raise forms.ValidationError('Both fields are required.')
        return self.cleaned_data

    def get_user(self):
        return self.user_cache

class ChangePasswordForm(forms.Form):
    old_password = forms.CharField(widget=forms.PasswordInput, required=True, label='Current Password')
    new_password1 = forms.CharField(widget=forms.PasswordInput, required=True, label='New Password')
    new_password2 = forms.CharField(widget=forms.PasswordInput, required=True, label='Confirm New Password')

    def clean(self):
        cleaned_data = super().clean()
        new_password1 = cleaned_data.get("new_password1")
        new_password2 = cleaned_data.get("new_password2")

        if new_password1 and new_password2 and new_password1 != new_password2:
            raise forms.ValidationError("The new passwords do not match")

        return cleaned_data

class QuizDeleteForm(forms.Form):
    quiz_id = forms.UUIDField()

    def delete_quiz(self, user):
        quiz_uuid = self.cleaned_data['quiz_id']
        quiz = Quiz.objects.get(uuid=quiz_uuid, created_by=user)
        quiz.delete()
