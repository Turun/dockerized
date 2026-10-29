#!/usr/bin/env python3
"""
pushgateway_lite.py — minimal Prometheus Pushgateway replacement.

Why this exists: the official Pushgateway categorically REJECTS metrics
that carry timestamps ("pushed metrics must not have timestamps", see
its storage/diskmetricstore.go — unconditional, no flag). Our smart-meter
receiver back-dates every reading to its true measurement time (paced
drain, outage backlog), so we need those timestamps to survive.

Semantics implemented (matching what the receiver relies on):

  POST /metrics/job/<anything>   body = text exposition format
      Upsert: every line in the body replaces the stored line with the
      same metric NAME + label set; all other stored metrics are kept.
      (This is the official Pushgateway per-name replacement behavior
      that the receiver's two-lane design depends on: the per-packet
      gauge POST must not clobber queued readings.)
      Lines without a value are ignored. Empty body deletes nothing.
      Responds 200 on success.

  GET /metrics
      Echoes ALL stored lines VERBATIM (values AND timestamps, no
      modification) in text exposition format. Prometheus must scrape
      with honor_timestamps: true so the back-dated timestamps survive.

  DELETE /metrics/job/<anything>
      Clears the store (not used by the receiver, handy for testing).

The job path is ignored — one global store. The receiver only ever
pushes to a single job path, so grouping adds nothing here.

Run:  python3 pushgateway_lite.py [port]   (default 9091)
Only stdlib. Single-threaded per request (ThreadingHTTPServer); the
receiver pushes at most one POST per 2 s, contention is not a concern.
"""

import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# metric key (name + sorted labels) -> raw exposition line (with timestamp)
store: dict[str, str] = {}
lock = threading.Lock()


def parse_key(line: str) -> str | None:
    """Extract a unique key (name + label set) from one exposition line.

    Format: name{labels} value [timestamp]  (labels optional).
    We key on name + labels verbatim (label order is stable per sender),
    which is sufficient for our single-sender use case.
    """
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if "{" in line:
        end = line.find("}")
        if end < 0:
            return None  # malformed
        return line[: end + 1]
    # no labels: key = metric name up to first space
    return line.split(" ", 1)[0]


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        # Compact one-line access log to stderr (docker-friendly).
        #sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))
        pass

    def log_error(self, fmt, *args):
        sys.stderr.write("%s ERROR %s\n" % (self.address_string(), fmt % args))

    # ---- POST: upsert pushed metrics -------------------------------------
    def do_POST(self):
        if not self.path.startswith("/metrics/job/"):
            self.send_error(404, "unknown path")
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            self.send_error(400, "bad content-length")
            return
        body = self.rfile.read(length).decode("utf-8", errors="replace")

        accepted = 0
        with lock:
            for line in body.splitlines():
                key = parse_key(line)
                if key is None:
                    continue
                store[key] = line
                accepted += 1

        # 200 with empty body (official Pushgateway does the same).
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    # ---- GET: echo everything verbatim ------------------------------------
    def do_GET(self):
        if self.path not in ("/metrics", "/metrics/"):
            self.send_error(404, "unknown path")
            return
        with lock:
            # Sorted for deterministic output (Prometheus doesn't care
            # about line order, but tests and humans do).
            body = "".join(line + "\n" for line in sorted(store.values()))
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ---- DELETE: clear the store -------------------------------------------
    def do_DELETE(self):
        if not self.path.startswith("/metrics/job/"):
            self.send_error(404, "unknown path")
            return
        with lock:
            store.clear()
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9091
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"pushgateway_lite listening on :{port} "
          f"(POST /metrics/job/*, GET /metrics)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
