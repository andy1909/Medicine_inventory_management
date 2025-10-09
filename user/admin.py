from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Profile

# =======================================================
#        TÍCH HỢP PROFILE VÀO TRANG QUẢN LÝ USER
# =======================================================

# -------------------------------------------------------
#   Inline: PROFILE
#   - Hiển thị thông tin Profile ngay trên trang User
# -------------------------------------------------------
class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'


# -------------------------------------------------------
#   Định nghĩa lại UserAdmin để bao gồm cả Profile
# -------------------------------------------------------
class UserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)


admin.site.unregister(User)
admin.site.register(User, UserAdmin)

