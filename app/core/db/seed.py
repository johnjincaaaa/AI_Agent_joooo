"""
数据库迁移与 seed —— 从 sqlOrm.py 拆出。

职责：
  - PROMO_CONFIG_DEFAULTS（推广/签到配置默认值）
  - init_db()：create_all + 给旧 users 表补列 + 补齐配置默认值
"""
from sqlalchemy import inspect, text

from app.core.db.models import engine, Base, SessionLocal, PromoConfig


# 配置默认值（seed 时仅补齐缺失的 key，不覆盖已有值）
PROMO_CONFIG_DEFAULTS = {
    # 分享弹窗介绍文案
    "popup_intro_zh": "把你的专属链接分享给好友，好友进入网页并点击下载APP，你即可获得奖励！",
    "popup_intro_en": "Share your personal link. When a friend opens the page and taps Download App, you earn rewards!",
    # 输入框推广文案
    "input_promo_zh": "邀请好友下载APP，每人奖励3元，满5人再得20元+永久会员！",
    "input_promo_en": "Invite friends to download the App: ¥3 each, plus ¥20 + lifetime membership at 5 invites!",
    # 奖励规则
    "reward_base": "3",
    "tier_threshold": "5",
    "tier_bonus": "20",
    "tier_membership_days": "-1",   # -1 表示永久
    # ===== 风控规则 =====
    "risk_ip_daily_limit": "10",           # 同一 IP 每日最多计多少次有效推广（防刷）
    "risk_withdraw_min": "10",             # 最低提现门槛（元）
    "risk_reward_freeze_hours": "24",      # 推广奖励冻结时长（小时），冻结期间不可提现
    "risk_new_user_withdraw_hours": "48",  # 新注册用户多少小时内不可提现
    # ===== 签到奖励（用户留存） =====
    "checkin_enabled": "1",                 # 签到功能开关
    "checkin_reward_amount": "0.2",         # 每日签到基础奖励（元）
    "checkin_reward_days": "1",             # 每日签到赠送会员天数
    "checkin_streak_bonus_3": "0.5",        # 连续签到 3 天额外奖励
    "checkin_streak_bonus_7": "2",          # 连续签到 7 天额外奖励
    "checkin_streak_bonus_30": "10",        # 连续签到 30 天额外奖励
    # 开关
    "promo_enabled": "1",
    "input_promo_enabled": "1",
    # 推广链接缓存有效期（天）
    "link_cache_days": "30",
    # 专属链接跳转的网页地址（前端拼 ?ref=）
    "landing_base_url": "http://gtp88.top/chat",
}


def _ensure_user_columns():
    """SQLite/MySQL 下 create_all 不会给已存在的 users 表补列，这里幂等补齐推广字段。"""
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("users")}
    # 列名 -> 建列 DDL（SQLite 与 MySQL 通用的简单类型）
    add_cols = {
        "referral_code": "VARCHAR(16)",
        "balance_usd": "FLOAT NOT NULL DEFAULT 0",
        "referral_count": "INTEGER NOT NULL DEFAULT 0",
        "membership_expire_at": "DATETIME NULL",
        "phone": "VARCHAR(20)",
        "nickname": "VARCHAR(50)",
    }
    with engine.begin() as conn:
        for col, ddl in add_cols.items():
            if col not in existing:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {ddl}"))


def seed_promo_config():
    """补齐缺失的推广配置默认值（不覆盖已有值）。"""
    db = SessionLocal()
    try:
        existing = {row.key for row in db.query(PromoConfig.key).all()}
        for key, value in PROMO_CONFIG_DEFAULTS.items():
            if key not in existing:
                db.add(PromoConfig(key=key, value=value))
        db.commit()
    finally:
        db.close()


def init_db():
    """创建所有表 + 给旧库补列 + 补齐配置默认值。"""
    Base.metadata.create_all(bind=engine)
    _ensure_user_columns()
    seed_promo_config()
