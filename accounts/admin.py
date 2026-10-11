
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Firm, User


@admin.register(Firm)
class FirmAdmin(admin.ModelAdmin):
    list_display  = ['name', 'lsk_number', 'email', 'phone', 'created_at']
    search_fields = ['name', 'lsk_number', 'email']
    ordering      = ['name']


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display   = ['email', 'first_name', 'last_name', 'firm', 'role', 'is_active']
    list_filter    = ['role', 'is_active', 'firm']
    search_fields  = ['email', 'first_name', 'last_name', 'lsk_number']
    ordering       = ['email']
    fieldsets      = (
        (None,           {'fields': ('email', 'password')}),
        ('Personal',     {'fields': ('first_name', 'last_name', 'phone', 'lsk_number')}),
        ('Firm & Role',  {'fields': ('firm', 'role')}),
        ('Permissions',  {'fields': ('is_active', 'is_staff', 'is_superuser')}),
    )
    add_fieldsets  = (
        (None, {'fields': ('email', 'password1', 'password2', 'first_name', 'last_name', 'firm', 'role')}),
    )
# Register your models here.
