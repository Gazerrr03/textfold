"""A service that answers only streamed (#23): a reply that comes as server-sent events is joined into one, a service
that refuses a request not streamed is asked again with "stream": true, and every other endpoint gets the request it
got before. A local server stands in for the services; no network.

Run from the repo root:
    python3 -m unittest discover tests
"""
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from textfold import llm_openai

REPLY = {"takeaway": "流式的回复也能读", "topic": "流式"}


def sse(text, usage=None):
    """text sent as a stream: a role chunk, the text in three pieces, an empty one, [DONE]."""
    n = len(text) // 3
    pieces = [text[:n], text[n:2 * n], text[2 * n:]]
    chunks = [{"choices": [{"index": 0, "delta": {"role": "assistant"}}]}]
    chunks += [{"choices": [{"index": 0, "delta": {"content": p}}]} for p in pieces]
    chunks.append({"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}], **({"usage": usage} if usage else {})})
    return "".join(f"data: {json.dumps(c, ensure_ascii=False)}\n\n" for c in chunks) + "data: [DONE]\n\n"


class Service(BaseHTTPRequestHandler):
    """/plain answers as most endpoints do; /only takes a stream alone and says so; /mute takes a stream alone and
    says nothing of it; /always streams whatever it is asked."""
    seen = []

    def log_message(self, *a):
        pass

    def send(self, code, body, kind="application/json"):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        Service.seen.append((self.path, body))
        text = json.dumps(REPLY, ensure_ascii=False)
        if self.path.startswith("/plain"):
            return self.send(200, json.dumps({"choices": [{"message": {"content": text}}]}, ensure_ascii=False))
        if self.path.startswith("/always"):
            return self.send(200, sse(text), "text/event-stream; charset=utf-8")
        if not body.get("stream"):
            said = {"error": {"message": "only stream=true is supported"}} if self.path.startswith("/only") else {"error": "bad request"}
            return self.send(400, json.dumps(said))
        return self.send(200, sse(text, {"total_tokens": 12}), "text/event-stream")


class Streamed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Service)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        Service.seen.clear()
        llm_openai._WORKED.clear()

    def ask(self, path):
        spec = {"base": f"{self.base}/{path}", "model": "m", "api_key": "k", "provider": path}
        return llm_openai.call("Fold this.", {"type": "object"}, spec, "system", 10)

    def test_an_endpoint_that_answers_whole_is_asked_as_before(self):
        self.assertEqual(self.ask("plain"), (REPLY, None))
        self.assertEqual(len(Service.seen), 1)
        self.assertNotIn("stream", Service.seen[0][1])
        self.assertEqual(Service.seen[0][1]["response_format"], {"type": "json_object"})

    def test_a_service_that_says_it_takes_a_stream_alone(self):
        self.assertEqual(self.ask("only"), (REPLY, None))
        self.assertEqual([b.get("stream") for _, b in Service.seen], [None, True])   # straight to the stream
        self.ask("only")   # the way that worked is remembered
        self.assertEqual([b.get("stream") for _, b in Service.seen], [None, True, True])

    def test_a_service_that_takes_a_stream_alone_without_saying_so(self):
        self.assertEqual(self.ask("mute"), (REPLY, None))
        self.assertEqual([b.get("stream") for _, b in Service.seen], [None, None, True])

    def test_a_reply_streamed_unasked(self):
        self.assertEqual(self.ask("always"), (REPLY, None))
        self.assertEqual(len(Service.seen), 1)
        self.assertNotIn("stream", Service.seen[0][1])


class Events(unittest.TestCase):
    def test_the_pieces_joined(self):
        d = llm_openai._events(sse('{"a": "第一 行"}', {"total_tokens": 3}).encode())
        self.assertEqual(llm_openai._content(d), '{"a": "第一 行"}')
        self.assertEqual(d["usage"], {"total_tokens": 3})

    def test_parts_comments_and_other_choices(self):
        raw = (": keep-alive\n\n"
               'data: {"choices": [{"index": 0, "delta": {"content": [{"type": "text", "text": "{\\"a\\""}]}}]}\n\n'
               'data: {"choices": [{"index": 1, "delta": {"content": "other"}}]}\n\n'
               'data: {"choices": [{"index": 0, "delta": {"content": ": 1}"}}]}\n\n'
               "data: [DONE]\n\n")
        self.assertEqual(llm_openai._content(llm_openai._events(raw.encode())), '{"a": 1}')

    def test_an_error_in_the_stream(self):
        d = llm_openai._events(b'data: {"error": {"message": "quota exceeded"}}\n\n')
        self.assertIsNone(llm_openai._content(d))
        self.assertEqual(d["error"]["message"], "quota exceeded")


if __name__ == "__main__":
    unittest.main()
