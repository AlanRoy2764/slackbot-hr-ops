"""
Slack Agent Orchestrator - Main entry point for Agent SDK integration.

Routes incoming Slack messages to appropriate HR skills using Claude Agent SDK.
Supports multi-turn param gathering: asks questions one at a time in the thread
until all required info is collected, then executes the skill.
"""
import calendar
import logging
import re
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

import anthropic
from config.prompts import get_orchestrator_system_prompt
from config.settings import Config
from skills import SKILL_REGISTRY
from skills.base_skill import SkillResult

# Configure logging
logging.basicConfig(
    level=Config.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-template: which params must be gathered interactively from the user.
# Everything else is auto-filled from employee data inside the skill.
# ---------------------------------------------------------------------------
TEMPLATE_PARAMS_TO_GATHER: Dict[str, List[str]] = {
    "contract_extension":    ["new_end_date"],
    "employment_contract":   ["career_level", "contract_type"],
    "internship_offer":      ["contract_term", "hod", "role_responsibilities"],
    "traineeship_offer":     ["contract_term", "hod", "role_responsibilities"],
    "probation_confirmation": ["salary", "benefits", "manager_title"],
}

# Params that are passed via custom_values (placeholder → value)
PARAM_TO_PLACEHOLDER: Dict[str, str] = {
    "contract_term":       "{{CONTRACT_TERM}}",
    "hod":                 "{{HOD}}",
    "role_responsibilities": "{{ROLE_RESPONSIBILITIES}}",
    "salary":              "{{SALARY}}",
    "benefits":            "{{BENEFITS}}",
    "manager_title":       "{{MANAGER_TITLE}}",
}

CAREER_LEVEL_MAP = {
    "1": "associate",
    "2": "senior_associate",
    "3": "assistant_manager",
    "4": "manager",
    "5": "senior_manager",
    "6": "c_suite",
    "7": "freelancer",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _add_months(dt: date, months: int) -> date:
    month = dt.month - 1 + months
    year = dt.year + month // 12
    month = month % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _fmt_date(d: date) -> str:
    return d.strftime("%-d %b %Y")


def _build_question(param_name: str, employee: Dict[str, Any],
                    template_type: str, step: int, total: int) -> str:
    """Return the mrkdwn question string for a given param."""
    name = employee.get("employee_name", employee.get("name", "the employee"))
    today = date.today()
    step_tag = f"_(Step {step} of {total})_\n\n" if total > 1 else ""

    if param_name == "new_end_date":
        d3  = _fmt_date(_add_months(today, 3))
        d6  = _fmt_date(_add_months(today, 6))
        d12 = _fmt_date(_add_months(today, 12))
        eoy = _fmt_date(date(today.year, 12, 31))
        return (
            f"{step_tag}"
            f"*What should the new contract end date be for {name}?*\n\n"
            f"Quick options:\n"
            f"• `3 months` → {d3}\n"
            f"• `6 months` → {d6}\n"
            f"• `1 year` → {d12}\n"
            f"• `end of year` → {eoy}\n\n"
            f"Or type a specific date, e.g. _\"31 Mar 2027\"_"
        )

    if param_name == "career_level":
        return (
            f"{step_tag}"
            f"*What is {name}'s career level?*\n\n"
            f"1. Associate\n"
            f"2. Senior Associate\n"
            f"3. Assistant Manager\n"
            f"4. Manager\n"
            f"5. Senior Manager\n"
            f"6. C-Suite\n"
            f"7. Freelancer\n\n"
            f"Reply with the number or the level name."
        )

    if param_name == "contract_type":
        return (
            f"{step_tag}"
            f"*What type of employment contract for {name}?*\n\n"
            f"1. Full-time, 1 year\n"
            f"2. Permanent\n"
            f"3. Fixed-term — _reply e.g. \"fixed 6\" for a 6-month contract_\n\n"
            f"Reply with the number or a description."
        )

    if param_name == "contract_term":
        kind = "internship" if template_type == "internship_offer" else "traineeship"
        return (
            f"{step_tag}"
            f"*How long is the {kind} for {name}?*\n\n"
            f"e.g. _\"3 months\"_, _\"6 months\"_, _\"1 year\"_"
        )

    if param_name == "hod":
        return (
            f"{step_tag}"
            f"*Who is the Head of Department (HOD) for this letter?*\n\n"
            f"Type the full name."
        )

    if param_name == "role_responsibilities":
        return (
            f"{step_tag}"
            f"*What are the key role responsibilities for {name}?*\n\n"
            f"Type a brief description, or _\"skip\"_ to leave blank."
        )

    if param_name == "salary":
        return (
            f"{step_tag}"
            f"*What is {name}'s confirmed monthly salary?*\n\n"
            f"e.g. _\"RM 5,000\"_"
        )

    if param_name == "benefits":
        return (
            f"{step_tag}"
            f"*What benefits should be listed in the letter for {name}?*\n\n"
            f"e.g. _\"Medical insurance, dental, annual leave as per EA\"_\n"
            f"Or _\"skip\"_ to leave blank."
        )

    if param_name == "manager_title":
        return (
            f"{step_tag}"
            f"*What is the signing manager's job title?*\n\n"
            f"e.g. _\"Head of People & Culture\"_"
        )

    return f"{step_tag}*What is the {param_name.replace('_', ' ')} for {name}?*"


def _build_contract_type_info(contract_type_str: str) -> Dict[str, Any]:
    if contract_type_str == "full-time-1yr":
        return {"type": "full-time", "months": 12, "display_name": "Full-time, 1 year"}
    if contract_type_str == "permanent":
        return {"type": "permanent", "months": None, "display_name": "Permanent"}
    if contract_type_str.startswith("fixed-term:"):
        try:
            months = int(contract_type_str.split(":")[1])
        except (IndexError, ValueError):
            months = 3
        return {"type": "fixed-term", "months": months, "display_name": f"Fixed-term, {months} months"}
    return {}


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class SlackAgentOrchestrator:
    """
    Orchestrates HR skill execution using Claude API.

    Supports multi-turn conversations in Slack threads to gather all required
    parameters before executing a skill.
    """

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        self.system_prompt = get_orchestrator_system_prompt()
        self.skills = list(SKILL_REGISTRY.keys())

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def process_message(
        self,
        user_message: str,
        user_id: str,
        channel_id: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        user_context: Optional[Dict[str, Any]] = None,
        session: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Process a user message.

        If the session has a pending skill execution (waiting for more params),
        continue gathering. Otherwise detect intent and start fresh.
        """
        try:
            # ── 1. Continue a pending param-gathering flow ──────────────
            if session and session.get_skill_state("pending"):
                logger.info("[Orchestrator] Continuing pending skill gathering")
                return await self._continue_gathering(user_message, session)

            # ── 2. Call Claude to understand the message ────────────────
            prompt = self._build_prompt(user_message, conversation_history, user_context)
            logger.info(f"[Claude API] Processing: {user_message[:80]!r}")
            claude_response = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2000,
                system=self.system_prompt,
                messages=[{"role": "user", "content": prompt}]
            )
            response_text = claude_response.content[0].text
            logger.info(f"[Claude API] Got response: {response_text[:80]!r}")

            # ── 3. Try to invoke a skill (may start gathering flow) ─────
            skill_outcome = await self._try_invoke_skill(
                user_message=user_message,
                conversation_history=conversation_history,
                session=session,
            )

            if skill_outcome is None:
                # No skill matched — return Claude's conversational reply
                return {
                    "message": response_text,
                    "blocks": None,
                    "skill_used": None,
                    "success": True,
                }

            if isinstance(skill_outcome, dict):
                # Gathering mode — return the question to the user
                return skill_outcome

            # It's a SkillResult — convert to response dict
            slack_message = skill_outcome.to_slack_message()
            return {
                "message": slack_message.get("text", skill_outcome.message),
                "blocks": slack_message.get("blocks"),
                "skill_used": skill_outcome.__class__.__name__,
                "success": skill_outcome.success,
            }

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            return {
                "message": "Sorry, I encountered an error processing your request.",
                "blocks": None,
                "skill_used": None,
                "error": str(e),
                "success": False,
            }

    # ------------------------------------------------------------------
    # Skill intent detection and param gathering
    # ------------------------------------------------------------------

    async def _try_invoke_skill(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        session: Optional[Any] = None,
    ) -> Optional[Union[SkillResult, Dict[str, Any]]]:
        """
        Detect skill intent, then either:
          - Start gathering params (store pending state, return question dict)
          - Execute the skill immediately (return SkillResult)
          - Return None if no skill matched
        """
        skill_patterns = {
            "hr_letter": [
                "generate", "letter", "contract", "document",
                "employment contract", "extension", "probation",
                "internship", "traineeship", "offer letter",
            ],
            "onboarding": [
                "onboarding", "welcome email", "new hire", "send email",
            ],
        }

        user_lower = user_message.lower()
        matched_skill = None
        for skill_name, patterns in skill_patterns.items():
            if any(p in user_lower for p in patterns):
                matched_skill = skill_name
                break

        if not matched_skill:
            return None

        # Extract initial params (employee name + template type)
        params = await self._extract_params(user_message, matched_skill, conversation_history)
        if not params or "employee_name" not in params:
            return None

        # Look up the employee immediately so we can show their details
        from utils.employee_lookup import get_employee_lookup
        lookup = get_employee_lookup()
        employee = lookup.find_by_name(params["employee_name"])

        if not employee:
            return SkillResult(
                success=False,
                message=f"I couldn't find an employee named *{params['employee_name']}* in the Active Employees sheet.",
                error="Please double-check the name and try again."
            )

        # Determine which params still need to be gathered
        template_type = params.get("template_type", "contract_extension")
        params_needed = list(TEMPLATE_PARAMS_TO_GATHER.get(template_type, []))

        # Remove any already provided
        params_needed = [p for p in params_needed if not params.get(p)]

        if not params_needed:
            # Everything available — execute immediately
            return await self._execute_skill(matched_skill, params, employee)

        # Build employee summary for context
        emp_name = employee.get("employee_name", employee.get("name", "Employee"))
        emp_title = employee.get("job_title", employee.get("designation", ""))
        emp_company = employee.get("company", "")
        emp_contract_end = employee.get("contract_expiry", employee.get("contract_end", ""))
        template_labels = {
            "contract_extension":    "Contract Extension Letter",
            "employment_contract":   "Employment Contract",
            "internship_offer":      "Internship Offer Letter",
            "traineeship_offer":     "Traineeship Offer Letter",
            "probation_confirmation": "Probation Confirmation Letter",
        }
        template_label = template_labels.get(template_type, template_type.replace("_", " ").title())

        employee_info_parts = [f":bust_in_silhouette: *Found: {emp_name}*"]
        if emp_title:
            employee_info_parts.append(f"Position: {emp_title}")
        if emp_company:
            employee_info_parts.append(f"Company: {emp_company}")
        if emp_contract_end:
            employee_info_parts.append(f"Contract ends: {emp_contract_end}")
        employee_info = "  |  ".join(employee_info_parts[1:])
        employee_info = f"{employee_info_parts[0]}\n{employee_info}" if employee_info else employee_info_parts[0]

        intro = (
            f"{employee_info}\n\n"
            f"To generate the *{template_label}*, I need a bit more information.\n"
        )

        # Ask the first question
        total = len(params_needed)
        first_question = _build_question(params_needed[0], employee, template_type, 1, total)

        # Store pending state in session
        if session:
            session.set_skill_state("pending", {
                "skill_name":    matched_skill,
                "params":        params,
                "employee":      employee,
                "waiting_for":   params_needed,
                "total_params":  total,
            })

        return {
            "message": f"{intro}\n{first_question}",
            "blocks": None,
            "skill_used": None,
            "success": True,
            "gathering": True,
        }

    async def _continue_gathering(
        self, user_message: str, session: Any
    ) -> Dict[str, Any]:
        """Handle a thread reply that answers a pending param question."""
        pending = session.get_skill_state("pending")
        waiting_for: List[str] = pending["waiting_for"]
        current_param = waiting_for[0]

        logger.info(f"[Gathering] Got answer for '{current_param}': {user_message!r}")

        # Parse the user's answer into the right format
        employee = pending["employee"]
        parsed_value = await self._parse_param_answer(user_message, current_param, employee)
        logger.info(f"[Gathering] Parsed '{current_param}' = {parsed_value!r}")

        pending["params"][current_param] = parsed_value
        waiting_for.pop(0)

        if waiting_for:
            # Still more params to collect
            employee = pending["employee"]
            template_type = pending["params"]["template_type"]
            total = pending["total_params"]
            step = total - len(waiting_for) + 1
            next_question = _build_question(waiting_for[0], employee, template_type, step, total)
            session.set_skill_state("pending", pending)
            return {
                "message": next_question,
                "blocks": None,
                "skill_used": None,
                "success": True,
                "gathering": True,
            }

        # All params collected — execute
        session.clear_skill_state()
        skill_result = await self._execute_skill(
            pending["skill_name"], pending["params"], pending["employee"]
        )
        return skill_result

    async def _execute_skill(
        self,
        skill_name: str,
        params: Dict[str, Any],
        employee: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a skill with all params gathered and return a response dict."""
        final_params = dict(params)

        # Build custom_values for templates that use {{PLACEHOLDER}} overrides
        custom_values: Dict[str, str] = {}
        for param_name, placeholder in PARAM_TO_PLACEHOLDER.items():
            val = final_params.get(param_name, "")
            if val:
                custom_values[placeholder] = val
        if custom_values:
            final_params["custom_values"] = custom_values

        # Build contract_type_info for employment contracts
        if (skill_name == "hr_letter"
                and final_params.get("template_type") == "employment_contract"):
            ct = final_params.get("contract_type", "full-time-1yr")
            final_params["contract_type_info"] = _build_contract_type_info(ct)

        logger.info(f"[Skill] Executing {skill_name} with params: { {k: v for k, v in final_params.items() if k != 'employee'} }")

        skill_instance = SKILL_REGISTRY[skill_name]()
        skill_result = await skill_instance.execute(final_params)

        slack_message = skill_result.to_slack_message()
        return {
            "message": slack_message.get("text", skill_result.message),
            "blocks": slack_message.get("blocks"),
            "skill_used": skill_name,
            "success": skill_result.success,
        }

    # ------------------------------------------------------------------
    # Param extraction and parsing
    # ------------------------------------------------------------------

    async def _extract_params(
        self,
        user_message: str,
        skill_name: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Extract initial params (employee name + template type) using Claude."""
        params: Dict[str, Any] = {}

        # Use Claude haiku to extract the employee name
        logger.info(f"[Claude API] Extracting employee name from: {user_message!r}")
        name_response = self.client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=50,
            messages=[{
                "role": "user",
                "content": (
                    "Extract the employee's full name from this HR request. "
                    "Return ONLY the person's name — nothing else, no punctuation, no explanation. "
                    "If no name is present, return the single word: NONE\n\n"
                    f"Message: {user_message}"
                )
            }]
        )
        extracted_name = name_response.content[0].text.strip()
        logger.info(f"[Claude API] Extracted name: {extracted_name!r}")

        if not extracted_name or extracted_name.upper() == "NONE":
            return None

        params["employee_name"] = extracted_name

        # Detect template type for hr_letter
        if skill_name == "hr_letter":
            from skills.hr_letter_skill import HrLetterSkill
            skill = HrLetterSkill()
            msg_lower = user_message.lower()
            for template in skill.TEMPLATE_TYPES:
                if template.replace("_", " ") in msg_lower:
                    params["template_type"] = template
                    break
            if "template_type" not in params:
                params["template_type"] = "contract_extension"  # default

        return params

    async def _parse_param_answer(
        self, user_answer: str, param_name: str, employee: Optional[Dict[str, Any]] = None
    ) -> str:
        """Parse a free-form user answer into the structured value expected by the skill."""
        today = date.today()
        today_str = _fmt_date(today)

        if param_name == "new_end_date":
            contract_end = ""
            if employee:
                contract_end = employee.get("contract_expiry", employee.get("contract_end", ""))
            context = f"Today is {today_str}."
            if contract_end:
                context += f" The employee's current contract end date is {contract_end}."
            response = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=30,
                messages=[{
                    "role": "user",
                    "content": (
                        f"{context} The user said: '{user_answer}'. "
                        "Return ONLY the date they mean in 'D Mon YYYY' format (e.g. '31 Mar 2027'). "
                        "If they said '3 months', add 3 months to today. "
                        "If they said '1 year after her current contract end date', add 1 year to the contract end date. "
                        f"If they said 'end of year', return '31 Dec {today.year}'. "
                        "Return ONLY the date string, nothing else."
                    )
                }]
            )
            return response.content[0].text.strip()

        if param_name == "career_level":
            ans = user_answer.strip()
            if ans in CAREER_LEVEL_MAP:
                return CAREER_LEVEL_MAP[ans]
            response = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=30,
                messages=[{
                    "role": "user",
                    "content": (
                        f"The user said: '{user_answer}'. "
                        "Map to one of: associate, senior_associate, assistant_manager, "
                        "manager, senior_manager, c_suite, freelancer. "
                        "Return ONLY the exact value."
                    )
                }]
            )
            return response.content[0].text.strip()

        if param_name == "contract_type":
            ans = user_answer.strip().lower()
            if ans == "1" or "full" in ans or "1 year" in ans or "1yr" in ans:
                return "full-time-1yr"
            if ans == "2" or "permanent" in ans:
                return "permanent"
            # Fixed-term — extract months
            nums = re.findall(r"\d+", user_answer)
            months = int(nums[0]) if nums else 3
            return f"fixed-term:{months}"

        # Free-text params (hod, role_responsibilities, salary, benefits, etc.)
        val = user_answer.strip()
        return "" if val.lower() == "skip" else val

    # ------------------------------------------------------------------
    # Claude prompt builder
    # ------------------------------------------------------------------

    def _build_prompt(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        lines = [user_message]
        if conversation_history:
            lines.append("\n\nPrevious conversation:")
            for msg in conversation_history[-10:]:
                lines.append(f"\n{msg.get('role','user').capitalize()}: {msg.get('content','')}")
        if user_context:
            ctx = []
            if user_context.get("user_name"):
                ctx.append(f"User: {user_context['user_name']}")
            if user_context.get("channel_name"):
                ctx.append(f"Channel: {user_context['channel_name']}")
            if ctx:
                lines.append("\n\nContext: " + ", ".join(ctx))
        lines.append(f"\n\nAvailable skills: {', '.join(self.skills)}")
        return "\n".join(lines)

    # kept for backwards compat
    def build_prompt(self, user_message, conversation_history=None, user_context=None):
        return self._build_prompt(user_message, conversation_history, user_context)

    def get_help_message(self) -> str:
        from config.prompts import SKILL_DESCRIPTIONS
        return SKILL_DESCRIPTIONS


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_orchestrator: Optional[SlackAgentOrchestrator] = None


def get_orchestrator() -> SlackAgentOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SlackAgentOrchestrator()
    return _orchestrator
