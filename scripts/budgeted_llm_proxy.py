"""Temporary localhost OpenAI gateway for bounded Tencent extraction smoke tests.

Only chat completions are accepted. Four requests and $0.02 maximum reserved
list-price cost by default. Does not log prompts or expose the upstream API key.
This is experiment infrastructure, not a production proxy.
"""
import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


def main():
    import tiktoken
    from openai import OpenAI
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=18421)
    parser.add_argument("--ledger", default="reports/tencent-extraction-usage.json")
    args = parser.parse_args()
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], max_retries=0, timeout=20)
    encoding = tiktoken.encoding_for_model("gpt-4.1-mini")
    ledger = {"max_calls": 4, "max_reserved_usd": 0.02, "reserved_usd": 0,
              "estimated_actual_usd": 0, "calls": [], "model": "gpt-4.1-mini-2025-04-14"}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *unused):
            pass

        def reply(self, status, body):
            payload = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_POST(self):
            if self.path != "/v1/chat/completions":
                return self.reply(404, {"error": {"message": "unsupported experiment route"}})
            length = int(self.headers.get("Content-Length", "0"))
            if length > 32000:
                return self.reply(413, {"error": {"message": "experiment input cap"}})
            body = json.loads(self.rfile.read(length))
            max_input = len(encoding.encode(json.dumps(body.get("messages", [])))) + 512
            reserve = (max_input * 0.40 + 768 * 1.60) / 1e6
            if len(ledger["calls"]) >= 4 or ledger["reserved_usd"] + reserve > 0.02:
                return self.reply(429, {"error": {"message": "experiment budget exhausted"}})
            ledger["reserved_usd"] += reserve
            entry = {"status": "started", "reserved_usd": reserve}
            ledger["calls"].append(entry)
            try:
                response = client.chat.completions.create(model=ledger["model"], messages=body["messages"],
                    max_tokens=768, temperature=0)
                usage = response.usage.model_dump()
                actual = (usage["prompt_tokens"] * 0.40 + usage["completion_tokens"] * 1.60) / 1e6
                entry.update(status="completed", usage=usage, estimated_usd=actual)
                ledger["estimated_actual_usd"] += actual
                self.reply(200, response.model_dump())
            except Exception as exc:
                entry.update(status="failed", error_type=type(exc).__name__)
                self.reply(502, {"error": {"message": "experiment upstream request failed"}})
            finally:
                Path(args.ledger).parent.mkdir(parents=True, exist_ok=True)
                Path(args.ledger).write_text(json.dumps(ledger, indent=2) + "\n")

    HTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
