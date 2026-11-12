from rest_framework import permissions
from accounts.models import User


class IsCitizen(permissions.BasePermission):
    """
    Allows access only to authenticated users with the CITIZEN role.
    """
    message = "Access restricted to registered citizens."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role == User.Role.CITIZEN
        )


class IsCMOAdmin(permissions.BasePermission):
    """
    Allows access only to authenticated CMO Administrators.
    """
    message = "Access restricted to CMO Administrative personnel."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.role == User.Role.CMO_ADMIN or request.user.is_superuser)
        )


class IsOfficer(permissions.BasePermission):
    """
    Allows access only to authenticated Department Officers.
    """
    message = "Access restricted to verified department officers."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role == User.Role.OFFICER and
            request.user.department_id is not None
        )


class IsGrievanceOwner(permissions.BasePermission):
    """
    Object-level permission allowing citizens to view and act only on grievances they own.
    CMO Administrators have administrative override.
    """
    message = "You do not have permission to access or modify this grievance."

    def has_object_permission(self, request, view, obj):
        if not (request.user and request.user.is_authenticated):
            return False

        if request.user.role == User.Role.CMO_ADMIN or request.user.is_superuser:
            return True

        # Handle models directly having 'citizen' attribute or 'grievance.citizen'
        grievance_citizen_id = getattr(obj, 'citizen_id', None)
        if grievance_citizen_id is None and hasattr(obj, 'grievance'):
            grievance_citizen_id = getattr(obj.grievance, 'citizen_id', None)

        return grievance_citizen_id == request.user.id


class IsAssignedOfficer(permissions.BasePermission):
    """
    Object-level permission granting access to an officer only if the grievance
    is assigned to their department or designated directly to them.
    CMO Admins have override.
    """
    message = "Access restricted to the designated department officer."

    def has_object_permission(self, request, view, obj):
        if not (request.user and request.user.is_authenticated):
            return False

        if request.user.role == User.Role.CMO_ADMIN or request.user.is_superuser:
            return True

        if request.user.role != User.Role.OFFICER:
            return False

        target_grievance = obj if hasattr(obj, 'assigned_officer_id') else getattr(obj, 'grievance', None)
        if not target_grievance:
            return False

        # Officer must either be the designated assigned_officer,
        # or belong to the assigned department if unassigned to specific officer
        is_direct = target_grievance.assigned_officer_id == request.user.id
        is_dept = (
            target_grievance.assigned_department_id == request.user.department_id and
            target_grievance.assigned_officer_id is None
        )
        return is_direct or is_dept

