"""
主动发消息 —— 主对话 AI 定时主动开启话题。

设计：
  - 后台线程定时扫描「有主对话会话的用户」
  - 若用户超过阈值（默认 5 分钟）无互动，生成一句主动关怀消息
  - 通过桌宠 SSE 广播（事件总线）+ 写入主对话历史

只作用于主对话（chat_type=main），新建会话不主动发。
"""
import logging
import threading
import time
from datetime import datetime, timedelta

from app.core.db import SessionLocal, ChatSession, Message
from app.core.db.models import User
from app.plugins import get_registry

logger = logging.getLogger(__name__)

# 主动发消息配置
ACTIVE_CHECK_INTERVAL_SEC = 60       # 每 60 秒检查一次
INACTIVE_THRESHOLD_MIN = 5           # 超过 5 分钟无互动才主动发
MIN_GAP_BETWEEN_ACTIVE_MIN = 10      # 两次主动发消息至少间隔 10 分钟（防刷屏）
MAX_UNANSWERED_ACTIVE = 3            # 连续主动发 3 次都没收到用户回应就停止，直到用户发消息重置

# 主动发消息的话术池（大肥鱼人设：平等朋友、傲娇散漫、偶尔颜文字）
ACTIVE_MESSAGES = [
    "人呢，不会又去忙了吧 (｡･ω･｡)",
    "喂，出来聊两句呗，我一个人待着怪无聊的",
    "你是不是把我给忘了… (*≧ω≦)",
    "刚刷到个好玩的东西，想不想听",
    "摸鱼中，你也来摸会儿鱼呗",
    "今天有啥新鲜事没，说说",
    "对了，之前那事后来咋样了",
    "发呆.jpg 已经快长蘑菇了",
]

# 记录每个用户最后一次主动发消息的时间（内存，重启清空——仅用于 MIN_GAP 防刷屏，
# 重启后最多多等一个 MIN_GAP 周期，不影响正确性）
_last_active_sent: dict = {}


def reset_unanswered_count(user_id: int) -> None:
    """用户发送消息时调用：清零连续未回应计数，恢复主动发消息。

    注意：只由「用户发消息」触发；宠物回应用户的那句（AI 回复）不算，
    也不该重置这里的计数。
    """
    if not user_id:
        return
    try:
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if user and user.unanswered_active_count != 0:
                user.unanswered_active_count = 0
                db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.warning("[active] 重置未回应计数失败 user=%s: %s", user_id, e)


def _generate_active_message(user_id: int, llm_config=None) -> str | None:
    """生成主动消息。简单起见先用话术池随机；后续可接 LLM 生成。"""
    import random
    return random.choice(ACTIVE_MESSAGES)


def _check_and_activate():
    """扫描主对话用户，对超时无互动的用户主动发消息。

    连续未回应计数持久化在 User.unanswered_active_count（重启不清零）。
    """
    db = SessionLocal()
    try:
        # 找所有有主对话会话的用户（按 user 去重，避免多 session 重复计数）
        main_rows = (
            db.query(ChatSession.user_id)
            .filter(ChatSession.chat_type == "main", ChatSession.user_id.isnot(None))
            .distinct()
            .all()
        )
        if not main_rows:
            return

        now = datetime.now()
        for (user_id,) in main_rows:
            if not user_id:
                continue

            # 找该用户主对话「最后一条用户消息」时间（以用户真实互动为准，
            # AI 主动发消息不算，避免主动消息把 last_time 刷新导致误判）
            last_user_msg = (
                db.query(Message)
                .join(ChatSession, Message.session_id == ChatSession.id)
                .filter(
                    ChatSession.chat_type == "main",
                    ChatSession.user_id == user_id,
                    Message.role == "user",
                )
                .order_by(Message.id.desc())
                .first()
            )
            last_time = last_user_msg.created_at if last_user_msg and last_user_msg.created_at else None

            # 无用户消息历史则跳过（主对话还没开始聊）
            if not last_time:
                continue

            # 超过阈值无互动
            inactive = (now - last_time) > timedelta(minutes=INACTIVE_THRESHOLD_MIN)
            if not inactive:
                continue

            # 连续主动发 3 次都没收到用户回应 → 停止，直到用户发消息重置
            user = db.query(User).filter(User.id == user_id).first()
            unanswered = user.unanswered_active_count if user else 0
            if unanswered >= MAX_UNANSWERED_ACTIVE:
                continue

            # 人设参数开关：主动发消息关闭则跳过
            try:
                from app.core import characters as charsvc
                settings = charsvc.get_user_settings(user_id)
                if not settings.get("active_message", True):
                    continue
            except Exception:
                pass

            # 防刷屏：两次主动发消息至少间隔 MIN_GAP
            last_sent = _last_active_sent.get(user_id, 0)
            if time.time() - last_sent < MIN_GAP_BETWEEN_ACTIVE_MIN * 60:
                continue

            # 生成主动消息
            text = _generate_active_message(user_id)
            if not text:
                continue

            # 找该用户的主对话 session（用于写入历史）
            session = (
                db.query(ChatSession)
                .filter(ChatSession.chat_type == "main", ChatSession.user_id == user_id)
                .order_by(ChatSession.id.asc())
                .first()
            )
            if not session:
                continue

            # 写入主对话历史（作为 AI 消息）
            db.add(Message(
                session_id=session.id,
                user_id=user_id,
                role="ai",
                content=text,
                reactions={},
            ))
            # 记录发送时间 + 连续未回应计数 +1（持久化）
            _last_active_sent[user_id] = time.time()
            if user:
                user.unanswered_active_count = (user.unanswered_active_count or 0) + 1
            db.commit()

            # 广播给桌宠前端（气泡显示）
            try:
                registry = get_registry()
                registry.broadcast("dsh-pet", {"t": "say-reply", "text": text})
                registry.broadcast("dsh-pet", {"t": "active-message", "text": text})
            except Exception as e:
                logger.warning("[active] 广播失败: %s", e)

            logger.info("[active] 用户 %s 主动发消息（第 %s 次未回应）: %s",
                        user_id, (user.unanswered_active_count if user else '?'), text[:30])
    except Exception as e:
        logger.warning("[active] 扫描失败: %s", e)
    finally:
        db.close()


def start_active_chat_worker():
    """启动后台主动发消息线程（守护线程，随主进程退出）。"""
    def _loop():
        logger.info("[active] 主动发消息线程启动，检查间隔 %ds", ACTIVE_CHECK_INTERVAL_SEC)
        while True:
            try:
                _check_and_activate()
            except Exception as e:
                logger.warning("[active] 循环异常: %s", e)
            time.sleep(ACTIVE_CHECK_INTERVAL_SEC)

    t = threading.Thread(target=_loop, daemon=True, name="active-chat-worker")
    t.start()
    return t
