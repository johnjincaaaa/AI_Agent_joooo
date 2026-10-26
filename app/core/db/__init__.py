"""
数据库层聚合导出 —— 兼容旧 `from app.core.db import *`。

模型与连接来自 models.py，迁移/seed 来自 seed.py。
"""
from app.core.db.models import *          # noqa: F401,F403
from app.core.db.models import get_db, SessionLocal, Base, engine
from app.core.db.seed import PROMO_CONFIG_DEFAULTS, init_db, seed_promo_config

__all__ = [
    "engine", "SessionLocal", "Base", "get_db",
    "User", "ChatSession", "JobProfile",
    "ReferralEvent", "WithdrawRequest", "PromoConfig",
    "PageVisit", "DownloadClick", "CheckInRecord",
    "PROMO_CONFIG_DEFAULTS", "init_db", "seed_promo_config",
]
