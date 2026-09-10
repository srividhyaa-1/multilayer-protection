from django.contrib import admin
from .models import UserProfile, UploadedFile, KeyRequest

admin.site.register(UserProfile)
admin.site.register(UploadedFile)
admin.site.register(KeyRequest)