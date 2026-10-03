"""Long-lived line-delimited JSON worker used by the Express API."""

from __future__ import annotations

import json
import sys
import traceback
from typing import Any

from .pipeline import analyze_image


def main() -> None:
    for line in sys.stdin:
        request: dict[str, Any] = {}
        try:
            request: dict[str, Any] = json.loads(line)
            result = analyze_image(
                request["imageBase64"],
                request["camera"],
                float(request.get("confidence", 0.3)),
            )
            response = {"requestId": request["requestId"], "ok": True, "result": result}
        except Exception as exc:
            traceback.print_exc(file=sys.stderr)
            response = {
                "requestId": request.get("requestId"),
                "ok": False,
                "error": str(exc),
            }
        sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()