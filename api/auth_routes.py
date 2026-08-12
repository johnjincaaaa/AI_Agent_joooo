"""
认证与用户信息 — extracted from main.py.

Sections:
- 手机号注册+验证码 (L1617-L1720)
- 用户信息 (L1722-L1796: /user/info, /user/nickname, /user/password)
- 短信验证码登录 (L1798-L1837)
- 用户名登录 + 注册 (L1839-L1900)
"""
import logging
import random
import time as _time_mod
import uuid as _uuid
from typing import Optional

from fastapi import (
    APIRouter, Depends, Response,
)
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from sqlOrm import get_db, User
from token_utils import verify_token, get_optional_user_id, create_access_token, TOKEN_COOKIE_KEY
from password_utils import hash_password, verify_password, needs_rehash
from config import ACCESS_TOKEN_EXPIRE_MINUTES


logger = logging.getLogger(__name__)
router = APIRouter()


def _token_response(payload: dict, token: str, status_code: int = 200) -> JSONResponse:
    """统一的登录/注册返回：JSON body + HTTP-only Cookie 双写，便于 chat/jinclaw 跨页面共享登录态。"""
    resp = JSONResponse(status_code=status_code, content=payload)
    # 把 token 写进 cookie：过期时间与 JWT exp 对齐（分钟→秒），兜底 30 天
    max_age = max(60, int(ACCESS_TOKEN_EXPIRE_MINUTES) * 60)
    # 安全说明：开发环境用 HTTP，所以 secure=False；生产部署 HTTPS 时可改为 True
    resp.set_cookie(
        key=TOKEN_COOKIE_KEY,
        value=token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )
    # 再写一个可读 cookie 给旧代码（前端 localStorage 同步）：非 HTTP-only
    resp.set_cookie(
        key="auth_token",
        value=token,
        max_age=max_age,
        httponly=False,
        samesite="lax",
        secure=False,
        path="/",
    )
    return resp


# 内存存储验证码：{phone: {"code": "123456", "expire": 时间戳}}
_sms_codes: dict = {}


def _gen_verify_code() -> str:
    return "".join(random.choices("0123456789", k=6))


def _is_valid_phone(phone: str) -> bool:
    return bool(phone and phone.isdigit() and len(phone) == 11 and phone.startswith("1"))


# ==================================================================
# Pydantic 模型
# ==================================================================

class SendCodeForm(BaseModel):
    phone: str


class RegisterByPhoneForm(BaseModel):
    phone: str
    code: str
    password: str
    confirm_password: str


class UpdateNicknameForm(BaseModel):
    nickname: str


class UpdatePasswordForm(BaseModel):
    old_password: str
    new_password: str
    confirm_password: str


class SmsLoginForm(BaseModel):
    phone: str
    code: str


class LoginForm(BaseModel):
    username: str
    password: str


class RegisterForm(BaseModel):
    username: str
    password: str


# ==================================================================
# 手机号注册 + 验证码
# ==================================================================

@router.post('/sms/send-code', summary='发送手机验证码')
def send_sms_code(form: SendCodeForm):
    phone = form.phone.strip()
    if not _is_valid_phone(phone):
        return {"code": 400, "msg": "手机号格式不正确"}
    now = _time_mod.time()
    cached = _sms_codes.get(phone)
    if cached and now - cached.get("sent_at", 0) < 60:
        return {"code": 429, "msg": "发送太频繁，请稍后再试"}
    code = _gen_verify_code()
    _sms_codes[phone] = {
        "code": code,
        "expire": now + 300,
        "sent_at": now,
    }
    return {"code": 200, "msg": "验证码已发送", "debug_code": code}


