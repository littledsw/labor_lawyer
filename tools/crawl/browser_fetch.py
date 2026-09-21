"""用真实 Chromium 渲染 JS 页面并取回内容（headless + CDP，无需任何手动配置）。

用途：政务网站的检索页、数据表格等由 JS 动态渲染，纯 HTTP 抓取只能拿到空壳。
本模块自带一个 headless Chrome 实例，等页面加载与 JS 执行完成后再取 DOM。

命令行用法：
    python browser_fetch.py <url> [--wait 6] [--json out.json]

Python 用法：
    from browser_fetch import render
    page = render("https://example.gov.cn/search?q=x", wait=6)
    page["title"], page["text"], page["links"], page["html"]

退出码：0 成功；2 页面无法加载；3 浏览器无法启动。
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import signal
import subprocess
import sys
import time
import urllib.request

import websocket  # websocket-client

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    shutil.which("google-chrome") or "",
    shutil.which("chromium") or "",
]
PROFILE = pathlib.Path("/tmp/labor_lawyer_browser_profile")


def _chrome_path() -> str:
    for c in CHROME_CANDIDATES:
        if c and pathlib.Path(c).exists():
            return c
    raise RuntimeError("未找到 Chrome/Chromium 可执行文件")


class Browser:
    """最小可用的 CDP 客户端：启动 → 导航 → 取 DOM → 关闭。"""

    def __init__(self, port: int = 9333, timeout: float = 40.0) -> None:
        self.port = port
        self.timeout = timeout
        self.proc: subprocess.Popen | None = None
        self.ws = None
        self._msg_id = 0

    # ---------------------------------------------------------- 生命周期
    def start(self) -> None:
        PROFILE.mkdir(parents=True, exist_ok=True)
        self.proc = subprocess.Popen(
            [_chrome_path(), "--headless=new", "--disable-gpu", "--no-sandbox",
             "--no-first-run", "--no-default-browser-check", "--disable-extensions",
             "--disable-background-networking", "--mute-audio",
             f"--remote-debugging-port={self.port}", f"--user-data-dir={PROFILE}",
             "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
        )
        deadline = time.time() + self.timeout
        target_ws = None
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json/list", timeout=3) as r:
                    targets = json.load(r)
                page = next((t for t in targets if t.get("type") == "page"), None)
                if page:
                    target_ws = page["webSocketDebuggerUrl"]
                    break
            except Exception:
                time.sleep(0.4)
        if not target_ws:
            raise RuntimeError("headless Chrome 未就绪（CDP 端口无响应）")
        self.ws = websocket.create_connection(target_ws, timeout=self.timeout,
                                              suppress_origin=True)
        self.call("Page.enable")
        self.call("Runtime.enable")

    def close(self) -> None:
        try:
            if self.ws:
                self.ws.close()
        except Exception:
            pass
        if self.proc:
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
            except Exception:
                self.proc.terminate()
            try:
                self.proc.wait(timeout=8)
            except Exception:
                pass

    # ---------------------------------------------------------- CDP 原语
    def call(self, method: str, **params):
        self._msg_id += 1
        mid = self._msg_id
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"{method} 失败：{msg['error']}")
                return msg.get("result", {})
        raise TimeoutError(method)

    def evaluate(self, expr: str):
        res = self.call("Runtime.evaluate", expression=expr, returnByValue=True,
                        awaitPromise=True)
        return res.get("result", {}).get("value")

    # ---------------------------------------------------------- 高层操作
    def render(self, url: str, wait: float = 6.0) -> dict:
        self.call("Page.navigate", url=url)
        time.sleep(wait)                      # 给 JS 渲染与 XHR 留时间
        for _ in range(6):                    # 等 document.readyState 完整
            if self.evaluate("document.readyState") == "complete":
                break
            time.sleep(1)
        payload = self.evaluate("""(() => ({
            title: document.title,
            text: document.body ? document.body.innerText : '',
            html: document.documentElement ? document.documentElement.outerHTML : '',
            links: Array.from(document.querySelectorAll('a[href]')).map(a => ({
                label: (a.innerText || a.textContent || '').trim().slice(0, 120),
                href: a.href, raw: a.getAttribute('href') || ''})),
            forms: Array.from(document.querySelectorAll('input,select')).map(el => ({
                tag: el.tagName, name: el.name, id: el.id, type: el.type || ''}))
        }))()""")
        payload = payload or {}
        payload["url"] = self.evaluate("location.href")
        return payload


def render(url: str, wait: float = 6.0, keep_html: bool = True) -> dict:
    b = Browser()
    try:
        b.start()
        page = b.render(url, wait=wait)
    finally:
        b.close()
    if not keep_html:
        page.pop("html", None)
    return page


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--wait", type=float, default=6.0, help="导航后额外等待秒数（等 JS/XHR）")
    ap.add_argument("--json", help="把结果写入该 JSON 文件")
    ap.add_argument("--grep", help="只打印标签或链接里含该关键词的条目")
    args = ap.parse_args()

    try:
        page = render(args.url, wait=args.wait)
    except RuntimeError as exc:
        print(f"[FAIL] {exc}")
        return 3
    if not page.get("text") and not page.get("html"):
        print("[FAIL] 页面无内容（可能加载失败）")
        return 2

    print(f"标题: {page['title']}")
    print(f"URL : {page['url']}")
    print(f"正文 {len(page.get('text') or '')} 字符 / HTML {len(page.get('html') or '')} 字符 "
          f"/ 链接 {len(page.get('links') or [])}")
    links = page.get("links") or []
    if args.grep:
        links = [l for l in links if args.grep in (l["label"] or "") or args.grep in (l["href"] or "")]
    print("---- 链接 ----")
    for l in links[:60]:
        print(f"  {l['label'][:70]!r} → {l['href'][:130]}")
    if not args.grep:
        print("---- 正文（前 1500 字符）----")
        print((page.get("text") or "")[:1500])
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(page, ensure_ascii=False, indent=2),
                                           encoding="utf-8")
        print(f"已写入 {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
