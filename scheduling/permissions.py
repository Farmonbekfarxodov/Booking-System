from rest_framework.permissions import SAFE_METHODS, BasePermission


def is_owner_or_admin(user, provider) -> bool:
    if not (user and user.is_authenticated):
        return False
    return user.is_business_admin or provider.user_id == user.id


class ProviderScheduleWrite(BasePermission):
    """Ish jadvalini hamma ko'ra oladi; o'zgartirish - admin yoki provider'ning o'zi."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return is_owner_or_admin(request.user, view.provider)


class ProviderOwnerOrAdmin(BasePermission):
    """Faqat admin yoki provider'ning o'zi (o'qish ham). TimeOff sabablari shaxsiy bo'lishi mumkin."""

    def has_permission(self, request, view):
        return is_owner_or_admin(request.user, view.provider)
