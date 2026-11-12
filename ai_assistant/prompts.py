from typing import List, Optional
from pydantic import BaseModel, Field


class GrievanceAIAnalysisPydantic(BaseModel):
    """
    Pydantic schema passed directly to Google GenAI Client for guaranteed structured JSON response.
    """
    suggested_department: str = Field(
        description="The exact name of the most appropriate Kerala Government Department from the permitted list."
    )
    suggested_category: str = Field(
        description="The standard category under which this grievance falls (e.g. Infrastructure, Healthcare, Revenue, Welfare, Law & Order, Education, Water Supply, Transport)."
    )
    suggested_priority: str = Field(
        description="Assessed priority level. Must strictly be one of: LOW, MEDIUM, HIGH."
    )
    summary: str = Field(
        description="Concise 1-2 sentence objective summary of the citizen's complaint suitable for CMO executive review."
    )
    duplicate_warning: bool = Field(
        default=False,
        description="True if the complaint appears to describe an ongoing or previously reported general incident or repetitive spam, otherwise False."
    )


AI_TRIAGE_SYSTEM_INSTRUCTION = """
You are the Chief Minister's Public Grievance Redressal Assistant for the Government of Kerala.
Your responsibility is to analyze incoming citizen complaints and provide accurate, objective classification, priority assignment, and executive summarization to assist CMO officers.

GUIDELINES:
1. Department Selection: You MUST select the most relevant department exclusively from the 'ALLOWED DEPARTMENTS' provided in the prompt. Do not invent or propose non-existent departments.
2. Priority Assessment:
   - 'HIGH': Imminent safety hazards, public emergencies, severe hospital/medical deficiencies, acute road cave-ins, disaster relief, major law & order breaches.
   - 'MEDIUM': Ongoing public inconveniences, water supply disruptions, local road repairs, pension/revenue delays, municipal waste issues.
   - 'LOW': General inquiries, minor administrative delays, non-urgent suggestions.
3. Summary: Keep the summary strictly factual, concise (under 250 characters), and free of emotional language.
4. Duplicate Warning: Set duplicate_warning to true only if the citizen explicitly notes submitting repeated requests for the exact same unresolved incident without updates, or if obvious spam is detected.
5. Strict JSON Compliance: Output only the required structured JSON adhering strictly to the schema.
"""


def build_analysis_user_prompt(
    subject: str,
    description: str,
    district: str,
    allowed_departments: List[str],
    standard_categories: Optional[List[str]] = None
) -> str:
    """
    Constructs the contextualized user prompt injected with real-time active database departments.
    """
    dept_list_str = "\n".join([f"- {dept}" for dept in allowed_departments]) if allowed_departments else "- General Administration"
    
    cat_section = ""
    if standard_categories:
        cat_section = f"\nSTANDARD CATEGORIES TO CHOOSE FROM:\n" + "\n".join([f"- {cat}" for cat in standard_categories])

    return f"""
Analyze the following citizen grievance submitted to the Government of Kerala:

GRIEVANCE DETAILS:
- District: {district}
- Subject: {subject}
- Description: {description}

ALLOWED DEPARTMENTS (Select ONLY from this list):
{dept_list_str}
{cat_section}

Please extract and return the structured triage recommendation according to the schema.
""".strip()

