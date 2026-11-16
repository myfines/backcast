"""Isolate Edge's event loop and profile from the API server process."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from services.api.edge_collector import run_edge
from services.api.zhihu import AccessBlocked

try:
    request = json.loads(sys.stdin.read())
    result = run_edge(request["target"], request.get("max_items", 20),
                      request.get("max_pages", 3), request.get("kinds"), request.get("resume", True))
    output = dict(ok=True, data=result)
except AccessBlocked as error:
    output = dict(ok=False, code=error.code, message=str(error), partial=error.partial)
except Exception:
    output = dict(ok=False, code="collector_error", message="Edge采集未完成；已保存的断点保留。")
print(json.dumps(output, ensure_ascii=True))
