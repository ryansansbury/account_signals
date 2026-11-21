"""How the recorder reaches a model. Every backend answers the same call, model(system, user) -> (text, meta).

- AnthropicAPI calls the Anthropic Messages API, with the frozen system prompt marked for prompt caching, since every
  brief shares it.
- OpenAICompatible calls OpenAI's Chat Completions for GPT-6 Luna.
- ClaudeCLI calls Claude through the Claude Code command line (claude -p) on the owner's Claude plan, with no key. It
  runs each call in a fresh empty folder with every tool off, and the cost it keeps is the one the command line reports,
  which is what the same call would cost at API prices (11/20).

Both retry rate limits and server errors, time each call, and report tokens and cost at the list prices in
config/models.json. The output cap is 16,000 tokens for every model, since a model's own reasoning counts against it:
at 4,000, Claude Haiku 5.5 ran out before finishing two of six dev briefs. The caller hands each key in, read from the macOS Keychain by owner code, so this module never reads
a key and nothing here ever prints one. The build calls none of this. It replays what the recorder saved.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
RETRY_STATUS = (429, 500, 502, 503, 504, 529)
MAX_TOKENS = 16000
TIMEOUT = 300
CACHE_WRITE, CACHE_READ = 1.25, 0.1
# The command line's flags this backend uses when the installed version offers them.
FLAGS = ("--model", "--output-format", "--system-prompt", "--max-turns", "--tools", "--disallowedTools",
         "--strict-mcp-config", "--no-session-persistence")
NO_TOOLS = "Bash Edit Write Read Glob Grep WebFetch WebSearch NotebookEdit Task TodoWrite"


def urllib_transport(url, headers, body, timeout):
    """POST body to url. Returns (status, response bytes), with an HTTP error's status and body returned too."""
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def cost(tokens_in, tokens_out, price_in, price_out, cache_write=0, cache_read=0):
    """Dollars at list prices per million tokens, with cache writes and reads at their multiples of the input price."""
    if None in (tokens_in, tokens_out, price_in, price_out):
        return None
    dollars = (tokens_in + cache_write * CACHE_WRITE + cache_read * CACHE_READ) * price_in + tokens_out * price_out
    return round(dollars / 1e6, 6)


def error_text(raw):
    try:
        data = json.loads(raw)
        err = data.get("error")
        return (err.get("message") if isinstance(err, dict) else str(err)) or str(data)[:300]
    except (ValueError, AttributeError):
        return (raw or b"")[:300].decode("utf-8", "replace")


