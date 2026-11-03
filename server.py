#!/usr/bin/env python3
"""拼假助手 LeaveOptimizer —— Grok Bot MCP 插件（纯 Python 标准库，零依赖）。

用法（stdio 传输，MCP JSON-RPC）：
    python3 server.py
Grok Bot / Cursor 接入时把本文件当作 MCP server 启动即可；本地自测用 test_client.py。

三个工具：
  1. list_holidays   —— 列出某年法定节假日与调休上班日
  2. is_workday      —— 判断某天是否上班（含调休上班日）
  3. best_leave_plan —— 给定年假天数，算出最划算的拼假方案
"""
import json
import os
import sys
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "holidays.json"), encoding="utf-8") as f:
    DATA = json.load(f)

WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def parse_date(s):
    y, m, d = s.split("-")
    return date(int(y), int(m), int(d))


def expand(spec):
    """'2026-02-15..2026-02-23' 展开成日期列表；单个日期原样返回。"""
    if ".." in spec:
        a, b = spec.split("..")
        out, d = [], parse_date(a)
        while d <= parse_date(b):
            out.append(d.isoformat())
            d += timedelta(days=1)
        return out
    return [spec]


def year_calendar(year):
    """返回 ({date: 是否休息}, 年份数据)；年份无数据时返回 (None, None)。"""
    info = DATA["years"].get(str(year))
    if info is None:
        return None, None
    days = {}
    d = date(year, 1, 1)
    while d.year == year:
        days[d] = d.weekday() >= 5  # 默认周六日休息
        d += timedelta(days=1)
    for h in info["holidays"]:
        for ds in h["off"]:
            for one in expand(ds):
                days[parse_date(one)] = True
    for ds in info.get("makeup_workdays", []):
        days[parse_date(ds)] = False  # 调休上班日：周末也要上班
    return days, info


def holiday_name_on(days_info, d):
    for h in days_info["holidays"]:
        for ds in h["off"]:
            if d.isoformat() in expand(ds):
                return h["name"]
    return None


def tool_list_holidays(year):
    days, info = year_calendar(year)
    if info is None:
        return {"error": "暂无该年数据",
                "说明": f"{year} 年官方放假安排尚未公布（国务院办公厅通常在上一年 11 月发布），"
                        "本插件不编造推算日期；公布后在 holidays.json 里补一年数据即可。"}
    out = {"year": year, "source": DATA["source"], "holidays": [], "makeup_workdays": info.get("makeup_workdays", [])}
    for h in info["holidays"]:
        spans = []
        for ds in h["off"]:
            dates = expand(ds)
            spans.append(f"{dates[0]} 至 {dates[-1]}（{len(dates)} 天）" if len(dates) > 1 else dates[0])
        out["holidays"].append({"name": h["name"], "off": spans})
    return out


def tool_is_workday(date_str):
    d = parse_date(date_str)
    days, info = year_calendar(d.year)
    if days is None:
        return {"error": "暂无该年数据", "说明": f"{d.year} 年官方放假安排尚未公布，本插件不编造推算日期。"}
    off = days[d]
    if holiday_name_on(info, d):
        reason = f"法定节假日（{holiday_name_on(info, d)}）"
    elif d.isoformat() in info.get("makeup_workdays", []):
        reason = "调休上班日"
    elif d.weekday() >= 5:
        reason = "周末"
    else:
        reason = "工作日"
    return {"date": date_str, "weekday": WEEKDAY_CN[d.weekday()], "is_workday": not off, "reason": reason}


