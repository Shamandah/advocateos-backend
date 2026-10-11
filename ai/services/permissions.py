from django.core.exceptions import PermissionDenied


def ensure_firm_access(user, firm):
    """
    Ensure the authenticated user belongs to the requested firm.
    """
    if not user.is_authenticated:
        raise PermissionDenied("Authentication required.")

    if user.firm_id != firm.id:
        raise PermissionDenied("You do not have access to this firm.")


def ensure_matter_access(user, matter):
    """
    Ensure the matter belongs to the authenticated user's firm.
    """
    if not user.is_authenticated:
        raise PermissionDenied("Authentication required.")

    if matter.firm_id != user.firm_id:
        raise PermissionDenied(
            "You do not have access to this matter."
        )