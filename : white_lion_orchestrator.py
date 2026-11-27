import json
import logging
import os
from typing import Any

import anthropic
import google.generativeai as genai
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

COMMANDER_MODEL = os.getenv("COMMANDER_MODEL", "gpt-4o")
CONTENT_MODEL = os.getenv("CONTENT_MODEL", "claude-3-5-sonnet-20241022")
TECH_MODEL = os.getenv("TECH_MODEL", "claude-3-5-sonnet-20241022")
MARKETING_MODEL = os.getenv("MARKETING_MODEL", "gemini-1.5-pro")
SHOPPING_MODEL = os.getenv("SHOPPING_MODEL", MARKETING_MODEL)
TEACHER_MODEL = os.getenv("TEACHER_MODEL", "llama-3.3-70b-versatile")

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY")) if os.getenv("OPENAI_API_KEY") else None
anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY")) if os.getenv("ANTHROPIC_API_KEY") else None

if os.getenv("GEMINI_API_KEY"):
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

teacher_client = (
    OpenAI(
        api_key=os.getenv("TEACHER_API_KEY") or os.getenv("GROQ_API_KEY"),
        base_url=os.getenv("TEACHER_BASE_URL", "https://api.groq.com/openai/v1"),
    )
    if os.getenv("TEACHER_API_KEY") or os.getenv("GROQ_API_KEY") else None
)

AGENT_NAMES = {"content", "marketing", "tech", "teacher", "shopping"}
MAX_TASKS = 4

def _text_from_anthropic(response: Any) -> str:
    return "\n".join(block.text for block in response.content if getattr(block, "type", None) == "text")

def _safe_error(exc: Exception) -> dict:
    logging.error("فشل استدعاء المزوّد (%s).", type(exc).__name__)
    return {"status": "error", "message": f"Provider error: {type(exc).__name__}"}

class WhiteLionOrchestrator:
    def run_commander(self, user_goal: str) -> dict:
        if not openai_client:
            return {"status": "error", "message": "OPENAI_API_KEY غير مضبوط."}

        system_prompt = f"""
You are the White Lion task planner.
Return ONLY a JSON object in this schema:
{{"tasks":[{{"agent":"content|marketing|tech|teacher|shopping",
"task":"specific task description","action":"generate|review|publish|payment"}}]}}
Rules: between 1 and {MAX_TASKS} tasks; use only listed agents;
never request live publishing, purchases, or transactions.
"""
        try:
            response = openai_client.chat.completions.create(
                model=COMMANDER_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_goal},
                ],
                response_format={"type": "json_object"},
            )
            parsed = json.loads(response.choices[0].message.content or "")
            self._validate_tasks(parsed)
            return parsed
        except Exception as exc:
            return _safe_error(exc)

    @staticmethod
    def _validate_tasks(tasks_json: dict) -> list[dict]:
        tasks = tasks_json.get("tasks") if isinstance(tasks_json, dict) else None
        if not isinstance(tasks, list) or not 1 <= len(tasks) <= MAX_TASKS:
            raise ValueError(f"يجب أن تكون tasks مصفوفة من 1 إلى {MAX_TASKS} مهام.")
        for task in tasks:
            if not isinstance(task, dict):
                raise ValueError("كل مهمة يجب أن تكون كائن JSON.")
            if task.get("agent") not in AGENT_NAMES:
                raise ValueError("اسم وكيل غير مسموح.")
            if not isinstance(task.get("task"), str) or not task["task"].strip():
                raise ValueError("وصف المهمة مفقود أو غير صالح.")
        return tasks

    def run_content_agent(self, task_prompt: str) -> dict:
        return self._run_anthropic(
            CONTENT_MODEL,
            "You are White Lion's silent 3D scriptwriter. Use the format: 🎬 Hook, 📽️ Scenes, 🖼️ Prompts, 📝 Title. Hook the viewer in the first 3 seconds. Keep character consistency with --cref where relevant.",
            task_prompt,
        )

    def run_tech_agent(self, task_prompt: str) -> dict:
        return self._run_anthropic(
            TECH_MODEL,
            "You are White Lion's Python engineer. Write production-ready code. Use Arabic comments and English variable names. Do not set temperature, top_p, or top_k. Handle stop reasons explicitly.",
            task_prompt,
        )

    def _run_anthropic(self, model: str, system_prompt: str, task_prompt: str) -> dict:
        if not anthropic_client:
            return {"status": "error", "message": "ANTHROPIC_API_KEY غير مضبوط."}
        try:
            response = anthropic_client.messages.create(
                model=model,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": task_prompt}],
            )
            stop_reason = response.stop_reason
            if stop_reason == "end_turn":
                return {"status": "success", "content": _text_from_anthropic(response)}
            if stop_reason == "tool_use":
                return {"status": "tool_use", "content": _text_from_anthropic(response), "message": "يلزم تنفيذ الأدوات عبر تكامل موثوق ومصرّح به."}
            if stop_reason == "max_tokens":
                return {"status": "error", "message": "بلغ الرد حد الرموز؛ قسّم المهمة."}
            if stop_reason == "refusal":
                return {"status": "error", "message": "رفض النموذج تنفيذ الطلب."}
            return {"status": "unknown", "stop_reason": stop_reason}
        except Exception as exc:
            return _safe_error(exc)

    def run_marketing_agent(self, task_prompt: str) -> dict:
        return self._run_gemini(
            MARKETING_MODEL,
            "You are White Lion's growth strategist. Include mandatory A/B tests, a target audience table, and budget planning. The White Lion Voice section must be 120–220 words.",
            task_prompt,
        )

    def run_shopping_agent(self, task_prompt: str) -> dict:
        return self._run_gemini(
            SHOPPING_MODEL,
            "You are a product-research assistant. Compare options using only information supplied in the prompt. Do not claim live prices, make purchases, or place orders. State when data is missing.",
            task_prompt,
        )

    @staticmethod
    def _run_gemini(model: str, system_prompt: str, task_prompt: str) -> dict:
        if not os.getenv("GEMINI_API_KEY"):
            return {"status": "error", "message": "GEMINI_API_KEY غير مضبوط."}
        try:
            gemini_model = genai.GenerativeModel(model_name=model, system_instruction=system_prompt)
            response = gemini_model.generate_content(task_prompt)
            return {"status": "success", "content": response.text}
        except Exception as exc:
            return _safe_error(exc)

    def run_teacher_agent(self, content_to_review: str) -> dict:
        if not teacher_client:
            return {"status": "error", "message": "اضبط TEACHER_API_KEY أو GROQ_API_KEY للمراجع."}
        try:
            response = teacher_client.chat.completions.create(
                model=TEACHER_MODEL,
                messages=[
                    {"role": "system", "content": "Audit the output. Use: Problem + Reason + Solution + Priority (P0/P1/P2). Score /10. No flattery. Suggest one tangible improvement."},
                    {"role": "user", "content": content_to_review},
                ],
            )
            return {"status": "success", "content": response.choices[0].message.content or ""}
        except Exception as exc:
            return _safe_error(exc)
