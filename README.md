# 拼假助手 LeaveOptimizer

中国法定节假日与拼假计算 MCP 插件。纯 Python 标准库，零依赖，stdio 传输。

## 工具

| 工具 | 作用 |
|------|------|
| `list_holidays` | 列出某年法定假日与调休上班日 |
| `is_workday` | 判断某天是否上班（法定假 / 调休上班 / 周末 / 工作日） |
| `best_leave_plan` | 给定年假天数，算出最划算的拼假方案 |

数据只用国务院办公厅已公布年份；未公布年份明确返回「未公布」，不编造。

## 本地运行

```bash
python3 test_client.py   # 自测三个工具
python3 server.py        # 作为 MCP server（stdio）
```

## MCP 接入示例

```json
{
  "mcpServers": {
    "leave-optimizer": {
      "command": "python3",
      "args": ["server.py"],
      "cwd": "/path/to/leave-optimizer"
    }
  }
}
```

## 数据更新

官方新一年放假通知发布后，在 `holidays.json` 的 `years` 里补一年即可，不用改代码。

## 许可

MIT
