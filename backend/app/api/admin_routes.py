"""
推广拉新/钱包 + 后台管理 — extracted from main.py (L1276-L1615).

Endpoints:
- /ai/promo/*  (推广拉新/钱包)
- /admin       (后台页面)
- /admin/api/* (后台 API)
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import (
    APIRouter, Depends, HTTPException, Query, Request,
)
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

import app.config as config
from app.core.db import (
    get_db, User, WithdrawRequest, PromoConfig, PROMO_CONFIG_DEFAULTS, RequestLog,
    CustomCharacter,
)
from app.core.token_utils import verify_token, get_optional_user_id, create_admin_token, verify_admin_token
from app.services import promo


logger = logging.getLogger(__name__)
router = APIRouter()

_templates_ref: Optional[Jinja2Templates] = None


def bind(templates):
    global _templates_ref
    _templates_ref = templates


# ==================================================================
# Pydantic 模型
# ==================================================================

class TrackDownloadRequest(BaseModel):
    ref: str = ""
    fingerprint: str = ""


class WithdrawSubmitRequest(BaseModel):
    paypal_email: str


class AdminLoginForm(BaseModel):
    username: str
    password: str


class AdminConfigUpdate(BaseModel):
    items: dict


class AdminBalanceAdjust(BaseModel):
    amount: float
    reason: str = ""


# ==================================================================
# 推广拉新 / 钱包
# ==================================================================

@router.get("/ai/promo/config", summary="推广展示配置（公开）")
def promo_config(db: Session = Depends(get_db)):
    cfg = promo.get_config_map(db)
    return {
        "code": 200,
        "promo_enabled": promo._is_on(cfg.get("promo_enabled")),
        "input_promo_enabled": promo._is_on(cfg.get("input_promo_enabled")),
        "link_cache_days": promo._to_int(cfg.get("link_cache_days"), 30),
        "popup_intro": {"zh": cfg.get("popup_intro_zh", ""), "en": cfg.get("popup_intro_en", "")},
        "input_promo": {"zh": cfg.get("input_promo_zh", ""), "en": cfg.get("input_promo_en", "")},
        "banner_promo": {"zh": cfg.get("banner_promo_zh", ""), "en": cfg.get("banner_promo_en", "")},
    }


@router.get("/ai/promo/my-link", summary="获取我的专属推广链接")
def promo_my_link(
        db: Session = Depends(get_db),
        user_id: int = Depends(verify_token),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail={"code": 404, "msg": "用户不存在"})
    code = promo.get_or_create_referral_code(db, user)
    return {"code": 200, "referral_code": code, "link": promo.build_referral_link(db, code)}


@router.post("/ai/promo/track-download", summary="记录下载控件点击并给推广人发奖（公开）")
def promo_track_download(
        request: TrackDownloadRequest,
        http_request: Request,
        db: Session = Depends(get_db),
        user_id: Optional[int] = Depends(get_optional_user_id),
):
    ip = promo.client_ip(http_request)
    ref = (request.ref or "").strip()
    fingerprint = (request.fingerprint or "").strip()

    try:
        promo.record_download_click(db, ip=ip, fingerprint=fingerprint, ref_code=ref)
    except Exception as e:
        logger.warning(f"[埋点] 下载点击记录失败：{e}")

    result = promo.track_download(
        db,
        ref_code=ref,
        fingerprint=fingerprint,
        ip=ip,
        visitor_user_id=user_id,
    )
    return {"code": 200, **result.to_dict()}


@router.get("/ai/promo/wallet", summary="我的钱包（余额 + 提现记录）")
def promo_wallet(
        db: Session = Depends(get_db),
        user_id: int = Depends(verify_token),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail={"code": 404, "msg": "用户不存在"})
    records = db.query(WithdrawRequest).filter(
        WithdrawRequest.user_id == user_id
    ).order_by(WithdrawRequest.created_at.desc()).all()
    return {
        "code": 200,
        "balance": round(user.balance_usd or 0.0, 2),
        "referral_count": user.referral_count or 0,
        "records": [
            {
                "id": r.id,
                "amount": round(r.amount, 2),
                "paypal_email": r.paypal_email,
                "status": r.status,
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
            }
            for r in records
        ],
    }


@router.get("/ai/promo/checkin-status", summary="获取我的签到状态")
def promo_checkin_status(
        db: Session = Depends(get_db),
        user_id: int = Depends(verify_token),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail={"code": 404, "msg": "用户不存在"})
    return {"code": 200, **promo.get_checkin_status(db, user)}


@router.post("/ai/promo/checkin", summary="签到领奖励")
def promo_checkin(
        db: Session = Depends(get_db),
        user_id: int = Depends(verify_token),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail={"code": 404, "msg": "用户不存在"})
    result = promo.do_checkin(db, user)
    if not result.ok:
        raise HTTPException(status_code=400, detail={"code": 400, "msg": "签到功能已关闭"})
    return {"code": 200, **result.to_dict()}


@router.get("/ai/promo/withdraw-available", summary="查询可提现金额（含风控校验）")
def promo_withdraw_available(
        db: Session = Depends(get_db),
        user_id: int = Depends(verify_token),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail={"code": 404, "msg": "用户不存在"})
    return {"code": 200, **promo.get_withdraw_available(db, user)}


@router.post("/ai/promo/withdraw", summary="提交提现申请（提现全部余额）")
def promo_withdraw(
        request: WithdrawSubmitRequest,
        db: Session = Depends(get_db),
        user_id: int = Depends(verify_token),
):
    email = (request.paypal_email or "").strip()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail={"code": 400, "msg": "请输入有效的 PayPal 邮箱"})

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail={"code": 404, "msg": "用户不存在"})

    withdraw_info = promo.get_withdraw_available(db, user)
    if not withdraw_info["can_withdraw"]:
        reasons = "；".join(withdraw_info["reasons"]) or "暂不可提现"
        raise HTTPException(status_code=400, detail={"code": 400, "msg": reasons})

    balance = withdraw_info["balance"]
    if balance <= 0:
        raise HTTPException(status_code=400, detail={"code": 400, "msg": "余额不足，无法提现"})

    record = WithdrawRequest(user_id=user_id, amount=balance, paypal_email=email, status="pending")
    db.add(record)
    user.balance_usd = 0.0
    db.commit()
    return {"code": 200, "msg": "提现申请已提交，等待人工审核", "amount": balance}


# ==================================================================
# 后台管理 /admin
# ==================================================================

@router.get("/admin", summary="后台管理页", description="返回后台单页，数据靠 /admin/api/* 异步拉取")
def admin_page(request: Request):
    return _templates_ref.TemplateResponse(name="admin.html", request=request)


@router.post("/admin/api/login", summary="后台登录")
def admin_login(form: AdminLoginForm):
    if not config.ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail={"code": 403, "msg": "后台未设置管理员密码，请在 .env 配置 ADMIN_PASSWORD"})
    if form.username == config.ADMIN_USERNAME and form.password == config.ADMIN_PASSWORD:
        return {"code": 200, "token": create_admin_token()}
    raise HTTPException(status_code=401, detail={"code": 401, "msg": "账号或密码错误"})


@router.get("/admin/api/stats", summary="后台数据看板")
def admin_stats(db: Session = Depends(get_db), _: bool = Depends(verify_admin_token)):
    return {"code": 200, **promo.get_admin_stats(db)}


@router.get("/admin/api/users", summary="用户列表")
def admin_users(
        q: str = Query("", description="按用户名搜索"),
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
        db: Session = Depends(get_db),
        _: bool = Depends(verify_admin_token),
):
    query = db.query(User)
    if q.strip():
        query = query.filter(User.username.like(f"%{q.strip()}%"))
    total = query.count()
    rows = query.order_by(User.id.desc()).offset(offset).limit(limit).all()
    return {
        "code": 200,
        "total": total,
        "users": [
            {
                "id": u.id,
                "username": u.username,
                "balance": round(u.balance_usd or 0.0, 2),
                "referral_count": u.referral_count or 0,
                "referral_code": u.referral_code or "",
                "membership_expire_at": u.membership_expire_at.strftime("%Y-%m-%d") if u.membership_expire_at else "",
                "register_time": u.register_time.strftime("%Y-%m-%d %H:%M") if u.register_time else "",
            }
            for u in rows
        ],
    }


@router.post("/admin/api/users/{uid}/balance", summary="手动调整用户余额")
def admin_adjust_balance(
        uid: int,
        body: AdminBalanceAdjust,
        db: Session = Depends(get_db),
        _: bool = Depends(verify_admin_token),
):
    user = db.query(User).filter(User.id == uid).first()
    if not user:
        raise HTTPException(status_code=404, detail={"code": 404, "msg": "用户不存在"})
    new_balance = round((user.balance_usd or 0.0) + body.amount, 2)
    if new_balance < 0:
        raise HTTPException(status_code=400, detail={"code": 400, "msg": "调整后余额不能为负"})
    user.balance_usd = new_balance
    db.commit()
    return {"code": 200, "msg": "已调整", "balance": new_balance}


@router.get("/admin/api/withdraws", summary="提现申请列表")
def admin_withdraws(
        status_filter: str = Query("", alias="status", description="pending/paid/rejected，空=全部"),
        db: Session = Depends(get_db),
        _: bool = Depends(verify_admin_token),
):
    query = db.query(WithdrawRequest)
    if status_filter in ("pending", "paid", "rejected"):
        query = query.filter(WithdrawRequest.status == status_filter)
    rows = query.order_by(WithdrawRequest.created_at.desc()).all()
    user_map = {u.id: u.username for u in db.query(User).all()}
    return {
        "code": 200,
        "withdraws": [
            {
                "id": r.id,
                "user_id": r.user_id,
                "username": user_map.get(r.user_id, f"#{r.user_id}"),
                "amount": round(r.amount, 2),
                "paypal_email": r.paypal_email,
                "status": r.status,
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
                "reviewed_at": r.reviewed_at.strftime("%Y-%m-%d %H:%M") if r.reviewed_at else "",
            }
            for r in rows
        ],
    }


@router.post("/admin/api/withdraws/{wid}/approve", summary="通过提现")
def admin_withdraw_approve(
        wid: int,
        db: Session = Depends(get_db),
        _: bool = Depends(verify_admin_token),
):
    record = db.query(WithdrawRequest).filter(WithdrawRequest.id == wid).first()
    if not record:
        raise HTTPException(status_code=404, detail={"code": 404, "msg": "提现记录不存在"})
    if record.status != "pending":
        raise HTTPException(status_code=400, detail={"code": 400, "msg": f"该申请已是 {record.status}，无法重复处理"})
    record.status = "paid"
    record.reviewed_at = datetime.now()
    db.commit()
    return {"code": 200, "msg": "已标记为已打款"}


@router.post("/admin/api/withdraws/{wid}/reject", summary="驳回提现（余额退回用户）")
def admin_withdraw_reject(
        wid: int,
        db: Session = Depends(get_db),
        _: bool = Depends(verify_admin_token),
):
    record = db.query(WithdrawRequest).filter(WithdrawRequest.id == wid).first()
    if not record:
        raise HTTPException(status_code=404, detail={"code": 404, "msg": "提现记录不存在"})
    if record.status != "pending":
        raise HTTPException(status_code=400, detail={"code": 400, "msg": f"该申请已是 {record.status}，无法重复处理"})
    record.status = "rejected"
    record.reviewed_at = datetime.now()
    user = db.query(User).filter(User.id == record.user_id).first()
    if user:
        user.balance_usd = round((user.balance_usd or 0.0) + record.amount, 2)
    db.commit()
    return {"code": 200, "msg": "已驳回，金额已退回用户余额"}


@router.get("/admin/api/memory-audit", summary="记忆体审核列表")
def admin_memory_audit(
        status_filter: str = Query("", alias="status", description="draft/pending/approved/rejected，空=全部"),
        db: Session = Depends(get_db),
        _: bool = Depends(verify_admin_token),
):
    query = db.query(CustomCharacter)
    if status_filter in ("draft", "pending", "approved", "rejected"):
        query = query.filter(CustomCharacter.status == status_filter)
    rows = query.order_by(CustomCharacter.updated_at.desc()).all()
    user_map = {u.id: u.username for u in db.query(User).all()}
    return {
        "code": 200,
        "characters": [
            {
                "npc_id": c.npc_id,
                "user_id": c.user_id,
                "username": user_map.get(c.user_id, f"#{c.user_id}"),
                "name": c.name,
                "description": c.description,
                "persona": c.persona,
                "status": c.status,
                "updated_at": c.updated_at.strftime("%Y-%m-%d %H:%M") if c.updated_at else "",
            }
            for c in rows
        ],
    }


@router.post("/admin/api/memory-audit/{npc_id}/approve", summary="通过记忆体审核")
def admin_memory_approve(
        npc_id: str,
        db: Session = Depends(get_db),
        _: bool = Depends(verify_admin_token),
):
    record = db.query(CustomCharacter).filter(CustomCharacter.npc_id == npc_id).first()
    if not record:
        raise HTTPException(status_code=404, detail={"code": 404, "msg": "记忆体不存在"})
    if record.status == "approved":
        raise HTTPException(status_code=400, detail={"code": 400, "msg": "该记忆体已通过审核"})
    if not (record.name or "").strip() or not (record.persona or "").strip():
        raise HTTPException(status_code=400, detail={"code": 400, "msg": "记忆体名称和人设不能为空，无法通过"})
    record.status = "approved"
    db.commit()
    return {"code": 200, "msg": "已通过审核，用户现在可以使用该记忆体"}


@router.post("/admin/api/memory-audit/{npc_id}/reject", summary="拒绝记忆体审核")
def admin_memory_reject(
        npc_id: str,
        db: Session = Depends(get_db),
        _: bool = Depends(verify_admin_token),
):
    record = db.query(CustomCharacter).filter(CustomCharacter.npc_id == npc_id).first()
    if not record:
        raise HTTPException(status_code=404, detail={"code": 404, "msg": "记忆体不存在"})
    if record.status == "rejected":
        raise HTTPException(status_code=400, detail={"code": 400, "msg": "该记忆体已拒绝"})
    record.status = "rejected"
    db.commit()
    return {"code": 200, "msg": "已拒绝，该记忆体不可使用"}


@router.get("/admin/api/config", summary="获取全部推广配置")
def admin_get_config(db: Session = Depends(get_db), _: bool = Depends(verify_admin_token)):
    return {"code": 200, "config": promo.get_config_map(db)}


@router.post("/admin/api/config", summary="批量更新推广配置")
def admin_set_config(
        body: AdminConfigUpdate,
        db: Session = Depends(get_db),
        _: bool = Depends(verify_admin_token),
):
    allowed = set(PROMO_CONFIG_DEFAULTS.keys())
    updated = []
    for key, value in body.items.items():
        if key not in allowed:
            continue
        row = db.query(PromoConfig).filter(PromoConfig.key == key).first()
        if row:
            row.value = str(value)
        else:
            db.add(PromoConfig(key=key, value=str(value)))
        updated.append(key)
    db.commit()
    return {"code": 200, "msg": "已保存", "updated": updated}


# ==================================================================
# 服务器信息 / 实时日志 / 用户信息（数据看板子级）
# ==================================================================

def _read_tail(path: Path, lines: int = 300, max_bytes: int = 2 * 1024 * 1024) -> str:
    """高效读取日志文件尾部 N 行（最多读 2MB，避免大文件卡顿）。"""
    try:
        size = path.stat().st_size
        if size == 0:
            return ""
        read_size = min(size, max_bytes)
        with open(path, "rb") as f:
            f.seek(size - read_size)
            data = f.read().decode("utf-8", errors="replace")
        return "\n".join(data.splitlines()[-lines:])
    except FileNotFoundError:
        return ""
    except Exception as e:
        return f"[读取日志失败] {e}"


def _read_tail_offset(path: Path, offset: int, max_bytes: int = 2 * 1024 * 1024) -> dict:
    """从 offset 字节之后增量读取日志（用于前端防闪烁的增量追加）。

    返回 {content, offset, truncated}：
      - offset 之后有新增 → content=新增部分, offset=新文件大小
      - offset 之后无新增 → content="", offset=offset
      - offset 失效（文件被 rolling 截断/重置）→ truncated=True, 前端应全量重载
    """
    try:
        size = path.stat().st_size
        if size == 0:
            return {"content": "", "offset": 0, "truncated": False}
        if offset > size:
            # 文件被截断/轮转重置，offset 失效
            return {"content": "", "offset": size, "truncated": True}
        if offset == size:
            return {"content": "", "offset": size, "truncated": False}
        # 增量读，最多 2MB
        read_size = min(size - offset, max_bytes)
        with open(path, "rb") as f:
            f.seek(offset)
            data = f.read(read_size).decode("utf-8", errors="replace")
        return {"content": data, "offset": offset + read_size, "truncated": False}
    except FileNotFoundError:
        return {"content": "", "offset": 0, "truncated": True}
    except Exception as e:
        return {"content": f"[读取日志失败] {e}", "offset": offset, "truncated": False}


def _logs_startpy_path() -> Path:
    from app.core.paths import logs_dir
    return Path(logs_dir()) / "app.log"


def _logs_voicestudio_path() -> Path:
    """VoiceStudio 日志：优先 OMNIVOICE_DATA_DIR，否则 Windows %APPDATA% / 类 Unix ~/.local/share。"""
    import os
    data_dir = os.environ.get("OMNIVOICE_DATA_DIR")
    if data_dir:
        return Path(data_dir) / "omnivoice.log"
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "OmniVoice" / "omnivoice.log"
    home = Path.home()
    for cand in (
        home / ".local" / "share" / "OmniVoice" / "omnivoice.log",
        home / ".omnivoice" / "omnivoice.log",
    ):
        if cand.exists():
            return cand
    return home / ".local" / "share" / "OmniVoice" / "omnivoice.log"


@router.get("/admin/api/server-info", summary="服务器性能指标（CPU/内存/磁盘/进程/运行时长）")
def admin_server_info(_: bool = Depends(verify_admin_token)):
    import platform
    import os
    import sys
    from datetime import datetime

    info = {
        "hostname": platform.node(),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "cpu_count": os.cpu_count() or 0,
        "boot_time": None,
        "cpu_percent": None,
        "mem_total": None,
        "mem_used": None,
        "mem_percent": None,
        "disk_total": None,
        "disk_used": None,
        "disk_percent": None,
        "process_rss": None,
        "process_cpu": None,
        "process_threads": None,
        "process_uptime": None,
        "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    try:
        import psutil
        info["cpu_percent"] = round(psutil.cpu_percent(interval=0.2), 1)
        vm = psutil.virtual_memory()
        info["mem_total"] = vm.total
        info["mem_used"] = vm.used
        info["mem_percent"] = vm.percent
        du = psutil.disk_usage(str(Path(__file__).resolve().anchor))
        info["disk_total"] = du.total
        info["disk_used"] = du.used
        info["disk_percent"] = du.percent
        info["boot_time"] = datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")
        proc = psutil.Process(os.getpid())
        info["process_rss"] = proc.memory_info().rss
        info["process_cpu"] = round(proc.cpu_percent(interval=0.1), 1)
        info["process_threads"] = proc.num_threads()
        info["process_uptime"] = int(datetime.now().timestamp() - proc.create_time())
    except Exception as e:
        info["psutil_error"] = str(e)

    if info["process_uptime"] is not None:
        secs = info["process_uptime"]
        info["process_uptime_human"] = f"{secs // 3600}h {(secs % 3600) // 60}m {secs % 60}s"
    else:
        info["process_uptime_human"] = "未知"

    return {"code": 200, **info}


@router.get("/admin/api/logs/startpy", summary="Python start.py 服务日志（实时尾部）")
def admin_logs_startpy(
        lines: int = Query(200, ge=10, le=2000),
        offset: int = Query(0, ge=0, description="增量读取的字节偏移；0=全量尾部"),
        _: bool = Depends(verify_admin_token),
):
    path = _logs_startpy_path()
    size = path.stat().st_size if path.exists() else 0
    if offset > 0:
        inc = _read_tail_offset(path, offset)
        return {
            "code": 200,
            "path": str(path),
            "exists": path.exists(),
            "size": size,
            "content": inc["content"],
            "offset": inc["offset"],
            "truncated": inc["truncated"],
        }
    return {
        "code": 200,
        "path": str(path),
        "exists": path.exists(),
        "size": size,
        "content": _read_tail(path, lines=lines),
        "offset": size,
        "truncated": False,
    }


@router.get("/admin/api/logs/voicestudio", summary="VoiceStudio 服务日志（实时尾部）")
def admin_logs_voicestudio(
        lines: int = Query(200, ge=10, le=2000),
        offset: int = Query(0, ge=0, description="增量读取的字节偏移；0=全量尾部"),
        _: bool = Depends(verify_admin_token),
):
    path = _logs_voicestudio_path()
    size = path.stat().st_size if path.exists() else 0
    if offset > 0:
        inc = _read_tail_offset(path, offset)
        return {
            "code": 200,
            "path": str(path),
            "exists": path.exists(),
            "size": size,
            "content": inc["content"],
            "offset": inc["offset"],
            "truncated": inc["truncated"],
        }
    return {
        "code": 200,
        "path": str(path),
        "exists": path.exists(),
        "size": size,
        "content": _read_tail(path, lines=lines),
        "offset": size,
        "truncated": False,
    }


@router.get("/admin/api/users-info", summary="用户信息（注册用户 + 访客 IP/请求头/token 用量）")
def admin_users_info(
        db: Session = Depends(get_db),
        _: bool = Depends(verify_admin_token),
):
    from sqlalchemy import func

    users = db.query(User).order_by(User.id.desc()).all()

    user_token_rows = db.query(
        RequestLog.user_id,
        func.coalesce(func.sum(RequestLog.tokens_in), 0),
        func.coalesce(func.sum(RequestLog.tokens_out), 0),
        func.count(RequestLog.id),
    ).filter(RequestLog.user_id.isnot(None)).group_by(RequestLog.user_id).all()
    user_tokens = {r[0]: {"tokens_in": int(r[1] or 0), "tokens_out": int(r[2] or 0), "requests": int(r[3] or 0)} for r in user_token_rows}

    user_last_req = {}
    for r in db.query(RequestLog).filter(RequestLog.user_id.isnot(None)).order_by(RequestLog.id.desc()).limit(5000).all():
        if r.user_id not in user_last_req:
            user_last_req[r.user_id] = {
                "ip": r.ip,
                "user_agent": r.user_agent,
                "last_path": r.path,
                "last_time": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "",
            }

    registered = []
    for u in users:
        t = user_tokens.get(u.id, {"tokens_in": 0, "tokens_out": 0, "requests": 0})
        lr = user_last_req.get(u.id, {})
        registered.append({
            "id": u.id,
            "username": u.username,
            "nickname": u.nickname or "",
            "phone": u.phone or "",
            "register_time": u.register_time.strftime("%Y-%m-%d %H:%M:%S") if u.register_time else "",
            "ip": lr.get("ip") or "",
            "user_agent": (lr.get("user_agent") or "")[:80],
            "last_path": lr.get("last_path") or "",
            "last_time": lr.get("last_time") or "",
            "tokens_in": t["tokens_in"],
            "tokens_out": t["tokens_out"],
            "tokens_total": t["tokens_in"] + t["tokens_out"],
            "requests": t["requests"],
        })

    visitor_rows = db.query(
        RequestLog.ip,
        RequestLog.visitor_key,
        func.count(RequestLog.id),
        func.coalesce(func.sum(RequestLog.tokens_in), 0),
        func.coalesce(func.sum(RequestLog.tokens_out), 0),
        func.max(RequestLog.created_at),
    ).filter(RequestLog.user_id.is_(None)).group_by(RequestLog.ip, RequestLog.visitor_key).order_by(
        func.max(RequestLog.created_at).desc()
    ).limit(200).all()

    visitors = []
    for ip, vk, cnt, tin, tout, last_time in visitor_rows:
        ua_row = db.query(RequestLog.user_agent).filter(
            RequestLog.user_id.is_(None),
            RequestLog.ip == ip,
        ).order_by(RequestLog.id.desc()).first()
        ua = ua_row[0] if ua_row else ""
        visitors.append({
            "ip": ip or "未知",
            "visitor_key": vk or "",
            "user_agent": (ua or "")[:80],
            "requests": int(cnt or 0),
            "tokens_in": int(tin or 0),
            "tokens_out": int(tout or 0),
            "tokens_total": int((tin or 0) + (tout or 0)),
            "last_time": last_time.strftime("%Y-%m-%d %H:%M:%S") if last_time else "",
        })

    total_visitor_requests = db.query(func.count(RequestLog.id)).filter(RequestLog.user_id.is_(None)).scalar() or 0
    total_user_requests = db.query(func.count(RequestLog.id)).filter(RequestLog.user_id.isnot(None)).scalar() or 0
    total_tokens = db.query(
        func.coalesce(func.sum(RequestLog.tokens_in), 0),
        func.coalesce(func.sum(RequestLog.tokens_out), 0),
    ).first()

    return {
        "code": 200,
        "registered": registered,
        "visitors": visitors,
        "summary": {
            "registered_count": len(registered),
            "visitor_count": len(visitors),
            "visitor_requests": int(total_visitor_requests),
            "user_requests": int(total_user_requests),
            "tokens_in_total": int(total_tokens[0] or 0),
            "tokens_out_total": int(total_tokens[1] or 0),
        },
    }


# ==================================================================
# 音色管理（VoiceStudio 本地服务 127.0.0.1:3900）
# ==================================================================

def _voicestudio_request(method: str, path: str, timeout: int = 30):
    """直连 VoiceStudio 本地服务，返回 (status, decoded_data)。"""
    import json as _json
    import urllib.request
    import urllib.error

    url = "http://127.0.0.1:3900" + path
    req = urllib.request.Request(url, method=method, headers={"User-Agent": "jingent-admin/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, _json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, _json.loads(e.read().decode("utf-8", errors="replace"))
        except Exception:
            return e.code, {"detail": f"VoiceStudio HTTP {e.code}"}
    except Exception as e:
        return -1, {"detail": f"无法连接 VoiceStudio：{str(e)[:200]}"}


@router.get("/admin/api/voices", summary="音色列表（VoiceStudio）")
def admin_voices(_: bool = Depends(verify_admin_token)):
    status, data = _voicestudio_request("GET", "/v1/audio/voices")
    if status != 200:
        raise HTTPException(status_code=502, detail={"code": 502, "msg": f"VoiceStudio 不可用（status={status}）"})
    voices = data.get("voices", []) if isinstance(data, dict) else []
    # 只返回可删除的 profile 音色 + 标记内置别名不可删
    result = []
    for v in voices:
        vid = v.get("voice_id") or v.get("id")
        result.append({
            "voice_id": vid,
            "name": v.get("name") or vid,
            "type": v.get("type", ""),
            "deletable": v.get("type") == "profile",
        })
    return {"code": 200, "voices": result, "total": len(result)}


@router.delete("/admin/api/voices/{voice_id}", summary="删除指定音色（VoiceStudio profile）")
def admin_delete_voice(voice_id: str, _: bool = Depends(verify_admin_token)):
    status, data = _voicestudio_request("DELETE", f"/profiles/{voice_id}")
    if status == 404:
        raise HTTPException(status_code=404, detail={"code": 404, "msg": "音色不存在"})
    if status != 200:
        detail = (data or {}).get("detail", "") if isinstance(data, dict) else str(data)
        raise HTTPException(status_code=502, detail={"code": 502, "msg": f"删除失败（status={status}）：{detail[:200]}"})
    return {"code": 200, "msg": f"已删除音色 {voice_id}"}
