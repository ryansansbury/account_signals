"""The model layer offline, with a fake transport and a made-up key: what each request carries, what a reply becomes,
and the retries. No network and no real key."""
import contextlib
import io
import json
import unittest

from agents import llm

KEY = "made-up-key-for-a-test-only"


def transport(*answers):
    calls = []

    def send(url, headers, body, timeout):
        calls.append({"url": url, "headers": headers, "body": json.loads(body)})
        status, data = answers[min(len(calls) - 1, len(answers) - 1)]
        return status, json.dumps(data).encode()
    send.calls = calls
    return send


class AnthropicBackend(unittest.TestCase):
    def test_the_request_caches_the_prompt_and_allows_room_to_reason(self):
        send = transport((200, {"content": [{"type": "text", "text": "{}"}], "usage": {}}))
        llm.AnthropicAPI(KEY, "claude-haiku-5-5", transport=send)("the prompt", "the sources")
        body = send.calls[0]["body"]
        self.assertEqual(body["max_tokens"], 16000)
        self.assertEqual(body["system"][0]["cache_control"], {"type": "ephemeral"})
        self.assertEqual(body["messages"], [{"role": "user", "content": "the sources"}])

    def test_a_reply_keeps_only_its_text_and_reports_why_it_stopped(self):
        reply = {"content": [{"type": "thinking", "thinking": "working it out"}, {"type": "text", "text": '{"a": 1}'}],
                 "usage": {"input_tokens": 1000, "output_tokens": 2000, "cache_creation_input_tokens": 0,
                           "cache_read_input_tokens": 3000}, "stop_reason": "end_turn"}
        text, meta = llm.AnthropicAPI(KEY, "claude-haiku-5-5", transport=transport((200, reply)), price_in=1,
                                      price_out=5)("p", "u")
        self.assertEqual(text, '{"a": 1}')
        self.assertEqual(meta["stop_reason"], "end_turn")
        self.assertEqual(meta["cost_usd"], round((1000 + 3000 * 0.1) * 1 / 1e6 + 2000 * 5 / 1e6, 6))

    def test_an_overloaded_api_is_tried_again(self):
        send = transport((529, {"error": {"message": "overloaded"}}),
                         (200, {"content": [{"type": "text", "text": "{}"}], "usage": {}}))
        text, _ = llm.AnthropicAPI(KEY, "claude-haiku-5-5", transport=send, sleep=lambda s: None)("p", "u")
        self.assertEqual((text, len(send.calls)), ("{}", 2))

    def test_a_refused_key_stops_with_the_fix(self):
        with self.assertRaises(RuntimeError) as caught:
            llm.AnthropicAPI(KEY, "claude-haiku-5-5", transport=transport((401, {"error": {"message": "no"}})))("p", "u")
        self.assertIn("owner/keys.sh", str(caught.exception))
        self.assertNotIn(KEY, str(caught.exception))


class OpenAIBackend(unittest.TestCase):
    def test_the_request_and_the_reply(self):
        send = transport((200, {"choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
                                "usage": {"prompt_tokens": 10, "completion_tokens": 20}}))
        text, meta = llm.OpenAICompatible(KEY, "gpt-6-luna", "https://api.openai.com/v1", transport=send)("p", "u")
        body = send.calls[0]["body"]
        self.assertEqual(body["max_completion_tokens"], 16000)
        self.assertEqual([m["role"] for m in body["messages"]], ["system", "user"])
        self.assertEqual((text, meta["stop_reason"]), ("{}", "stop"))


HELP = ("--model --output-format --system-prompt --max-turns --tools --disallowedTools --strict-mcp-config "
        "--no-session-persistence")


class Run:
    """A stand-in for subprocess.run: the help text first, then the replies in order, and every call kept."""

    def __init__(self, *replies, help_text=HELP):
        self.calls, self.replies, self.help = [], list(replies), help_text

    def __call__(self, args, **kw):
        self.calls.append((args, kw))
        if args[-1] == "--help":
            return type("R", (), {"returncode": 0, "stdout": self.help, "stderr": ""})()
        code, out, err = self.replies.pop(0)
        return type("R", (), {"returncode": code, "stdout": out, "stderr": err})()


