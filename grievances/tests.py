from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status
from django.core.files.uploadedfile import SimpleUploadedFile
from accounts.models import User
from departments.models import Department
from grievances.models import (
    Grievance,
    GrievanceHistory,
    DepartmentAssignment,
    ActionTakenReport,
    CitizenFeedback,
)
from contact.models import ContactEnquiry


class CMKeralaAPITestCase(APITestCase):
    def setUp(self):
        # 1. Departments
        self.dept_rev = Department.objects.create(name="Revenue Department", code="REV")
        self.dept_hlt = Department.objects.create(name="Health Department", code="HLT")

        # 2. Users
        self.citizen1 = User.objects.create_citizen(
            email="citizen1@example.com",
            password="Password@123",
            full_name="Citizen One",
            mobile_number="+919447000001"
        )
        self.citizen2 = User.objects.create_citizen(
            email="citizen2@example.com",
            password="Password@123",
            full_name="Citizen Two",
            mobile_number="+919447000002"
        )
        self.cmo_admin = User.objects.create_superuser(
            email="cmo@kerala.gov.in",
            password="Password@123",
            full_name="CMO Secretary"
        )
        self.officer_rev = User.objects.create_user(
            email="officer.rev@kerala.gov.in",
            password="Password@123",
            full_name="Revenue Officer",
            role=User.Role.OFFICER,
            department=self.dept_rev
        )
        self.officer_hlt = User.objects.create_user(
            email="officer.hlt@kerala.gov.in",
            password="Password@123",
            full_name="Health Officer",
            role=User.Role.OFFICER,
            department=self.dept_hlt
        )

    # -------------------------------------------------------------------------
    # 1. CITIZEN REGISTRATION & ROLE ENFORCEMENT
    # -------------------------------------------------------------------------
    def test_citizen_registration_success_and_role_forcing(self):
        payload = {
            "email": "newcitizen@example.com",
            "password": "StrongPassword@123",
            "password_confirm": "StrongPassword@123",
            "full_name": "New Registered Citizen",
            "mobile_number": "+919876543210",
            "role": "CMO_ADMIN"  # Malicious attempt to elevate role
        }
        response = self.client.post('/api/v1/auth/register/', payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('tokens', response.data)
        user = User.objects.get(email="newcitizen@example.com")
        self.assertEqual(user.role, User.Role.CITIZEN)
        self.assertIsNone(user.department)

    def test_citizen_registration_duplicate_email(self):
        payload = {
            "email": "citizen1@example.com",
            "password": "StrongPassword@123",
            "password_confirm": "StrongPassword@123",
            "full_name": "Duplicate Citizen",
        }
        response = self.client.post('/api/v1/auth/register/', payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already exists", str(response.data))

    # -------------------------------------------------------------------------
    # 2. LOGIN WITH EMAIL & CREDENTIAL VALIDATION
    # -------------------------------------------------------------------------
    def test_login_success_and_profile_retrieval(self):
        response = self.client.post('/api/v1/auth/login/', {
            "email": "citizen1@example.com",
            "password": "Password@123"
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        access_token = response.data['access']

        # Profile retrieval
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        profile_res = self.client.get('/api/v1/auth/me/')
        self.assertEqual(profile_res.status_code, status.HTTP_200_OK)
        self.assertEqual(profile_res.data['email'], "citizen1@example.com")
        self.assertEqual(profile_res.data['role'], "CITIZEN")

    def test_login_invalid_credentials(self):
        response = self.client.post('/api/v1/auth/login/', {
            "email": "citizen1@example.com",
            "password": "WrongPassword@123"
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_and_token_blacklist(self):
        login_res = self.client.post('/api/v1/auth/login/', {
            "email": "citizen1@example.com",
            "password": "Password@123"
        })
        refresh_token = login_res.data['refresh']
        access_token = login_res.data['access']

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        logout_res = self.client.post('/api/v1/auth/logout/', {"refresh": refresh_token})
        self.assertEqual(logout_res.status_code, status.HTTP_200_OK)

        # Refresh token must now be invalid
        refresh_attempt = self.client.post('/api/v1/auth/token/refresh/', {"refresh": refresh_token})
        self.assertEqual(refresh_attempt.status_code, status.HTTP_401_UNAUTHORIZED)

    # -------------------------------------------------------------------------
    # 3. CITIZEN GRIEVANCE SUBMISSION, ISOLATION & TRACKING
    # -------------------------------------------------------------------------
    def test_citizen_grievance_submission_and_reference_generation(self):
        self.client.force_authenticate(user=self.citizen1)
        file_content = b"Simulated grievance photo or document evidence"
        test_file = SimpleUploadedFile("evidence.pdf", file_content, content_type="application/pdf")

        payload = {
            "district": "THIRUVANANTHAPURAM",
            "category": "Public Works",
            "subject": "Road cave-in near Secretariat gate",
            "description": "Deep road cave-in causing traffic hazards and risk of accidents.",
            "priority": "HIGH",
            "attachments": [test_file]
        }
        response = self.client.post('/api/v1/citizen/grievances/', payload, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['reference_number'].startswith("CMK-"))
        self.assertEqual(response.data['status'], "SUBMITTED")
        self.assertEqual(len(response.data['attachments']), 1)

        # Check history was automatically created
        ref = response.data['reference_number']
        g = Grievance.objects.get(reference_number=ref)
        self.assertEqual(g.history_logs.count(), 1)
        self.assertEqual(g.history_logs.first().new_status, "SUBMITTED")

        # Public tracking without auth
        self.client.force_authenticate(user=None)
        track_res = self.client.get(f'/api/v1/grievances/track/?ref={ref}')
        self.assertEqual(track_res.status_code, status.HTTP_200_OK)
        self.assertEqual(track_res.data['reference_number'], ref)
        self.assertNotIn('citizen', track_res.data)
        self.assertNotIn('description', track_res.data)

    def test_citizen_data_isolation(self):
        # Create grievance for citizen1
        g1 = Grievance.objects.create(
            citizen=self.citizen1,
            district=Grievance.District.ERNAKULAM,
            category="Revenue",
            subject="Land Mutation Delay for Citizen 1",
            description="Awaiting patta mutation since two months."
        )
        # Authenticate as citizen2
        self.client.force_authenticate(user=self.citizen2)
        list_res = self.client.get('/api/v1/citizen/grievances/')
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_res.data['results']), 0)

        # Direct access to citizen1's grievance should 404
        detail_res = self.client.get(f'/api/v1/citizen/grievances/{g1.id}/')
        self.assertEqual(detail_res.status_code, status.HTTP_404_NOT_FOUND)

    # -------------------------------------------------------------------------
    # 4. CMO DEPARTMENT ASSIGNMENT & OFFICER VALIDATION
    # -------------------------------------------------------------------------
    def test_cmo_department_assignment_and_officer_mismatch(self):
        g = Grievance.objects.create(
            citizen=self.citizen1,
            district=Grievance.District.KOLLAM,
            category="Revenue",
            subject="Revenue inspection delay",
            description="Tehsildar office has not inspected site."
        )

        self.client.force_authenticate(user=self.cmo_admin)

        # Mismatch: Assigning Revenue department with Health officer
        bad_payload = {
            "department_id": str(self.dept_rev.id),
            "officer_id": str(self.officer_hlt.id),
            "remarks": "Assigned"
        }
        res_bad = self.client.post(f'/api/v1/cmo/grievances/{g.id}/assign/', bad_payload)
        self.assertEqual(res_bad.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("does not belong to", str(res_bad.data))

        # Valid: Assign Revenue department with Revenue officer
        valid_payload = {
            "department_id": str(self.dept_rev.id),
            "officer_id": str(self.officer_rev.id),
            "remarks": "Assigned to Revenue officer for immediate enquiry."
        }
        res_valid = self.client.post(f'/api/v1/cmo/grievances/{g.id}/assign/', valid_payload)
        self.assertEqual(res_valid.status_code, status.HTTP_200_OK)

        g.refresh_from_db()
        self.assertEqual(g.assigned_department, self.dept_rev)
        self.assertEqual(g.assigned_officer, self.officer_rev)
        self.assertEqual(g.status, Grievance.Status.IN_PROGRESS)

        # Verify historical assignment record
        assignment = DepartmentAssignment.objects.get(grievance=g, is_active=True)
        self.assertEqual(assignment.department, self.dept_rev)
        self.assertEqual(assignment.officer, self.officer_rev)

    # -------------------------------------------------------------------------
    # 5. OFFICER ISOLATION & REMARKS
    # -------------------------------------------------------------------------
    def test_officer_access_and_isolation(self):
        g_rev = Grievance.objects.create(
            citizen=self.citizen1,
            district=Grievance.District.KASARAGOD,
            category="Revenue",
            subject="Revenue matter",
            description="Land records issue",
            assigned_department=self.dept_rev,
            assigned_officer=self.officer_rev
        )

        # Health officer cannot access or modify Revenue grievance
        self.client.force_authenticate(user=self.officer_hlt)
        detail_res = self.client.get(f'/api/v1/officer/grievances/{g_rev.id}/')
        self.assertEqual(detail_res.status_code, status.HTTP_404_NOT_FOUND)

        remark_res = self.client.post(f'/api/v1/officer/grievances/{g_rev.id}/remarks/', {"remarks": "Unauthorized remark"})
        self.assertEqual(remark_res.status_code, status.HTTP_403_FORBIDDEN)

        # Revenue officer can access and add remarks
        self.client.force_authenticate(user=self.officer_rev)
        detail_ok = self.client.get(f'/api/v1/officer/grievances/{g_rev.id}/')
        self.assertEqual(detail_ok.status_code, status.HTTP_200_OK)

        remark_ok = self.client.post(f'/api/v1/officer/grievances/{g_rev.id}/remarks/', {"remarks": "Site inspection conducted today."})
        self.assertEqual(remark_ok.status_code, status.HTTP_200_OK)

    # -------------------------------------------------------------------------
    # 6. ACTION TAKEN REPORT, SELF-APPROVAL BAN & RESOLUTION GATE
    # -------------------------------------------------------------------------
    def test_atr_submission_and_cmo_approval_workflow(self):
        g = Grievance.objects.create(
            citizen=self.citizen1,
            district=Grievance.District.MALAPPURAM,
            category="Revenue",
            subject="Encroachment investigation",
            description="Complaint regarding public path encroachment.",
            status=Grievance.Status.IN_PROGRESS,
            assigned_department=self.dept_rev,
            assigned_officer=self.officer_rev
        )

        # Officer submits ATR
        self.client.force_authenticate(user=self.officer_rev)
        atr_payload = {
            "investigation_description": "Conducted joint survey with Taluk Surveyor.",
            "resolution_details": "Encroachment removed and path restored to public use."
        }
        atr_res = self.client.post(f'/api/v1/officer/grievances/{g.id}/reports/', atr_payload)
        self.assertEqual(atr_res.status_code, status.HTTP_201_CREATED)
        report_id = atr_res.data['report']['id']

        # Officer attempts to review their own report (forbidden)
        self.client.force_authenticate(user=self.officer_rev)
        review_self = self.client.post(f'/api/v1/cmo/reports/{report_id}/review/', {"decision": "APPROVED"})
        self.assertEqual(review_self.status_code, status.HTTP_403_FORBIDDEN)

        # CMO reviews and approves report
        self.client.force_authenticate(user=self.cmo_admin)
        review_ok = self.client.post(f'/api/v1/cmo/reports/{report_id}/review/', {
            "decision": "APPROVED",
            "remarks": "Action verified and approved."
        })
        self.assertEqual(review_ok.status_code, status.HTTP_200_OK)

        g.refresh_from_db()
        self.assertEqual(g.status, Grievance.Status.RESOLVED)

        # Citizen submits feedback on resolved grievance
        self.client.force_authenticate(user=self.citizen1)
        fb_res = self.client.post(f'/api/v1/citizen/grievances/{g.id}/feedback/', {
            "rating": 5,
            "comments": "Prompt action taken. Thank you!"
        })
        self.assertEqual(fb_res.status_code, status.HTTP_201_CREATED)

    # -------------------------------------------------------------------------
    # 7. FEEDBACK REJECTION ON UNRESOLVED GRIEVANCES
    # -------------------------------------------------------------------------
    def test_feedback_rejected_on_unresolved_grievance(self):
        g_unresolved = Grievance.objects.create(
            citizen=self.citizen1,
            district=Grievance.District.ALAPPUZHA,
            category="Health",
            subject="Hospital medicine shortage",
            description="Certain basic medications are unavailable in PHC.",
            status=Grievance.Status.IN_PROGRESS
        )
        self.client.force_authenticate(user=self.citizen1)
        fb_res = self.client.post(f'/api/v1/citizen/grievances/{g_unresolved.id}/feedback/', {
            "rating": 4,
            "comments": "Good"
        })
        self.assertEqual(fb_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("RESOLVED grievances", str(fb_res.data))

    # -------------------------------------------------------------------------
    # 8. CONTACT ENQUIRY & CMO DASHBOARD STATS
    # -------------------------------------------------------------------------
    def test_public_contact_enquiry(self):
        payload = {
            "name": "General Citizen",
            "email": "contact.citizen@example.com",
            "subject": "Portal enquiry regarding Aadhaar linking",
            "message": "Is Aadhaar verification mandatory for filing grievances?"
        }
        res = self.client.post('/api/v1/public/contact/', payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(ContactEnquiry.objects.filter(email="contact.citizen@example.com").exists())

    def test_cmo_dashboard_stats(self):
        self.client.force_authenticate(user=self.cmo_admin)
        res = self.client.get('/api/v1/cmo/stats/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('overview', res.data)
        self.assertIn('total_grievances', res.data['overview'])
        self.assertIn('district_distribution', res.data)
        self.assertIn('department_distribution', res.data)