@router.post('/register/phone', summary='手机号注册')
def register_by_phone(
    form: RegisterByPhoneForm,
    db: Session = Depends(get_db),
):
    phone = form.phone.strip()
    if not _is_valid_phone(phone):
        return {"code": 400, "msg": "手机号格式不正确"}
    if len(form.password) < 6:
        return {"code": 400, "msg": "密码至少6位"}
    if form.password != form.confirm_password:
        return {"code": 400, "msg": "两次密码不一致"}

    cached = _sms_codes.get(phone)
    now = _time_mod.time()
    if not cached or cached.get("expire", 0) < now:
        return {"code": 400, "msg": "验证码已过期，请重新获取"}
    if cached.get("code") != form.code.strip():
        return {"code": 400, "msg": "验证码错误"}

    exist = db.query(User).filter(User.phone == phone).first()
    if exist:
        return {"code": 400, "msg": "该手机号已注册"}

    suffix = _uuid.uuid4().hex[:6].lower()
    default_username = f"Jingent_{suffix}"
    while db.query(User).filter(User.username == default_username).first():
        suffix = _uuid.uuid4().hex[:6].lower()
        default_username = f"Jingent_{suffix}"

    new_user = User(
        username=default_username,
        phone=phone,
        nickname=default_username,
        password=hash_password(form.password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    _sms_codes.pop(phone, None)

    token = create_access_token({'user_id': new_user.id})
    return _token_response({
        "code": 200,
        "msg": "注册成功",
        "token": token,
        "user_id": new_user.id,
        "username": new_user.username,
        "nickname": new_user.nickname,
    }, token)


# ==================================================================
# 用户信息
# ==================================================================

@router.get('/user/info', summary='获取当前用户信息')
def get_user_info(
    user_id: Optional[int] = Depends(get_optional_user_id),
    db: Session = Depends(get_db),
):
    if not user_id:
        return {"code": 401, "msg": "未登录"}
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"code": 404, "msg": "用户不存在"}
    return {
        "code": 200,
        "data": {
            "user_id": user.id,
            "username": user.username,
            "nickname": user.nickname or user.username,
            "phone": user.phone,
            "register_time": user.register_time.isoformat() if user.register_time else None,
        }
    }


@router.post('/user/nickname', summary='修改用户昵称')
def update_nickname(
    form: UpdateNicknameForm,
    user_id: Optional[int] = Depends(get_optional_user_id),
    db: Session = Depends(get_db),
):
    if not user_id:
        return {"code": 401, "msg": "未登录"}
    nickname = form.nickname.strip()
    if not nickname:
        return {"code": 400, "msg": "昵称不能为空"}
    if len(nickname) > 20:
        return {"code": 400, "msg": "昵称长度不能超过20个字符"}
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"code": 404, "msg": "用户不存在"}
    user.nickname = nickname
    db.commit()
    return {"code": 200, "msg": "昵称修改成功", "nickname": nickname}


@router.post('/user/password', summary='修改密码')
def update_password(
    form: UpdatePasswordForm,
    user_id: Optional[int] = Depends(get_optional_user_id),
    db: Session = Depends(get_db),
):
    if not user_id:
        return {"code": 401, "msg": "未登录"}
    if len(form.new_password) < 6:
        return {"code": 400, "msg": "新密码至少6位"}
    if form.new_password != form.confirm_password:
        return {"code": 400, "msg": "两次新密码不一致"}
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"code": 404, "msg": "用户不存在"}
    if not verify_password(form.old_password, user.password):
        return {"code": 400, "msg": "原密码错误"}
    user.password = hash_password(form.new_password)
    db.commit()
    return {"code": 200, "msg": "密码修改成功"}


# ==================================================================
# 短信验证码登录
# ==================================================================

@router.post('/login/sms', summary='短信验证码登录')
def login_by_sms(
        form: SmsLoginForm,
        db: Session = Depends(get_db),
):
    phone = form.phone.strip()
    if not _is_valid_phone(phone):
        return {"code": 400, "msg": "手机号格式不正确"}

    cached = _sms_codes.get(phone)
    now = _time_mod.time()
    if not cached or cached.get("expire", 0) < now:
        return {"code": 400, "msg": "验证码已过期，请重新获取"}
    if cached.get("code") != form.code.strip():
        return {"code": 400, "msg": "验证码错误"}

    existing_user = db.query(User).filter(User.phone == phone).first()
    if not existing_user:
        return {"code": 404, "msg": "该手机号未注册，请先注册"}

    _sms_codes.pop(phone, None)

    token: str = create_access_token({'user_id': existing_user.id})
    return _token_response({
        "code": 200,
        "msg": "登录成功",
        "token": token,
        "user_id": existing_user.id,
        "username": existing_user.nickname or existing_user.username,
    }, token)


# ==================================================================
# 用户名登录 + 注册
# ==================================================================

@router.post('/login', summary='登录')
def login(
        form: LoginForm,
        db: Session = Depends(get_db),

):
    existing_user = db.query(User).filter(
        (User.username == form.username) | (User.phone == form.username),
    ).first()
    if existing_user and verify_password(form.password, existing_user.password):
        if needs_rehash(existing_user.password):
            existing_user.password = hash_password(form.password)
            db.commit()
        token: str = create_access_token({'user_id': existing_user.id})
        return _token_response({
            "code": 200,
            "msg": "登录成功",
            "token": token,
            "user_id": existing_user.id,
            "username": existing_user.nickname or existing_user.username,
        }, token)
    else:
        return {
            "code": 401,
            "msg": "用户名或密码错误"
        }


@router.post('/register', summary='注册')
def register(
        form: RegisterForm,
        db: Session = Depends(get_db)
):
    existed_user = db.query(User).filter(
        User.username == form.username,
    ).first()
    if existed_user:
        return {'code': 401, "msg": "已存在用户名"}
    else:
        new_user = User(
            username=form.username,
            password=hash_password(form.password),
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        token: str = create_access_token({'user_id': new_user.id})
        return _token_response({
            "code": 200,
            "msg": "注册成功",
            "token": token,
            "user_id": new_user.id,
            "username": new_user.nickname or new_user.username,
        }, token)
