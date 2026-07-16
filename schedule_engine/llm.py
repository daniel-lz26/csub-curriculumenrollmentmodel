"""LLM client. Picks a provider from whatever credentials are in the
environment / .env, in order: OpenAI (OPENAI_API_KEY), Anthropic API
(ANTHROPIC_API_KEY), then AWS Bedrock (AWS creds with bedrock:InvokeModel).
All providers share one chat(system, messages) interface.
"""
import json
import os

from . import config


def _load_dotenv():
    path = os.path.join(config.REPO, ".env")
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


class LLM:
    def __init__(self):
        _load_dotenv()
        self.provider = None
        if os.environ.get("OPENAI_API_KEY"):
            import openai
            self.client = openai.OpenAI()
            self.model = os.environ.get("OPENAI_MODEL", config.OPENAI_MODEL)
            self.provider = "openai"
        elif os.environ.get("ANTHROPIC_API_KEY"):
            import anthropic
            self.client = anthropic.Anthropic()
            self.model = config.DEFAULT_MODEL
            self.provider = "anthropic"
        else:
            try:
                import boto3
                sts = boto3.client("sts")
                sts.get_caller_identity()
                self.client = boto3.client("bedrock-runtime",
                                           region_name=config.BEDROCK_REGION)
                self.model = config.BEDROCK_MODEL
                self.provider = "bedrock"
            except Exception:
                raise SystemExit(
                    "No LLM credentials found. Put one of these in a .env at the\n"
                    "repo root: OPENAI_API_KEY=... or ANTHROPIC_API_KEY=...,\n"
                    "or configure AWS credentials with bedrock:InvokeModel.")

    def chat(self, system: str, messages: list, max_tokens: int = 8000) -> str:
        """messages: [{'role': 'user'|'assistant', 'content': str}, ...]"""
        if self.provider == "openai":
            resp = self.client.chat.completions.create(
                model=self.model, max_tokens=max_tokens,
                messages=[{"role": "system", "content": system}] + messages)
            return resp.choices[0].message.content or ""
        if self.provider == "anthropic":
            resp = self.client.messages.create(
                model=self.model, max_tokens=max_tokens,
                system=system, messages=messages)
            return "".join(b.text for b in resp.content if b.type == "text")
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
        }
        raw = self.client.invoke_model(modelId=self.model, body=json.dumps(body))
        out = json.loads(raw["body"].read())
        return "".join(b["text"] for b in out["content"]
                       if b.get("type") == "text")
