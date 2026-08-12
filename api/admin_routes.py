"""
推广拉新/钱包 + 后台管理 — extracted from main.py (L1276-L1615).

Endpoints:
- /ai/promo/*  (推广拉新/钱包)
- /admin       (后台页面)
- /admin/api/* (后台 API)
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import (
    APIRouter, Depends, HTTPException, Query, Request,
)
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

import config
from sqlOrm import (
    get_db, User, WithdrawRequest, PromoConfig, PROMO_CONFIG_DEFAULTS,
)
from token_utils import verify_token, get_optional_user_id, create_admin_token, verify_admin_token
from services import promo


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
