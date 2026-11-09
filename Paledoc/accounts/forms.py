from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password


class RegistrationForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Choose a username',
            'autofocus': True,
        }),
        help_text='Required. 150 characters or fewer. Letters, digits, and @/./+/-/_ only.',
    )

    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email address (optional)',
        }),
    )

    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password',
        }),
    )

    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm password',
        }),
    )

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("A user with that username already exists.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')

        if password1 and password2:
            if password1 != password2:
                raise forms.ValidationError("The two password fields didn't match.")
            try:
                validate_password(password1)
            except forms.ValidationError as e:
                self.add_error('password1', e)

        return cleaned_data

    def save(self):
        username = self.cleaned_data['username']
        email = self.cleaned_data.get('email', '')
        password = self.cleaned_data['password1']
        user = User.objects.create_user(username=username, email=email, password=password)
        return user