class AnthropicAPI:
    """model(system, user) through the Messages API, with two retries on rate limits and server errors."""

    def __init__(self, key, model, max_tokens=MAX_TOKENS, timeout=TIMEOUT, retries=2, transport=None, sleep=time.sleep,
                 price_in=None, price_out=None):
        if not key:
            raise ValueError("The Anthropic API needs a key from the Keychain.")
        self.key, self.model = key, model
        self.max_tokens, self.timeout, self.retries = max_tokens, timeout, retries
        self.transport, self.sleep = transport or urllib_transport, sleep
        self.price_in, self.price_out = price_in, price_out

    def request(self, system, user):
        headers = {"x-api-key": self.key, "anthropic-version": API_VERSION, "content-type": "application/json"}
        body = {"model": self.model, "max_tokens": self.max_tokens,
                "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                "messages": [{"role": "user", "content": user}]}
        return headers, json.dumps(body).encode()

    def __call__(self, system, user):
        headers, body = self.request(system, user)
        t0 = time.time()
        for attempt in range(self.retries + 1):
            status, raw = self.transport(API_URL, headers, body, self.timeout)
            if status == 200:
                data = json.loads(raw)
                text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
                u = data.get("usage") or {}
                meta = {"ms": round((time.time() - t0) * 1000), "input_tokens": u.get("input_tokens"),
                        "output_tokens": u.get("output_tokens"),
                        "cache_write_tokens": u.get("cache_creation_input_tokens") or 0,
                        "cache_read_tokens": u.get("cache_read_input_tokens") or 0,
                        "model": data.get("model", self.model), "stop_reason": data.get("stop_reason")}
                meta["cost_usd"] = cost(meta["input_tokens"], meta["output_tokens"], self.price_in, self.price_out,
                                        meta["cache_write_tokens"], meta["cache_read_tokens"])
                return text, meta
            if status in (401, 403):
                raise RuntimeError(f"The Anthropic API refused the key ({status}). Save it again with "
                                   "bash owner/keys.sh anthropic.")
            if status in RETRY_STATUS and attempt < self.retries:
                self.sleep(2 * 3 ** attempt)
                continue
            raise RuntimeError(f"The Anthropic API answered {status}: {error_text(raw)}")

    def described(self):
        return {"backend": "anthropic-api", "model": self.model}


class OpenAICompatible:
    """model(system, user) through Chat Completions, with four retries that back off up to 45 seconds."""

    def __init__(self, key, model, base_url, vendor="", keychain="", token_param="max_completion_tokens",
                 max_tokens=MAX_TOKENS, timeout=TIMEOUT * 2, retries=4, transport=None, sleep=time.sleep,
                 price_in=None, price_out=None):
        if not key:
            raise ValueError(f"{vendor or 'This vendor'} needs a key from the Keychain.")
        self.key, self.model, self.url = key, model, base_url.rstrip("/") + "/chat/completions"
        self.vendor, self.keychain, self.token_param = vendor, keychain, token_param
        self.max_tokens, self.timeout, self.retries = max_tokens, timeout, retries
        self.transport, self.sleep = transport or urllib_transport, sleep
        self.price_in, self.price_out = price_in, price_out

    def request(self, system, user):
        headers = {"authorization": f"Bearer {self.key}", "content-type": "application/json"}
        body = {"model": self.model, "messages": [{"role": "system", "content": system},
                                                  {"role": "user", "content": user}],
                self.token_param: self.max_tokens}
        return headers, json.dumps(body).encode()

    def __call__(self, system, user):
        headers, body = self.request(system, user)
        t0 = time.time()
        for attempt in range(self.retries + 1):
            status, raw = self.transport(self.url, headers, body, self.timeout)
            if status == 200:
                data = json.loads(raw)
                choice = (data.get("choices") or [{}])[0]
                content = (choice.get("message") or {}).get("content") or ""
                if isinstance(content, list):
                    content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
                u = data.get("usage") or {}
                meta = {"ms": round((time.time() - t0) * 1000), "input_tokens": u.get("prompt_tokens"),
                        "output_tokens": u.get("completion_tokens"), "cache_write_tokens": 0, "cache_read_tokens": 0,
                        "model": data.get("model", self.model), "stop_reason": choice.get("finish_reason")}
                meta["cost_usd"] = cost(meta["input_tokens"], meta["output_tokens"], self.price_in, self.price_out)
                return content, meta
            if status in (401, 403):
                raise RuntimeError(f"{self.vendor or 'The vendor'} refused the key ({status}). Save it again with "
                                   f"bash owner/keys.sh openai.")
            if status in RETRY_STATUS and attempt < self.retries:
                wait = min(2 * 3 ** attempt, 45)
                print(f"    {self.model}: {status}, trying again in {wait} s", file=sys.stderr, flush=True)
                self.sleep(wait)
                continue
            raise RuntimeError(f"{self.vendor or 'The vendor'} answered {status}: {error_text(raw)}")

    def described(self):
        return {"backend": "openai-compatible", "vendor": self.vendor, "model": self.model}


def parse_cli(stdout, ms, model):
    """The reply text and what the command line reported about the call, in the meta the other backends give. Anything
    it didn't report stays None."""
    try:
        data = json.loads(stdout)
    except ValueError:
        raise RuntimeError(f"claude -p answered something other than JSON: {stdout[:200]!r}")
    if isinstance(data, list):
        data = next((d for d in reversed(data) if isinstance(d, dict) and d.get("type") == "result"), {})
    if data.get("is_error"):
        raise RuntimeError(f"claude -p reported an error: {str(data.get('result'))[:300]}")
    u = data.get("usage") or {}
    used = sorted((data.get("modelUsage") or {}).keys())
    return str(data.get("result", "")), {
        "ms": round(float(data.get("duration_ms") or ms)), "input_tokens": u.get("input_tokens"),
        "output_tokens": u.get("output_tokens"), "cache_write_tokens": u.get("cache_creation_input_tokens") or 0,
        "cache_read_tokens": u.get("cache_read_input_tokens") or 0, "model": used[0] if len(used) == 1 else model,
        "models": used, "stop_reason": data.get("stop_reason") or data.get("subtype"),
        "cost_usd": data.get("total_cost_usd")}


def cli_reason(stdout, stderr):
    """The command line's own words for a failed call: the result or errors in its JSON when it printed some, else
    whatever it wrote."""
    try:
        data = json.loads(stdout or "")
        if isinstance(data, list):
            data = next((d for d in reversed(data) if isinstance(d, dict) and d.get("type") == "result"), {})
        said = data.get("result") or data.get("errors") or data.get("error") or data.get("subtype")
        if said:
            return str(said)[:400]
    except (ValueError, AttributeError):
        pass
    return ((stderr or "").strip() or (stdout or "").strip())[:400]


class ClaudeCLI:
    """model(system, user) through claude -p, with only the flags the installed command line offers. Each call runs in a
    fresh empty folder in the system's temporary space, outside any project, so no project's instructions reach the
    prompt, and every tool is off."""

    def __init__(self, model, timeout=TIMEOUT * 2, which=shutil.which, run=subprocess.run, retries=2, sleep=time.sleep):
        if not which("claude"):
            raise SystemExit("The claude command isn't on your PATH. Open Claude Code once, then run this again.")
        self.run, self.model, self.timeout, self.retries, self.sleep = run, model, timeout, retries, sleep
        help_text = run(["claude", "--help"], capture_output=True, text=True, timeout=60).stdout or ""
        self.flags = {f: f in help_text for f in FLAGS}
        self.tools_flag = "--tools" if self.flags["--tools"] else "--disallowedTools" if self.flags["--disallowedTools"] \
            else None

    def args(self, system, user):
        a = ["claude", "-p"]
        if self.flags["--model"]:
            a += ["--model", self.model]
        if self.flags["--output-format"]:
            a += ["--output-format", "json"]
        if self.flags["--max-turns"]:
            a += ["--max-turns", "1"]
        if self.tools_flag == "--tools":
            a += ["--tools", ""]
        elif self.tools_flag == "--disallowedTools":
            a += ["--disallowedTools", NO_TOOLS]
        if self.flags["--strict-mcp-config"]:
            a.append("--strict-mcp-config")
        if self.flags["--no-session-persistence"]:
            a.append("--no-session-persistence")
        if self.flags["--system-prompt"]:
            return a + ["--system-prompt", system, user]
        return a + [system + "\n\n" + user]

    def __call__(self, system, user):
        """One call, tried again after a failure with a back-off of 2, 6, 18 and then 45 seconds. A failed login stops at
        once, since only logging in again fixes it."""
        for attempt in range(self.retries + 1):
            try:
                return self.once(system, user)
            except RuntimeError as e:
                if "authenticate" in str(e).lower() or "login" in str(e).lower() or attempt >= self.retries:
                    raise
                wait = min(2 * 3 ** attempt, 45)
                print(f"    {self.model}: {str(e)[:120]}, trying again in {wait} s", file=sys.stderr, flush=True)
                self.sleep(wait)

    def once(self, system, user):
        workdir = tempfile.mkdtemp(prefix="account-signals-")
        try:
            t0 = time.time()
            r = self.run(self.args(system, user), cwd=workdir, capture_output=True, text=True, timeout=self.timeout)
            if r.returncode != 0 and self.tools_flag == "--tools" and "tools" in (r.stderr or "").lower():
                self.tools_flag = "--disallowedTools" if self.flags["--disallowedTools"] else None
                r = self.run(self.args(system, user), cwd=workdir, capture_output=True, text=True, timeout=self.timeout)
            if r.returncode != 0:
                raise RuntimeError(f"claude -p exited with {r.returncode}: {cli_reason(r.stdout, r.stderr)}")
            return parse_cli(r.stdout, (time.time() - t0) * 1000, self.model)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    def described(self):
        return {"backend": "claude-cli", "model": self.model, "flags": [f for f, on in self.flags.items() if on],
                "tools_off": self.tools_flag}


def backend_for(entry, key_for):
    """The backend a config/models.json entry describes. key_for(item) returns that Keychain item's key."""
    prices = {"price_in": entry.get("price_in"), "price_out": entry.get("price_out")}
    if entry["via"] == "claude-cli":
        return ClaudeCLI(entry["model"])
    if entry["via"] == "anthropic":
        return AnthropicAPI(key_for(entry["keychain"]), entry["model"], **prices)
    if entry["via"] == "openai":
        return OpenAICompatible(key_for(entry["keychain"]), entry["model"], entry["base_url"],
                                vendor=entry.get("vendor", ""), keychain=entry["keychain"],
                                token_param=entry.get("token_param", "max_completion_tokens"), **prices)
    raise ValueError(f"{entry.get('id')} names an unknown way to reach its model: {entry.get('via')}")
