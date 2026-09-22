from django import forms
from django.contrib.auth import authenticate, password_validation
from django.core.exceptions import ValidationError

from .models import User



class RegistrationForm(forms.ModelForm):
    password1 = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Confirm password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    class Meta:
        model = User
        fields = ("full_name", "email")
        widgets = {
            "full_name": forms.TextInput(attrs={"autocomplete": "name"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
        }

    def clean_email(self):
        email = self.cleaned_data.get("email", "").lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email already exists.")
        return email

    def clean_password2(self):
        pw1 = self.cleaned_data.get("password1")
        pw2 = self.cleaned_data.get("password2")
        if pw1 and pw2 and pw1 != pw2:
            raise ValidationError("Passwords do not match.")
        return pw2

    def _post_clean(self):
        super()._post_clean()
        password = self.cleaned_data.get("password1")
        if password:
            try:
                password_validation.validate_password(password, self.instance)
            except ValidationError as error:
                self.add_error("password1", error)

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        user.role = User.Role.SHOP_OWNER
        user.status = User.Status.PENDING
        if commit:
            user.save()
        return user


class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )
    password = forms.CharField(
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def __init__(self, *args, **kwargs):
        self.user = None
        super().__init__(*args, **kwargs)

    def clean(self):
        email = self.cleaned_data.get("email", "").lower()
        password = self.cleaned_data.get("password")

        if email and password:
            self.user = authenticate(email=email, password=password)
            if self.user is None:
                raise ValidationError("Invalid email or password.")

        return self.cleaned_data


class AdminCreateUserForm(forms.Form):
    """
    Admin-only form for direct user creation (SCRUM-41).

    Creates an account with an unusable password; the user must follow the
    one-time set-password link to choose their own password before logging in.

    Validation rules:
    - full_name: required, not whitespace-only, max 150 chars.
    - email: required, stripped, fully lower-cased, valid format, unique
      (case-insensitive check mirrors RegistrationForm.clean_email).
    - role: must be exactly ADMIN or SHOP_OWNER — server-side re-validation
      regardless of what the client POSTed.
    """

    full_name = forms.CharField(
        label="Full name",
        max_length=User._meta.get_field("full_name").max_length,
        strip=True,
        widget=forms.TextInput(attrs={"autocomplete": "name"}),
    )
    email = forms.EmailField(
        label="Email address",
        max_length=User._meta.get_field("email").max_length,
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )
    role = forms.ChoiceField(
        label="Role",
        choices=User.Role.choices,
    )

    def clean_full_name(self):
        name = self.cleaned_data.get("full_name", "")
        if not name.strip():
            raise ValidationError("Full name is required.")
        return name

    def clean_email(self):
        # Strip whitespace and fully lower-case (normalize_email only
        # lowercases the domain; the local-part must be lowercased here).
        email = self.cleaned_data.get("email", "").strip().lower()
        if not email:
            raise ValidationError("Email address is required.")
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("A user with this email already exists.")
        return email

    def clean_role(self):
        role = self.cleaned_data.get("role", "")
        allowed = {User.Role.ADMIN, User.Role.SHOP_OWNER}
        if role not in allowed:
            raise ValidationError(
                "Select a valid role. Allowed values: ADMIN, SHOP_OWNER."
            )
        return role
