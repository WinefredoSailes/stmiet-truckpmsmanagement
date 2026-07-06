from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import User
from core.forms import BootstrapFormMixin


class CustomUserCreationForm(BootstrapFormMixin, UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ['username', 'email', 'first_name', 'last_name',
                  'role', 'mobile', 'specialization', 'employee_id']


class CustomUserChangeForm(BootstrapFormMixin, UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = ['username', 'email', 'first_name', 'last_name',
                  'role', 'mobile', 'specialization', 'employee_id', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'password' in self.fields:
            del self.fields['password']
