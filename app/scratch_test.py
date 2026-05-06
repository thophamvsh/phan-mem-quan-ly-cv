import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from core.admin import CustomUserChangeForm
form = CustomUserChangeForm()
print("Fields in form:")
for name, field in form.fields.items():
    print(f"{name}: {type(field)}")

print("Password field widget:")
if 'password' in form.fields:
    print(type(form.fields['password'].widget))
    print(form.fields['password'].help_text)
