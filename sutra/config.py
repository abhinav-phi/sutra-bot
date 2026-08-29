"""Runtime settings. Env-overridable; tests inject overrides directly."""
import os
from dataclasses import dataclass, field
from pathlib import Path


def _load_dotenv(path=None):
    """Tiny .env loader (no dependency). Existing env vars always win, so
    `uvicorn bot:app` works out of the box after copying .env.example -> .env."""
    p = Path(path or (Path(__file__).parent / ".env"))
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


_load_dotenv()


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


@dataclass
class Settings:
    team_name: str = field(default_factory=lambda: os.environ.get("TEAM_NAME", "Team Sutra"))
    team_members: list = field(
        default_factory=lambda: [
            m.strip() for m in os.environ.get("TEAM_MEMBERS", "Member 1, Member 2").split(",") if m.strip()
        ]
    )
    contact_email: str = field(default_factory=lambda: os.environ.get("CONTACT_EMAIL", "team@example.com"))
    version: str = "1.0.0"

    anthropic_api_key: str = field(default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY", ""))
    openai_api_key: str = field(default_factory=lambda: os.environ.get("OPENAI_API_KEY", ""))
    openrouter_api_key: str = field(default_factory=lambda: os.environ.get("OPENROUTER_API_KEY", ""))
    openrouter_model: str = field(default_factory=lambda: os.environ.get("LLM_OPENROUTER_MODEL", "google/gemma-4-31b-it:free"))
    custom_llm_base_url: str = field(default_factory=lambda: os.environ.get("CUSTOM_LLM_BASE_URL", ""))
    custom_llm_api_key: str = field(default_factory=lambda: os.environ.get("CUSTOM_LLM_API_KEY", ""))
    custom_llm_model: str = field(default_factory=lambda: os.environ.get("CUSTOM_LLM_MODEL", "deepseek-v4-flash"))
    custom_llm_max_tokens: int = field(default_factory=lambda: _env_int("CUSTOM_LLM_MAX_TOKENS", 2000))
    # b.ai needs thinking:{"type":"disabled"}; Groq REJECTS unknown params — flag gates it
    custom_llm_send_thinking: bool = field(
        default_factory=lambda: os.environ.get("CUSTOM_LLM_SEND_THINKING", "1") not in {"0", "false", "no"})
    primary_model: str = field(default_factory=lambda: os.environ.get("LLM_PRIMARY_MODEL", "gpt-oss-120b"))
    secondary_model: str = field(default_factory=lambda: os.environ.get("LLM_SECONDARY_MODEL", "minimax-m3:free"))

    disable_llm: bool = field(default_factory=lambda: os.environ.get("DISABLE_LLM", "") in {"1", "true", "yes"})
    llm_timeout_s: float = field(default_factory=lambda: _env_float("LLM_TIMEOUT_S", 25.0))
    reply_llm_timeout_s: float = field(default_factory=lambda: _env_float("REPLY_LLM_TIMEOUT_S", 10.0))

    spend_soft_usd: float = field(default_factory=lambda: _env_float("SPEND_SOFT_USD", 20.0))
    spend_hard_usd: float = field(default_factory=lambda: _env_float("SPEND_HARD_USD", 25.0))

    snapshot_path: str = field(default_factory=lambda: os.environ.get("SNAPSHOT_PATH", "data/snapshot.json"))
    snapshot_interval_s: int = field(default_factory=lambda: _env_int("SNAPSHOT_INTERVAL_S", 30))
    artifacts_dir: str = field(default_factory=lambda: os.environ.get("ARTIFACTS_DIR", "data/artifacts"))

    max_actions_per_tick: int = field(default_factory=lambda: _env_int("MAX_ACTIONS_PER_TICK", 20))
    top_k_per_tick: int = field(default_factory=lambda: _env_int("TOP_K_PER_TICK", 5))
    tick_deadline_s: float = field(default_factory=lambda: _env_float("TICK_DEADLINE_S", 24.0))

    @property
    def llm_enabled(self) -> bool:
        return not self.disable_llm and bool(self.anthropic_api_key or self.openai_api_key
                                             or self.openrouter_api_key or self.custom_llm_api_key)


def repo_root() -> Path:
    """Challenge package root (contains dataset/, examples/, judge_simulator.py)."""
    return Path(__file__).resolve().parent.parent
