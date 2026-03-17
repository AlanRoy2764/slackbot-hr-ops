"""
Employee lookup utility for Slackbot HR Ops.

Provides access to employee data from Google Sheets.
Reuses functions from the existing contract_renewal skill.
"""
import json
import subprocess
from typing import Any, Dict, List, Optional

from config.settings import Config


class EmployeeLookup:
    """
    Employee data lookup from Google Sheets.

    Wraps the existing employee lookup functionality from
    the contract_renewal skill for use in the bot.
    """

    # Default sheet configuration (can be overridden in .env)
    SHEET_ID = None  # Loaded from config
    SHEET_NAME = None  # Loaded from config

    def __init__(self):
        """Initialize with configuration from environment."""
        self.SHEET_ID = Config.EMPLOYEE_SHEET_ID
        self.SHEET_NAME = Config.EMPLOYEE_SHEET_NAME

    def run_gws(self, args: List[str], dry_run: bool = False) -> Dict[str, Any]:
        """
        Execute gws CLI command and return parsed JSON output.

        Args:
            args: List of command-line arguments to pass to gws
            dry_run: If True, print command instead of executing

        Returns:
            Parsed JSON response as dict

        Raises:
            RuntimeError: If command fails
        """
        cmd = ["gws"] + args

        if dry_run:
            print(f"[DRY-RUN] Would execute: {' '.join(cmd)}")
            return {}

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
                f"stderr: {e.stderr}\n"
                f"stdout: {e.stdout}"
            ) from e
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"gws returned invalid JSON: {' '.join(cmd)}\n"
                f"stdout: {result.stdout}"
            ) from e

    def fetch_all_employees(self, dry_run: bool = False) -> List[Dict[str, Any]]:
        """
        Fetch all employees from the Google Sheet.

        Args:
            dry_run: If True, return mock data

        Returns:
            List of employee dictionaries
        """
        result = self.run_gws([
            "sheets", "spreadsheets", "values", "get",
            "--params", json.dumps({
                "spreadsheetId": self.SHEET_ID,
                "range": f"{self.SHEET_NAME}!A:Z"
            }),
        ], dry_run=dry_run)

        if not result or "values" not in result:
            return []

        raw_headers = result["values"][0]
        # Normalize headers
        headers = [h.strip().lower().replace(" ", "_") for h in raw_headers]

        employees = []
        for row in result["values"][1:]:
            employee = {
                headers[i]: row[i]
                for i in range(min(len(headers), len(row)))
            }
            # Alias common alternate column names
            if "job_title_(designation)" in employee:
                employee["job_title"] = employee["job_title_(designation)"]
            if "manager/supervisor" in employee:
                employee["manager"] = employee["manager/supervisor"]
            # Only include active employees
            if employee.get("employment_status", "").lower() == "active":
                employees.append(employee)

        return employees

    def find_by_name(
        self,
        employee_name: str,
        dry_run: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Find an employee by name.

        Args:
            employee_name: Name to search for
            dry_run: If True, return mock data

        Returns:
            Employee dictionary or None if not found
        """
        employees = self.fetch_all_employees(dry_run=dry_run)

        if dry_run:
            return {
                "employee_name": employee_name,
                "email": "test@example.com",
                "job_title": "Test Role",
                "company": "Mereka Innovative Education Sdn Bhd",
                "contract_end": "15 Dec 2025",
            }

        # Try exact match first
        for emp in employees:
            emp_name = emp.get("employee_name", emp.get("name", ""))
            if emp_name.lower() == employee_name.lower():
                return emp

        # Try partial match
        for emp in employees:
            emp_name = emp.get("employee_name", emp.get("name", ""))
            if (employee_name.lower() in emp_name.lower() or
                    emp_name.lower() in employee_name.lower()):
                return emp

        return None

    def search_by_email(
        self,
        email: str,
        dry_run: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Find an employee by email address.

        Args:
            email: Email address to search for
            dry_run: If True, return mock data

        Returns:
            Employee dictionary or None if not found
        """
        employees = self.fetch_all_employees(dry_run=dry_run)

        for emp in employees:
            emp_email = emp.get("email", emp.get("work_email", ""))
            if emp_email.lower() == email.lower():
                return emp

        return None

    def get_employee_summary(
        self,
        employee: Dict[str, Any]
    ) -> str:
        """
        Get a formatted summary of employee data.

        Args:
            employee: Employee dictionary

        Returns:
            Formatted summary string
        """
        name = employee.get("employee_name", employee.get("name", "N/A"))
        email = employee.get("email", employee.get("work_email", "N/A"))
        company = employee.get("company", "N/A")
        role = employee.get("job_title", employee.get("designation", "N/A"))
        end_date = employee.get("contract_expiry", employee.get("contract_end", "N/A"))

        return f"*Employee Details:*\n• *Name:* {name}\n• *Email:* {email}\n• *Company:* {company}\n• *Role:* {role}\n• *Contract End:* {end_date}"

    def lookup_job_description(self, job_title: str) -> str:
        """
        Search the JD Drive folder for a doc matching job_title.

        Args:
            job_title: Job title to search for

        Returns:
            Plain text content of job description, or empty if not found
        """
        if not Config.JD_FOLDER_ID:
            return ""

        try:
            result = self.run_gws([
                "drive", "files", "list",
                "--params", json.dumps({
                    "q": f"'{Config.JD_FOLDER_ID}' in parents and trashed=false",
                    "fields": "files(id,name)",
                    "supportsAllDrives": True,
                    "includeItemsFromAllDrives": True,
                }),
            ])

            files = result.get("files", [])
            title_lower = job_title.lower()

            # Find matching file
            match = next(
                (f for f in files
                 if title_lower in f["name"].lower() or f["name"].lower() in title_lower),
                None,
            )

            if not match:
                return ""

            # Export the file as plain text
            r = subprocess.run([
                "gws", "drive", "files", "export",
                "--params", json.dumps({
                    "fileId": match["id"],
                    "mimeType": "text/plain"
                }),
            ], capture_output=True, text=True)

            return r.stdout.strip() if r.returncode == 0 else ""

        except Exception:
            return ""


# Singleton instance
_lookup: Optional[EmployeeLookup] = None


def get_employee_lookup() -> EmployeeLookup:
    """Get the singleton EmployeeLookup instance."""
    global _lookup
    if _lookup is None:
        _lookup = EmployeeLookup()
    return _lookup
