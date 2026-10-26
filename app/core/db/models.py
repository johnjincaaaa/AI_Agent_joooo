"""
数据库模型层 —— 从 sqlOrm.py 拆出（原文件命名不规范 + 职责过重）。

本模块只放：
  - engine / SessionLocal / Base 连接基础设施
  - ORM 模型（User / ChatSession / JobProfile / 推广与埋点等）
  - get_db 依赖

表结构迁移与配置 seed 见：
  - app/core/db/seed.py（PROMO_CONFIG_DEFAULTS、补列、seed）
"""
from datetime import datetime

from sqlalchemy import (
    create_engine, Column, Integer, String, Text, DateTime, ForeignKey,
    JSON, BIGINT, Float, UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from app.config import SQLALCHEMY_DATABASE_URL

# SQLite 需要关闭线程检查（FastAPI 多线程访问同一连接）；其它数据库正常连接。
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
else:
    engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ======================
# 用户表
# ======================
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)  # 账号唯一
    password = Column(String(255), nullable=False)  # bcrypt 哈希
    phone = Column(String(20), unique=True, index=True, nullable=True)     # 手机号（手机号注册）
    nickname = Column(String(50), nullable=True)                             # 用户昵称（可修改）
    register_time = Column(DateTime, default=datetime.now)

    # ===== 推广拉新相关 =====
    referral_code = Column(String(16), unique=True, index=True, nullable=True)  # 专属推广码（首次取链接时生成）
    balance_usd = Column(Float, default=0.0, nullable=False)                    # 推广余额（不含待审核提现）
    referral_count = Column(Integer, default=0, nullable=False)                 # 累计有效推广人数
    membership_expire_at = Column(DateTime, nullable=True)                      # 会员到期（永久=远期日期，仅记录）

    sessions = relationship("ChatSession", back_populates="user", cascade="all, delete")  # 双向绑定，两边能互相找到对方session.user


# ======================
# 会话表
# ======================
class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    session_name = Column(String(100), nullable=False)  # 加上会话名字段
    session_time = Column(BIGINT, nullable=False, comment="创建时间（ms时间戳）")
    messages = Column(JSON)  # 对话JSON
    # 👇 核心：user_id + session_time 联合唯一索引（同一会话不重复）
    __table_args__ = (
        UniqueConstraint("user_id", "session_time", name="uq_user_session_time"),
    )
    user = relationship("User", back_populates="sessions")


class JobProfile(Base):
    __tablename__ = "job_profiles"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    profile_data = Column(JSON, default=dict)
    resume_content = Column(Text, nullable=True)
    template_id = Column(String(50), default="classic")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    user = relationship("User")


# ======================
# 有效推广记录表
# ======================
class ReferralEvent(Base):
    __tablename__ = "referral_events"

    id = Column(Integer, primary_key=True, index=True)
    referrer_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)  # 推广人
    # sha256(fingerprint|ip)，全局唯一 → 同一访客只计一次
    visitor_key = Column(String(64), unique=True, index=True, nullable=False)
    visitor_ip = Column(String(64), nullable=True)
    visitor_fingerprint = Column(String(128), nullable=True)
    reward_amount = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime, default=datetime.now)


# ======================
# 提现申请表
# ======================
class WithdrawRequest(Base):
    __tablename__ = "withdraw_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    amount = Column(Float, nullable=False)
    paypal_email = Column(String(120), nullable=False)
    status = Column(String(20), default="pending", nullable=False)  # pending / paid / rejected
    created_at = Column(DateTime, default=datetime.now)
    reviewed_at = Column(DateTime, nullable=True)


# ======================
# 推广可视化配置表（key-value）
# ======================
class PromoConfig(Base):
    __tablename__ = "promo_config"

    key = Column(String(64), primary_key=True)
    value = Column(Text, nullable=True)


# ======================
# 页面访问埋点（算 PV / UV）
# ======================
class PageVisit(Base):
    __tablename__ = "page_visits"

    id = Column(Integer, primary_key=True, index=True)
    visitor_key = Column(String(64), index=True, nullable=False)  # sha256(ua|ip)，算 UV 去重用
    visitor_ip = Column(String(64), nullable=True)
    ref_code = Column(String(16), nullable=True, index=True)      # 带 ?ref= 进来的推广码（区分自然/推广流量）
    path = Column(String(120), nullable=True)                     # 访问路径，默认 /chat
    created_at = Column(DateTime, default=datetime.now, index=True)


# ======================
# 下载按钮点击埋点（总点击量，可重复；与去重发奖的 ReferralEvent 不同）
# ======================
class DownloadClick(Base):
    __tablename__ = "download_clicks"

    id = Column(Integer, primary_key=True, index=True)
    visitor_key = Column(String(64), index=True, nullable=True)
    visitor_ip = Column(String(64), nullable=True)
    ref_code = Column(String(16), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.now, index=True)


# ======================
# 签到记录表（用户留存）
# ======================
class CheckInRecord(Base):
    __tablename__ = "checkin_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    checkin_date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    reward_amount = Column(Float, default=0.0, nullable=False)     # 本次签到奖励金额（元）
    reward_days = Column(Integer, default=0, nullable=False)        # 本次签到奖励会员天数
    streak_days = Column(Integer, default=1, nullable=False)        # 连续签到天数
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        UniqueConstraint("user_id", "checkin_date", name="uq_user_checkin_date"),
    )


# DB 依赖：给接口【自动提供数据库连接】，用完【自动关闭】
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
