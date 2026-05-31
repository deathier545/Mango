"""Split mango/config.py into config_env.py + config_build.py."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "mango" / "config.py"
lines = CONFIG.read_text(encoding="utf-8").splitlines(keepends=True)

# Helpers: lines 29-66 (1-based) -> index 28:66
helpers = "".join(lines[28:66])
env_py = (
    '"""Environment variable parsing helpers for Mango config."""\n\n'
    "from __future__ import annotations\n\n"
    "import logging\n"
    "import os\n\n"
    "logger = logging.getLogger(__name__)\n\n"
    + helpers
)
(ROOT / "mango" / "config_env.py").write_text(env_py, encoding="utf-8")

# Build body: lines 230-949 (1-based) -> index 229:949
body = lines[229:949]
indented = "".join(("    " + L if L.strip() else L) for L in body)

build_header = '''"""Build a `Config` instance from `os.environ` (after dotenv load)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from mango.config import Config
from mango.config_env import (
    _float_env,
    _int_env,
    _ollama_base_url_from_env,
    _sanitize_api_key,
)
from mango.config_sections import (
    AudioConfig,
    LlmConfig,
    ToolPolicyConfig,
    TtsConfig,
    WakeConfig,
)
from mango.interruption_policy import resolve_profile
from mango.logging_setup import mask_secret
from mango.presets import known_presets
from mango.quiet_hours import parse_quiet_hours

logger = logging.getLogger(__name__)


def build_config_from_env() -> Config:
'''
build_py = build_header + indented + "\n"
(ROOT / "mango" / "config_build.py").write_text(build_py, encoding="utf-8")

# New config.py: lines 1-28 + dataclass through load stub + apply_cli
head = "".join(lines[0:28])
dataclass_part = "".join(lines[68:224])  # @dataclass through end of fields before load
load_stub = (
    "    @classmethod\n"
    "    def load(cls) -> Config:\n"
    "        from mango.config_dotenv import load_project_dotenv\n"
    "        from mango.config_build import build_config_from_env\n\n"
    "        load_project_dotenv(_PROJECT_ROOT)\n"
    "        return build_config_from_env()\n\n\n"
)
tail = "".join(lines[951:])  # apply_cli_wake_oww_test onward

new_config = (
    head
    + dataclass_part
    + load_stub
    + tail
)
CONFIG.write_text(new_config, encoding="utf-8")
print("config_env.py", len(env_py.splitlines()), "lines")
print("config_build.py", len(build_py.splitlines()), "lines")
print("config.py", len(new_config.splitlines()), "lines")