REPLY = json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "{\"why_now\": []}",
                    "duration_ms": 2400, "total_cost_usd": 0.0123,
                    "usage": {"input_tokens": 900, "output_tokens": 300, "cache_creation_input_tokens": 50,
                              "cache_read_input_tokens": 0}, "modelUsage": {"claude-sonnet-5-5": {}}})


class ClaudeCommandLine(unittest.TestCase):
    def test_each_call_runs_alone_with_every_tool_off(self):
        run = Run((0, REPLY, ""))
        cli = llm.ClaudeCLI("sonnet", which=lambda name: "/bin/claude", run=run)
        text, meta = cli("the frozen prompt", "the account's postings")
        args, kw = run.calls[1]
        self.assertEqual(args[:2], ["claude", "-p"])
        self.assertEqual(args[args.index("--model") + 1], "sonnet")
        self.assertEqual(args[args.index("--tools") + 1], "")
        self.assertEqual(args[-3:], ["--system-prompt", "the frozen prompt", "the account's postings"])
        self.assertIn("account-signals-", kw["cwd"])
        self.assertEqual(text, "{\"why_now\": []}")
        self.assertEqual((meta["input_tokens"], meta["output_tokens"], meta["cache_write_tokens"]), (900, 300, 50))
        self.assertEqual((meta["cost_usd"], meta["model"], meta["ms"]), (0.0123, "claude-sonnet-5-5", 2400))

    def test_an_older_command_line_turns_the_tools_off_by_name(self):
        run = Run((0, REPLY, ""), help_text="--model --output-format --disallowedTools")
        llm.ClaudeCLI("haiku", which=lambda name: "/bin/claude", run=run)("p", "u")
        args = run.calls[1][0]
        self.assertIn("--disallowedTools", args)
        self.assertNotIn("--tools", args)
        self.assertEqual(args[-1], "p\n\nu")

    def test_a_failed_call_is_tried_again_and_then_says_why(self):
        waits = []
        run = Run((1, "", "overloaded"), (0, REPLY, ""))
        cli = llm.ClaudeCLI("opus", which=lambda name: "claude", run=run, sleep=waits.append)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli("p", "u")[0], "{\"why_now\": []}")
        self.assertEqual(waits, [2])
        bad = json.dumps({"type": "result", "is_error": True, "result": "Failed to authenticate: OAuth session expired"})
        run = Run((1, bad, ""))
        with self.assertRaises(RuntimeError):
            llm.ClaudeCLI("opus", which=lambda name: "claude", run=run, sleep=waits.append)("p", "u")
        self.assertEqual((len(run.calls), waits), (2, [2]))  # the help text and one call: a failed login never retries

    def test_a_failed_call_says_why(self):
        run = Run((1, "", "rate limited"), (1, "", "rate limited"), (1, "", "rate limited"))
        cli = llm.ClaudeCLI("opus", which=lambda name: "claude", run=run, sleep=lambda s: None)
        with self.assertRaises(RuntimeError) as e, contextlib.redirect_stderr(io.StringIO()):
            cli("p", "u")
        self.assertIn("rate limited", str(e.exception))

    def test_an_error_result_is_never_a_brief(self):
        bad = json.dumps({"type": "result", "is_error": True, "result": "usage limit reached"})
        with self.assertRaises(RuntimeError):
            llm.ClaudeCLI("opus", which=lambda name: "claude", run=Run((0, bad, "")), retries=0)("p", "u")

    def test_the_config_reaches_it_with_no_key(self):
        def no_key(item):
            raise AssertionError("a Claude plan call never reads a key")
        made, real = [], llm.ClaudeCLI

        class Fake(real):
            def __init__(self, model):
                made.append(model)
                real.__init__(self, model, which=lambda name: "claude", run=Run())
        llm.ClaudeCLI = Fake
        try:
            b = llm.backend_for({"id": "claude-opus", "via": "claude-cli", "model": "opus"}, no_key)
        finally:
            llm.ClaudeCLI = real
        self.assertEqual((made, b.described()["backend"]), (["opus"], "claude-cli"))

    def test_without_the_command_it_stops_with_the_fix(self):
        with self.assertRaises(SystemExit):
            llm.ClaudeCLI("opus", which=lambda name: None, run=Run())


if __name__ == "__main__":
    unittest.main()
