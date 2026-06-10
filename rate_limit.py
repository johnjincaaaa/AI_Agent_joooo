from collections import defaultdict
from time import time

from fastapi import HTTPException, Request, status

import config

_ip_requests: dict[str, list[float]] = defaultdict(list)


def check_anonymous_rate_limit(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    now = time()
    window = config.ANONYMOUS_RATE_LIMIT_WINDOW
    max_requests = config.ANONYMOUS_RATE_LIMIT_MAX

    timestamps = [t for t in _ip_requests[client_ip] if now - t < window]
    if len(timestamps) >= max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": 429,
                "msg": "未登录用户免费体验次数已用完，请注册或登录后继续使用",
            },
        )
    timestamps.append(now)
    _ip_requests[client_ip] = timestamps
