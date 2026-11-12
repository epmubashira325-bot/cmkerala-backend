from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied

from .models import (
    Grievance,
    GrievanceHistory,
    DepartmentAssignment,
    ActionTakenReport,
)
from accounts.models import User
from departments.models import Department


class GrievanceWorkflowService:
    """
    Central business logic orchestrator for Grievance status transitions,
    department assignments, and report reviews.
    Enforces that model state transitions cannot be bypassed.
    """

    ALLOWED_TRANSITIONS = {
        Grievance.Status.SUBMITTED: [Grievance.Status.UNDER_REVIEW],
        Grievance.Status.UNDER_REVIEW: [Grievance.Status.IN_PROGRESS],
        Grievance.Status.IN_PROGRESS: [Grievance.Status.RESOLVED],
        Grievance.Status.RESOLVED: [Grievance.Status.REOPENED],
        Grievance.Status.REOPENED: [Grievance.Status.IN_PROGRESS],
    }

    @classmethod
    @transaction.atomic
    def change_status(cls, grievance: Grievance, new_status: str, actor: User, remarks: str = "") -> Grievance:
        """
        Validates transition, actor permissions, and logs history atomically.
        """
        current_status = grievance.status

        if new_status == current_status:
            return grievance

        allowed_next = cls.ALLOWED_TRANSITIONS.get(current_status, [])
        if new_status not in allowed_next:
            raise ValidationError(
                f"Invalid status transition from '{current_status}' to '{new_status}'. "
                f"Permitted next statuses: {allowed_next}"
            )

        # Enforce actor authorization for transitions
        if new_status == Grievance.Status.UNDER_REVIEW:
            if not (actor.role == User.Role.CMO_ADMIN or actor.is_superuser):
                raise PermissionDenied("Only CMO Administrators can mark grievances as UNDER_REVIEW.")

        elif new_status == Grievance.Status.IN_PROGRESS:
            # Can be triggered when CMO assigns an officer or when officer accepts/remarks
            is_cmo = actor.role == User.Role.CMO_ADMIN or actor.is_superuser
            is_assigned = (
                actor.role == User.Role.OFFICER and
                (grievance.assigned_officer_id == actor.id or grievance.assigned_department_id == actor.department_id)
            )
            if not (is_cmo or is_assigned):
                raise PermissionDenied("Only assigned officers or CMO Administrators can transition grievance to IN_PROGRESS.")

        elif new_status == Grievance.Status.RESOLVED:
            # Crucial requirement: A report must be approved by CMO before grievance can be marked RESOLVED.
            has_approved_report = ActionTakenReport.objects.filter(
                grievance=grievance,
                review_status=ActionTakenReport.ReviewStatus.APPROVED
            ).exists()
            if not has_approved_report:
                raise ValidationError(
                    "Cannot resolve grievance without an approved Action Taken Report (ATR) from CMO."
                )
            if not (actor.role == User.Role.CMO_ADMIN or actor.is_superuser):
                raise PermissionDenied("Only CMO Administrators can mark a grievance as RESOLVED.")

        elif new_status == Grievance.Status.REOPENED:
            # Only citizen owner or CMO admin can reopen a resolved grievance
            is_owner = actor.id == grievance.citizen_id
            is_cmo = actor.role == User.Role.CMO_ADMIN or actor.is_superuser
            if not (is_owner or is_cmo):
                raise PermissionDenied("Only the citizen who filed the grievance or CMO Admins can reopen it.")

        # Update grievance status
        previous_status = grievance.status
        grievance.status = new_status
        grievance.save(update_fields=['status', 'updated_at'])

        # Record immutable audit history
        GrievanceHistory.objects.create(
            grievance=grievance,
            previous_status=previous_status,
            new_status=new_status,
            changed_by=actor,
            remarks=remarks.strip() if remarks else f"Status transitioned to {new_status}"
        )

        return grievance

    @classmethod
    @transaction.atomic
    def assign_department_and_officer(
        cls,
        grievance: Grievance,
        department: Department,
        officer: User | None,
        assigned_by: User,
        due_date=None,
        remarks: str = ""
    ) -> DepartmentAssignment:
        """
        Validates department, validates officer relationship, retires previous active assignments,
        creates historical assignment log, updates current grievance pointers, and updates status if needed.
        """
        if not (assigned_by.role == User.Role.CMO_ADMIN or assigned_by.is_superuser):
            raise PermissionDenied("Only CMO Administrators can assign departments or officers.")

        if not department.is_active:
            raise ValidationError("Cannot assign to an inactive department.")

        if officer is not None:
            if officer.role != User.Role.OFFICER:
                raise ValidationError("Assigned user must have the OFFICER role.")
            if officer.department_id != department.id:
                raise ValidationError(
                    f"Selected officer '{officer.full_name}' does not belong to department '{department.name}'."
                )

        now = timezone.now()

        # Mark all prior active assignments for this grievance as ended
        DepartmentAssignment.objects.filter(
            grievance=grievance,
            is_active=True
        ).update(
            is_active=False,
            ended_at=now
        )

        # Create new historical record
        assignment = DepartmentAssignment.objects.create(
            grievance=grievance,
            department=department,
            officer=officer,
            assigned_by=assigned_by,
            due_date=due_date or grievance.due_date,
            is_active=True
        )

        # Update grievance current assignment references
        grievance.assigned_department = department
        grievance.assigned_officer = officer
        if due_date:
            grievance.due_date = due_date

        update_fields = ['assigned_department', 'assigned_officer', 'updated_at']
        if due_date:
            update_fields.append('due_date')
        grievance.save(update_fields=update_fields)

        # Auto transition status if appropriate: SUBMITTED -> UNDER_REVIEW -> IN_PROGRESS
        target_status = Grievance.Status.IN_PROGRESS if officer else Grievance.Status.UNDER_REVIEW
        if grievance.status == Grievance.Status.SUBMITTED:
            cls.change_status(
                grievance,
                Grievance.Status.UNDER_REVIEW,
                assigned_by,
                remarks=f"Triage commenced. Assigned to {department.code}."
            )
            if officer:
                cls.change_status(
                    grievance,
                    Grievance.Status.IN_PROGRESS,
                    assigned_by,
                    remarks=f"Assigned to Officer {officer.full_name}."
                )
        elif grievance.status == Grievance.Status.UNDER_REVIEW and officer:
            cls.change_status(
                grievance,
                Grievance.Status.IN_PROGRESS,
                assigned_by,
                remarks=f"Assigned to Officer {officer.full_name}."
            )
        elif remarks:
            # If no status transition took place, log history entry for reassignment
            GrievanceHistory.objects.create(
                grievance=grievance,
                previous_status=grievance.status,
                new_status=grievance.status,
                changed_by=assigned_by,
                remarks=f"Reassigned to {department.code}" + (f" ({officer.full_name}): " if officer else ": ") + remarks
            )

        return assignment

    @classmethod
    @transaction.atomic
    def review_action_taken_report(
        cls,
        report: ActionTakenReport,
        cmo_admin: User,
        decision: str,
        remarks: str = ""
    ) -> ActionTakenReport:
        """
        Reviews ATR filed by officer. Officers cannot review their own reports.
        If APPROVED, allows CMO to mark grievance as RESOLVED.
        """
        if not (cmo_admin.role == User.Role.CMO_ADMIN or cmo_admin.is_superuser):
            raise PermissionDenied("Only CMO Administrators can review Action Taken Reports.")

        if report.officer_id == cmo_admin.id:
            raise ValidationError("An officer cannot review or approve their own Action Taken Report.")

        if decision not in (ActionTakenReport.ReviewStatus.APPROVED, ActionTakenReport.ReviewStatus.REJECTED):
            raise ValidationError("Decision must be either 'APPROVED' or 'REJECTED'.")

        report.review_status = decision
        report.reviewed_by = cmo_admin
        report.review_remarks = remarks
        report.reviewed_at = timezone.now()
        report.save(update_fields=['review_status', 'reviewed_by', 'review_remarks', 'reviewed_at'])

        grievance = report.grievance

        # Audit history log
        GrievanceHistory.objects.create(
            grievance=grievance,
            previous_status=grievance.status,
            new_status=Grievance.Status.RESOLVED if decision == ActionTakenReport.ReviewStatus.APPROVED else grievance.status,
            changed_by=cmo_admin,
            remarks=f"ATR {decision}: {remarks}".strip()
        )

        if decision == ActionTakenReport.ReviewStatus.APPROVED:
            # Mark grievance as RESOLVED
            grievance.status = Grievance.Status.RESOLVED
            grievance.save(update_fields=['status', 'updated_at'])

        return report

