#!/usr/bin/env python3
"""本地自测：以 JSON-RPC 客户端身份启动 server.py，依次调一遍三个工具并打印结果。"""
import json
import subprocess
import sys

proc = subprocess.Popen([sys.executable, "server.py"], stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE, text=True, cwd=".")
_next_id = [0]


def call(method, params=None):
    _next_id[0] += 1
    rid = _next_id[0]
    req = {"jsonrpc": "2.0", "id": rid, "method": method}
    if params is not None:
        req["params"] = params
    proc.stdin.write(json.dumps(req, ensure_ascii=False) + "\n")
    proc.stdin.flush()
    resp = json.loads(proc.stdout.readline())
    assert resp["id"] == rid, resp
    return resp.get("result", resp.get("error"))


def tool(name, args):
    res = call("tools/call", {"name": name, "arguments": args})
    return res["content"][0]["text"]


print("== initialize ==")
print(json.dumps(call("initialize", {"protocolVersion": "2024-11-05",
      "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}}), ensure_ascii=False))
proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
proc.stdin.flush()

print("\n== tools/list ==")
for t in call("tools/list")["tools"]:
    print("-", t["name"], ":", t["description"])

print("\n== list_holidays(2026) ==")
print(tool("list_holidays", {"year": 2026}))

print("\n== is_workday: 2026-02-28（应为调休上班日）、2026-10-01（应为国庆） ==")
print(tool("is_workday", {"date": "2026-02-28"}))
print(tool("is_workday", {"date": "2026-10-01"}))

print("\n== best_leave_plan(2026, 5天年假) ==")
print(tool("best_leave_plan", {"year": 2026, "annual_leave_days": 5}))

print("\n== best_leave_plan(2026, 2天年假) ==")
print(tool("best_leave_plan", {"year": 2026, "annual_leave_days": 2}))

print("\n== best_leave_plan(2027, 5天年假) —— 官方未公布，应明确拒绝编造 ==")
print(tool("best_leave_plan", {"year": 2027, "annual_leave_days": 5}))

proc.stdin.close()
proc.wait()
print("\n自测完成，server 退出码：", proc.returncode)
