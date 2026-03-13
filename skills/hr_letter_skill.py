"""
HR Letter Generation Skill.

Wraps the existing contract_renewal skill functionality
for use with the Agent SDK.
"""
import os
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


class HrLetterSkill(BaseSkill):
    """
    HR Letter Generation skill.

    Generates HR letters and documents from Google Docs templates:
    - Contract extensions
    - Employment contracts
    - Internship offers
    - Traineeship offers
    - Probation confirmations
    """

    # Available template types
    TEMPLATE_TYPES = [
        "contract_extension",
        "employment_contract",
        "internship_offer",
        "traineeship_offer",
        "probation_confirmation",
    ]

    # Career levels for employment contracts
    CAREER_LEVELS = [
        "associate",
        "senior_associate",
        "assistant_manager",
        "manager",
        "senior_manager",
        "c_suite",
        "freelancer",
    ]

    @property
    def name(self) -> str:
        return "hr_letter"

    @property
    def description(self) -> str:
        return "Generate HR letters and documents from templates"

    def get_required_params(self) -> List[str]:
        return ["employee_name", "template_type"]

    def get_optional_params(self) -> List[str]:
        return [
            "career_level",  # Required for employment_contract
            "contract_type",  # Required for employment_contract
            "new_end_date",  # For contract_extension
            "start_date",  # For new contracts
            "end_date",  # For internship/trainee offers
            "probation_start",  # For probation_confirmation
            "probation_end",  # For probation_confirmation
            "salary",  # For probation_confirmation
            "custom_values",  # Dict of custom placeholder values
        ]

    async def execute(
        self,
        params: Dict[str, Any],
        session: Optional[Any] = None
    ) -> SkillResult:
        """
        Execute the HR letter generation.

        Args:
            params: Must include employee_name and template_type
            session: Optional thread session

        Returns:
            SkillResult with generated document info or error
        """
        # Validate parameters
        validation_error = self.validate_params(params)
        if validation_error:
            return SkillResult(
                success=False,
                message="I couldn't generate the HR letter.",
                error=validation_error
            )

        employee_name = params["employee_name"]
        template_type = params["template_type"]

        # Validate template type
        if template_type not in self.TEMPLATE_TYPES:
            return SkillResult(
                success=False,
                message=f"Unknown template type: {template_type}",
                error=f"Available templates: {', '.join(self.TEMPLATE_TYPES)}"
            )

        # Find employee
        lookup = get_employee_lookup()
        employee = lookup.find_by_name(employee_name)

        if not employee:
            return SkillResult(
                success=False,
                message=f"I couldn't find an employee named '{employee_name}'.",
                error="Employee not found in Active Employees sheet"
            )

        # Import the contract_renewal functions
        try:
            # The build_values_for_template function is in the skills/contract_renewal.py
            # file in the linked hr_automation directory
            import contract_renewal
            build_values_for_template = contract_renewal.build_values_for_template

            from docx_templates import render_letter
            from template_registry import (
                get_template,
                resolve_company_key,
            )
        except ImportError as e:
            return SkillResult(
                success=False,
                message="I couldn't load the letter generation module.",
                error=str(e)
            )

        try:
            # Resolve company if needed
            company_key = None
            if template_type in ("employment_contract", "contract_extension"):
                company_name = employee.get("company", "")
                try:
                    company_key = resolve_company_key(company_name)
                except ValueError as e:
                    return SkillResult(
                        success=False,
                        message=f"Couldn't determine company template for '{company_name}'.",
                        error=str(e)
                    )

            # Get career level for employment contracts
            career_level = params.get("career_level")
            if template_type == "employment_contract" and not career_level:
                return SkillResult(
                    success=False,
                    message="Employment contracts require a career level.",
                    details=f"Available levels: {', '.join(self.CAREER_LEVELS)}",
                    next_action="Please specify the career level."
                )

            # Build values from employee data
            values = build_values_for_template(
                template_type,
                employee,
                career_level=career_level,
                contract_type_info=params.get("contract_type_info"),
            )

            # Apply custom values if provided
            custom_values = params.get("custom_values", {})
            if custom_values:
                values.update(custom_values)

            # Apply template-specific overrides from params
            if template_type == "contract_extension":
                if params.get("new_end_date"):
                    values["{{NEW_END_DATE}}"] = params["new_end_date"]

            # Get template info
            tmpl = get_template(template_type)
            output_filename = (
                f"{tmpl['description']} — "
                f"{employee.get('employee_name', employee.get('name', 'Employee'))} — "
                f"{datetime.now().strftime('%Y-%m-%d')}.docx"
            )

            # Generate the letter
            result = render_letter(
                template_key=template_type,
                values=values,
                career_level=career_level,
                company_key=company_key,
                output_folder_id=Config.CONTRACTS_FOLDER_ID,
                output_filename=output_filename,
                dry_run=False,
            )

            # Success!
            file_url = result.get("file_url", "")

            return SkillResult(
                success=True,
                message=f":white_check_mark: Successfully generated {tmpl['description']} for *{employee.get('employee_name', employee.get('name'))}*!",
                details=lookup.get_employee_summary(employee),
                attachments=[{
                    "title": tmpl['description'],
                    "url": file_url
                }],
                next_action="Review the document and share with the employee."
            )

        except ValueError as e:
            return SkillResult(
                success=False,
                message="There was a validation error generating the letter.",
                error=str(e)
            )
        except RuntimeError as e:
            return SkillResult(
                success=False,
                message="There was an error generating the letter.",
                error=str(e)
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message="Something went wrong while generating the letter.",
                error=f"Unexpected error: {str(e)}"
            )

    def format_help(self) -> str:
        """Format help text for this skill."""
        lines = [
            "*HR Letter Generation*",
            self.description,
            "",
            "*Usage:*",
            "`@hr-bot generate <template_type> for <employee_name>`",
            "",
            "*Available templates:*",
        ]

        for tmpl in self.TEMPLATE_TYPES:
            lines.append(f"• `{tmpl}`")

        lines.extend([
            "",
            "*For employment_contract, you'll also need:*",
            "• `career_level`: " + ", ".join(self.CAREER_LEVELS[:4]) + ", etc.",
            "• `contract_type`: full-time-1yr, permanent, or fixed-term:N",
            "",
            "*Examples:*",
            "• `@hr-bot generate contract_extension for John Doe`",
            "• `@hr-bot generate employment_contract for Jane Smith` (will prompt for details)",
        ])

        return "\n".join(lines)
