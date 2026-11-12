import os
import sys

backend_dir = os.path.abspath('backend')
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from ai_assistant.services import GeminiAssistantService
from departments.models import Department

print("--- LIVE GEMINI API INTEGRATION TEST ---")
print(f"Configured Model: {GeminiAssistantService.get_configured_model()}")

# Verify sample grievance analysis
test_complaint = {
    "subject": "Dangerous deep pothole near Government High School",
    "description": "A very large pothole has formed right in front of the school gate on Main Road. Two two-wheelers skidded this morning.",
    "district": "PALAKKAD"
}

try:
    print(f"Sending test complaint to Gemini ({GeminiAssistantService.get_configured_model()})...")
    result = GeminiAssistantService.analyze_grievance(
        subject=test_complaint["subject"],
        description=test_complaint["description"],
        district=test_complaint["district"]
    )
    print("\n[SUCCESS] Gemini Structured Response Received:")
    print("Suggestions:", result["suggestions"])
    print("Metadata:", result["metadata"])
except Exception as e:
    print(f"\n[FAILED] Live call failed with error: {e}")
    sys.exit(1)

