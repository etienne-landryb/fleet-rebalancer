"""List all models available on the configured Groq API key."""

import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from groq import Groq

from rebalancer.config import get_settings

settings = get_settings()
client = Groq(api_key=settings.groq_api_key)
models = client.models.list()
for m in sorted(models.data, key=lambda x: x.id):
    print(m.id)