def tool_best_leave_plan(year, budget, max_plans=3):
    days, info = year_calendar(year)
    if days is None:
        return {"error": "暂无该年数据",
                "说明": f"{year} 年官方放假安排尚未公布，本插件不编造推算日期；"
                        "公布后在 holidays.json 里补一年数据即可，不用改代码。"}
    ordered = sorted(days)
    is_off = [days[d] for d in ordered]
    pref = [0]
    for off in is_off:
        pref.append(pref[-1] + (0 if off else 1))  # pref[k] = 前 k 天里的工作日数
    n = len(ordered)
    cands = []
    for i in range(n):
        if not is_off[i]:
            continue
        for j in range(i + 1, n):
            if not is_off[j]:
                continue
            leave = pref[j + 1] - pref[i]
            if leave == 0 or leave > budget:
                continue
            # 只保留“极大连休”：窗口两端之外必须是工作日，否则会被更长的窗口支配
            if i > 0 and is_off[i - 1]:
                continue
            if j < n - 1 and is_off[j + 1]:
                continue
            cands.append({"start": ordered[i].isoformat(), "end": ordered[j].isoformat(),
                          "total_days": j - i + 1, "leave_days": leave})
    if not cands:
        return {"year": year, "budget": budget, "plans": [], "说明": "按给定年假天数拼不出比法定假期更长的连休。"}
    for c in cands:
        start, end = parse_date(c["start"]), parse_date(c["end"])
        c["leave_dates"] = [d.isoformat() for d in ordered
                            if start <= d <= end and not days[d]]
        names = sorted({holiday_name_on(info, d) for d in ordered
                        if start <= d <= end and holiday_name_on(info, d)})
        c["covers_holidays"] = names
    by_length = sorted(cands, key=lambda c: (-c["total_days"], c["leave_days"]))
    best_ratio = max(cands, key=lambda c: (c["total_days"] / c["leave_days"], c["total_days"]))
    top = by_length[:max_plans]
    if all(p["start"] != best_ratio["start"] or p["end"] != best_ratio["end"] for p in top):
        top.append(best_ratio)
    return {"year": year, "budget": budget,
            "plans": [{"连休": f"{p['start']} 至 {p['end']}", "连休天数": p["total_days"],
                       "请假日期": p["leave_dates"], "消耗年假": p["leave_days"],
                       "含法定假": p["covers_holidays"]} for p in top],
            "最划算（天数/年假比最高）": f"{best_ratio['start']} 至 {best_ratio['end']}，"
            f"{best_ratio['total_days']} 天连休只用 {best_ratio['leave_days']} 天年假"}


TOOLS = [
    {"name": "list_holidays", "description": "列出某年法定节假日与调休上班日（仅官方已公布年份，未公布年份明确告知，不编造）。",
     "inputSchema": {"type": "object", "properties": {"year": {"type": "integer"}}, "required": ["year"]}},
    {"name": "is_workday", "description": "判断某天是否上班，区分法定假日、调休上班日、周末、工作日。",
     "inputSchema": {"type": "object", "properties": {"date": {"type": "string", "description": "YYYY-MM-DD"}}, "required": ["date"]}},
    {"name": "best_leave_plan", "description": "给定年假天数，算出最划算的拼假方案（连休区间、请假日期、消耗年假天数）。",
     "inputSchema": {"type": "object", "properties": {
         "year": {"type": "integer"}, "annual_leave_days": {"type": "integer"},
         "max_plans": {"type": "integer", "default": 3}}, "required": ["year", "annual_leave_days"]}},
]


def dispatch(name, args):
    if name == "list_holidays":
        return tool_list_holidays(int(args["year"]))
    if name == "is_workday":
        return tool_is_workday(args["date"])
    if name == "best_leave_plan":
        return tool_best_leave_plan(int(args["year"]), int(args["annual_leave_days"]),
                                    int(args.get("max_plans", 3)))
    raise ValueError(f"未知工具 {name}")


def send(rid, result):
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": rid, "result": result}, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def send_error(rid, code, message):
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": rid,
                                 "error": {"code": code, "message": message}}, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        method = req.get("method", "")
        rid = req.get("id")
        if method == "initialize":
            send(rid, {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                       "serverInfo": {"name": "leave-optimizer", "version": "0.1.0"}})
        elif method == "ping":
            send(rid, {})
        elif method == "tools/list":
            send(rid, {"tools": TOOLS})
        elif method == "tools/call":
            params = req.get("params", {})
            try:
                result = dispatch(params["name"], params.get("arguments", {}))
                send(rid, {"content": [{"type": "text",
                                        "text": json.dumps(result, ensure_ascii=False, indent=2)}]})
            except Exception as e:  # noqa: BLE001 —— 工具异常转为 MCP 错误文本，不炸掉服务
                send(rid, {"content": [{"type": "text", "text": f"出错：{e}"}], "isError": True})
        elif method.startswith("notifications/"):
            continue
        else:
            send_error(rid, -32601, f"未知方法 {method}")


if __name__ == "__main__":
    main()
