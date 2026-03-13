"""
Tests for employee lookup utility.
"""
import pytest
from unittest.mock import Mock, patch

from utils.employee_lookup import EmployeeLookup


class TestEmployeeLookup:
    """Test EmployeeLookup class."""

    def test_init(self):
        """Test EmployeeLookup initialization."""
        lookup = EmployeeLookup()
        assert lookup.SHEET_ID is not None
        assert lookup.SHEET_NAME is not None

    @patch('utils.employee_lookup.Config')
    def test_find_by_name_dry_run(self, mock_config):
        """Test find_by_name in dry run mode."""
        lookup = EmployeeLookup()
        result = lookup.find_by_name("Test User", dry_run=True)

        assert result is not None
        assert result["employee_name"] == "Test User"
        assert result["email"] == "test@example.com"

    def test_get_employee_summary(self):
        """Test get_employee_summary formatting."""
        lookup = EmployeeLookup()
        employee = {
            "employee_name": "John Doe",
            "email": "john@example.com",
            "company": "Test Company",
            "job_title": "Developer",
            "contract_end": "2025-12-31",
        }

        summary = lookup.get_employee_summary(employee)

        assert "John Doe" in summary
        assert "john@example.com" in summary
        assert "Test Company" in summary
        assert "Developer" in summary
        assert "2025-12-31" in summary
