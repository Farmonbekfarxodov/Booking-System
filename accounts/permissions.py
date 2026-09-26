from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsBusinessAdmin(BasePermission):
    """Faqat biznes admini (role=admin yoki superuser)."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_business_admin)


class IsStaffOrAdmin(BasePermission):
    """Xodim yoki admin."""

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (u.is_staff_member or u.is_business_admin))


class IsAdminOrReadOnly(BasePermission):
    """O'qish hamma uchun ochiq, o'zgartirish faqat admin uchun."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated and request.user.is_business_admin)
