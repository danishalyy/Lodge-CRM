"""Server-only background principal. No HTTP header or model argument can create it."""

from starlette.requests import Request


class ReportRequest(Request):
    def __init__(self, anchor_id, actor_id, run_id, lease_token):
        super().__init__(
            {
                "type": "http",
                "method": "POST",
                "path": "/internal/ai/reports",
                "headers": [],
                "query_string": b"",
                "scheme": "http",
                "server": ("worker", 80),
                "client": ("worker", 0),
            }
        )
        self.anchor_id = anchor_id
        self.actor_id = actor_id
        self.run_id = run_id
        self.lease_token = lease_token


class ReportReadRequest(ReportRequest):
    """Internal delivery authorization for an already completed private report."""

    def __init__(self, anchor_id, actor_id, run_id):
        super().__init__(anchor_id, actor_id, run_id, None)
