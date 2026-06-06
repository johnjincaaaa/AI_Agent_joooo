from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey,JSON,BIGINT,UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime
from config import SQLALCHEMY_DATABASE_URL
# MySQL 连接

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
    password = Column(String(255), nullable=False)  # 密码明文
    register_time = Column(DateTime, default=datetime.now)

    sessions = relationship("ChatSession", back_populates="user", cascade="all, delete") # 意思：双向绑定，两边能互相找到对方session.user

# ======================
# 会话表
# ======================
class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    session_name = Column(String(100),nullable=False)  # 加上会话名字段
    session_time = Column(BIGINT,nullable=False,comment="创建时间（ms时间戳）")
    messages = Column(JSON)  # 对话JSON
    # 👇 核心：user_id + session_time 联合唯一索引（同一会话不重复）
    __table_args__ = (
        UniqueConstraint("user_id", "session_time", name="uq_user_session_time"),
    )
    user = relationship("User", back_populates="sessions")

# 自动创建所有表（不用写SQL）
Base.metadata.create_all(bind=engine)

# DB 依赖  给你的接口【自动提供数据库连接】，用完【自动关闭】
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

if __name__ == '__main__':
    with SessionLocal() as session:
        a = session.query(ChatSession).filter(
            ChatSession.user_id==1
        ).all()
        for i in a:
            print(i.session_name)