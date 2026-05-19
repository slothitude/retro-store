"""Shared httpx client, headers, error handling for scrapers."""
import httpx
import random
from typing import Optional

DEFAULT_TIMEOUT = 30.0

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
]


def get_headers() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-AU,en;q=0.9,en-US;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }


def get_client(timeout: float = DEFAULT_TIMEOUT, follow_redirects: bool = True) -> httpx.Client:
    return httpx.Client(
        headers=get_headers(),
        timeout=timeout,
        follow_redirects=follow_redirects,
    )


def fetch_html(url: str, timeout: float = DEFAULT_TIMEOUT) -> str:
    """Fetch a URL and return HTML text. Raises on HTTP errors."""
    with get_client(timeout=timeout) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.text


def fetch_html_fallback(url: str, timeout: float = DEFAULT_TIMEOUT) -> str:
    """Try fetching, return error string on failure instead of raising."""
    try:
        return fetch_html(url, timeout)
    except Exception as e:
        return f"FETCH_ERROR: {e}"


def fetch_via_web_reader(url: str) -> str:
    """Fetch page content via the web-reader MCP server (Playwright on Lappy:8003).

    Uses MCP-over-SSE protocol: connect to SSE stream, get session URL,
    POST JSON-RPC tool calls, read response from stream.
    The web-reader uses Playwright with anti-detection, so it handles JS-heavy sites.
    """
    import urllib.request
    import json
    import threading
    import time

    host = "192.168.0.33"
    port = 8003
    timeout = 60

    results = []
    session_url = [""]
    ready = threading.Event()

    def sse_reader():
        try:
            req = urllib.request.Request(f"http://{host}:{port}/sse")
            resp = urllib.request.urlopen(req, timeout=timeout)
            event_type = [""]
            for line in resp:
                line = line.decode().strip()
                if line.startswith("event:"):
                    event_type[0] = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    data = line.split("data:", 1)[1].strip()
                    if "/messages" in data and not session_url[0]:
                        session_url[0] = data
                        ready.set()
                    elif event_type[0] == "message":
                        try:
                            msg = json.loads(data)
                            if "result" in msg or "error" in msg:
                                results.append(msg)
                                # Wait for the tool call response (id=2), not the init response (id=1)
                                if msg.get("id") == 2:
                                    return
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            results.append({"error": str(e)})
            ready.set()

    def _post(url, payload):
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data,
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5)

    t = threading.Thread(target=sse_reader, daemon=True)
    t.start()

    if not ready.wait(timeout=10):
        return "FETCH_ERROR: web-reader SSE connection timed out"

    if not session_url[0]:
        return "FETCH_ERROR: web-reader did not provide session URL"

    post_url = f"http://{host}:{port}{session_url[0]}"

    try:
        # Initialize MCP session
        _post(post_url, {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "retro-tools", "version": "1.0"}
            }
        })
        time.sleep(0.3)

        # Call read_url tool
        _post(post_url, {
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {
                "name": "read_url",
                "arguments": {"url": url}
            }
        })

        t.join(timeout=timeout)

        if not results:
            return "FETCH_ERROR: web-reader returned no response"

        result = results[-1]
        if "error" in result:
            return f"FETCH_ERROR: web-reader error: {result['error']}"

        # Extract content from MCP tool result
        content = result.get("result", {}).get("content", [])
        if content:
            text = content[0].get("text", "")
            return text

        return "FETCH_ERROR: web-reader returned empty content"

    except Exception as e:
        return f"FETCH_ERROR: web-reader call failed: {e}"


def fetch_html_smart(url: str, timeout: float = DEFAULT_TIMEOUT) -> str:
    """Try direct fetch first, fall back to web-reader MCP on 403/block."""
    html = fetch_html_fallback(url, timeout)
    if html.startswith("FETCH_ERROR:"):
        if "403" in html or "401" in html or "Captcha" in html:
            # Try web-reader
            wr_html = fetch_via_web_reader(url)
            if not wr_html.startswith("FETCH_ERROR:"):
                return wr_html
        return html
    return html


def _call_web_reader_tool(tool_name: str, arguments: dict, timeout: int = 60) -> str:
    """Call any web-reader MCP tool and return the text result.

    Shared MCP-over-SSE client for search/read operations.
    """
    import urllib.request
    import json
    import threading
    import time

    host = "192.168.0.33"
    port = 8003

    results = []
    session_url = [""]
    ready = threading.Event()

    def sse_reader():
        try:
            req = urllib.request.Request(f"http://{host}:{port}/sse")
            resp = urllib.request.urlopen(req, timeout=timeout)
            event_type = [""]
            for line in resp:
                line = line.decode().strip()
                if line.startswith("event:"):
                    event_type[0] = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    data = line.split("data:", 1)[1].strip()
                    if "/messages" in data and not session_url[0]:
                        session_url[0] = data
                        ready.set()
                    elif event_type[0] == "message":
                        try:
                            msg = json.loads(data)
                            if "result" in msg or "error" in msg:
                                results.append(msg)
                                if msg.get("id") == 2:
                                    return
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            results.append({"error": str(e)})
            ready.set()

    def _post(url, payload):
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data,
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5)

    t = threading.Thread(target=sse_reader, daemon=True)
    t.start()

    if not ready.wait(timeout=10):
        return ""

    if not session_url[0]:
        return ""

    post_url = f"http://{host}:{port}{session_url[0]}"

    try:
        _post(post_url, {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "retro-tools", "version": "1.0"}
            }
        })
        time.sleep(0.3)

        _post(post_url, {
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments}
        })

        t.join(timeout=timeout)

        if not results:
            return ""

        result = results[-1]
        content = result.get("result", {}).get("content", [])
        if content:
            return content[0].get("text", "")
        return ""

    except Exception:
        return ""


def web_search(query: str, num_results: int = 10) -> str:
    """Search via SearXNG through web-reader MCP. Returns markdown with titles, URLs, snippets."""
    return _call_web_reader_tool("web_search", {
        "query": query,
        "num_results": num_results,
    })


def web_search_and_read(query: str, num_results: int = 3) -> str:
    """Search SearXNG then read top results. Returns combined markdown content."""
    return _call_web_reader_tool("search_and_read", {
        "query": query,
        "num_results": num_results,
    }, timeout=90)
