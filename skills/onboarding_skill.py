"""
Onboarding Skill.

Sends onboarding emails to new hires.
"""
import json
import os
import subprocess
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

# Add parent and hr_automation to path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
hr_automation_server = os.path.join(parent_dir, "hr_automation", "server")
hr_automation_skills = os.path.join(parent_dir, "hr_automation", "skills")

for path in [parent_dir, hr_automation_server, hr_automation_skills]:
    if os.path.exists(path) and path not in sys.path:
        sys.path.insert(0, path)

from config.settings import Config
from skills.base_skill import BaseSkill, SkillResult
from utils.employee_lookup import get_employee_lookup


class OnboardingSkill(BaseSkill):
    """
    Onboarding skill.

    Sends onboarding/welcome emails to new hires.
    """

    @property
    def name(self) -> str:
        return "onboarding"

    @property
    def description(self) -> str:
        return "Send onboarding emails to new hires"

    def get_required_params(self) -> List[str]:
        return ["employee_name"]

    def get_optional_params(self) -> List[str]:
        return [
            "template_type",  # internship_offer, traineeship_offer, employment_contract
            "start_date",
            "include_docs",  # Whether to include document links
            "custom_message",
        ]

    def run_gws(self, args: List[str]) -> Dict[str, Any]:
        """Execute gws CLI command."""
        cmd = ["gws"] + args
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            return json.loads(result.stdout) if result.stdout else {}
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"gws command failed: {' '.join(cmd)}\n"
                f"stderr: {e.stderr}"
            ) from e

    async def execute(
        self,
        params: Dict[str, Any],
        session: Optional[Any] = None
    ) -> SkillResult:
        """
        Execute the onboarding email send.

        Args:
            params: Must include employee_name
            session: Optional thread session

        Returns:
            SkillResult with send confirmation or error
        """
        # Validate parameters
        validation_error = self.validate_params(params)
        if validation_error:
            return SkillResult(
                success=False,
                message="I couldn't send the onboarding email.",
                error=validation_error
            )

        employee_name = params["employee_name"]

        # Find employee
        lookup = get_employee_lookup()
        employee = lookup.find_by_name(employee_name)

        if not employee:
            return SkillResult(
                success=False,
                message=f"I couldn't find an employee named '{employee_name}'.",
                error="Employee not found in Active Employees sheet"
            )

        emp_email = employee.get("email", employee.get("work_email", ""))
        if not emp_email:
            return SkillResult(
                success=False,
                message=f"Employee '{employee_name}' has no email address on file.",
                error="Email address required"
            )

        # Build email content
        name = employee.get("employee_name", employee.get("name", ""))
        company = employee.get("company", "our company")
        role = employee.get("job_title", employee.get("designation", "your new role"))
        start_date = params.get("start_date", employee.get("contract_start", "soon"))
        manager = employee.get("manager", "the HR team")

        subject = f"Welcome to {company}! — Onboarding Information"
        body = f"""Dear {name},

Welcome to {company}! We're excited to have you join us as {role}.

Your start date is: {start_date}

Here's what you need to know before your first day:

1. **Please arrive at 9:30 AM** on your start date
2. **Bring the following documents:**
   - NRIC/Passport
   - Bank account details for payroll
   - Previous employment references (if applicable)

3. **Your first day will include:**
   - Orientation with HR
   - Meeting your manager, {manager}
   - Team introduction
   - IT setup and access

If you have any questions before your start date, feel free to reply to this email.

We look forward to working with you!

Best regards,
HR Team
{company}
"""

        # Add custom message if provided
        if params.get("custom_message"):
            body += f"\n\n{params['custom_message']}\n"

        # Add document links if requested
        if params.get("include_docs"):
            body += "\n**Useful Documents:**\n"
            body += "- Employee Handbook: [Link]\n"
            body += "- IT Setup Guide: [Link]\n"

        try:
            # Send email via Gmail API
            # Build MIME message
            import base64
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            msg = MIMEMultipart()
            msg['To'] = emp_email
            msg['From'] = Config.GMAIL_SENDER
            msg['Subject'] = subject

            mime_text = MIMEText(body, 'plain')
            msg.attach(mime_text)

            # Encode as base64url
            raw_bytes = msg.as_bytes()
            encoded = base64.urlsafe_b64encode(raw_bytes).decode('ascii')

            # Send via gws
            result = self.run_gws([
                "gmail", "users", "messages", "send",
                "--params", '{"userId": "me"}',
                "--json", f'{{"raw": "{encoded}"}}'
            ])

            message_id = result.get("id", "")

            if not message_id:
                return SkillResult(
                    success=False,
                    message="The email was sent but I couldn't get confirmation.",
                    details="Please check your Sent folder in Gmail."
                )

            return SkillResult(
                success=True,
                message=f":white_check_mark: Onboarding email sent to *{name}* ({emp_email})!",
                details=f"""*Employee Details:*
• **Name:** {name}
• **Email:** {emp_email}
• **Role:** {role}
• **Start Date:** {start_date}

*Email Contents:*
{body[:200]}...
""",
                next_action=f"Follow up with {name} on their start date ({start_date})."
            )

        except Exception as e:
            return SkillResult(
                success=False,
                message="There was an error sending the onboarding email.",
                error=str(e)
            )

    def format_help(self) -> str:
        """Format help text for this skill."""
        lines = [
            "*Onboarding*",
            self.description,
            "",
            "*Usage:*",
            "`@hr-bot send onboarding for <employee_name>`",
            "`@hr-bot onboarding email for <employee_name>`",
            "",
            "*Optional parameters:*",
            "• `start_date`: Override the employee's start date",
            "• `include_docs`: Include helpful document links",
            "• `custom_message`: Add a custom message to the email",
            "",
            "*Examples:*",
            "• `@hr-bot send onboarding for John Doe`",
            "• `@hr-bot send onboarding for Jane Smith starting March 15`",
            "• `@hr-bot onboarding for Alex Johnson with custom message`",
        ]

        return "\n".join(lines)
