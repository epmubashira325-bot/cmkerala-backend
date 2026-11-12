from rest_framework import status
from rest_framework.test import APITestCase
from django.urls import reverse
from accounts.models import User
from departments.models import Department


class CMODepartmentOfficersAPITests(APITestCase):
    """
    Automated security and functional verification for:
    GET /api/v1/cmo/departments/{id}/officers/
    """

    def setUp(self):
        # Create test departments
        self.pwd = Department.objects.create(
            name="Public Works Department",
            code="PWD_TEST",
            description="Roads and bridges",
            is_active=True
        )
        self.health = Department.objects.create(
            name="Health and Family Welfare",
            code="HFW_TEST",
            description="Public healthcare",
            is_active=True
        )

        # Create CMO Admin
        self.cmo_user = User.objects.create_user(
            email="cmo.test.officers@example.com",
            password="StrongPassword123!",
            full_name="CMO Officer Inspector",
            role=User.Role.CMO_ADMIN
        )

        # Create Citizen
        self.citizen_user = User.objects.create_citizen(
            email="citizen.test.officers@example.com",
            password="StrongPassword123!",
            full_name="Citizen Tester"
        )

        # Create PWD Officers (2 active, 1 inactive)
        self.pwd_officer1 = User.objects.create_user(
            email="pwd.officer1@example.com",
            password="StrongPassword123!",
            full_name="PWD Officer Alpha",
            role=User.Role.OFFICER,
            department=self.pwd
        )
        self.pwd_officer2 = User.objects.create_user(
            email="pwd.officer2@example.com",
            password="StrongPassword123!",
            full_name="PWD Officer Beta",
            role=User.Role.OFFICER,
            department=self.pwd
        )
        self.pwd_officer_inactive = User.objects.create_user(
            email="pwd.officer.inactive@example.com",
            password="StrongPassword123!",
            full_name="PWD Officer Inactive",
            role=User.Role.OFFICER,
            department=self.pwd,
            is_active=False
        )

        # Create Health Officer
        self.health_officer = User.objects.create_user(
            email="health.officer@example.com",
            password="StrongPassword123!",
            full_name="Health Officer Gamma",
            role=User.Role.OFFICER,
            department=self.health
        )

        self.url = reverse('cmo-department-officers-list', kwargs={'pk': str(self.pwd.id)})

    def test_cmo_can_access_department_officers(self):
        """CMO administrator is authorized to list officers belonging to a department."""
        self.client.force_authenticate(user=self.cmo_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 2)  # Only 2 active PWD officers

        officer_emails = [o['email'] for o in data]
        self.assertIn("pwd.officer1@example.com", officer_emails)
        self.assertIn("pwd.officer2@example.com", officer_emails)
        self.assertNotIn("pwd.officer.inactive@example.com", officer_emails)
        self.assertNotIn("health.officer@example.com", officer_emails)

    def test_citizen_cannot_access_department_officers(self):
        """Citizens are strictly forbidden (HTTP 403)."""
        self.client.force_authenticate(user=self.citizen_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_officer_cannot_access_department_officers(self):
        """Department officers are strictly forbidden (HTTP 403)."""
        self.client.force_authenticate(user=self.pwd_officer1)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_access(self):
        """Anonymous requests return HTTP 401."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
