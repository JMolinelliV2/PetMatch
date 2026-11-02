from datetime import timedelta
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, Field, ConfigDict
from typing import Literal
import re

from app.core.security import create_access_token, decode_token_claims, hash_password, verify_password, password_needs_upgrade
from app.core.config import settings
from app.core.login_limit import check_login_budget
from app.analysis.service import utcnow
from app.db.session import get_db
from app.dependencies import current_user, oauth2_scheme
from app.models import User, AuthSession, Notification, AccountToken
from app.admin_access import claim_reserved_access
from app.schemas import LoginRequest, NotificationPreferences, RegisterRequest, TokenResponse, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


def issue_session(db, user):
    session = AuthSession(user_id=user.id, expires_at=utcnow() + timedelta(minutes=settings.access_token_minutes))
    db.add(session)
    db.flush()
    token = create_access_token(user.id, session.id)
    db.commit()
    return TokenResponse(access_token=token, user=user, expires_in=settings.access_token_minutes * 60)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",email) or not payload.name.strip():
        raise HTTPException(status_code=422, detail="A valid email address is required")
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    require_account_mail()
    user = User(email=email, password_hash=hash_password(payload.password), name=payload.name.strip(), phone=payload.phone)
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409,detail="An account with this email already exists") from exc
    from app.account_mail import issue_token
    issue_token(db,user,"VERIFY_EMAIL")
    from app.product_analytics import record
    record(db,"account_created",user.id,request=request,user=user)
    result = issue_session(db, user)
    request.state.activity_user_id = user.id
    return result


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    check_login_budget(email)
    # Serialize login with credential changes so an old password cannot create
    # a new session after the other sessions have been revoked.
    user = db.scalar(select(User).where(User.email == email).with_for_update())
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect", headers={"WWW-Authenticate": "Bearer"})
    if user.status != "ACTIVE":
        raise HTTPException(status_code=403, detail="This account is unavailable")
    if password_needs_upgrade(user.password_hash):
        user.password_hash = hash_password(payload.password)
    result = issue_session(db, user)
    request.state.activity_user_id = user.id
    return result


@router.post("/logout", status_code=204)
def logout(token=Depends(oauth2_scheme), user=Depends(current_user), db=Depends(get_db)):
    session = db.get(AuthSession, UUID(decode_token_claims(token)["jti"]))
    session.revoked_at = utcnow()
    db.commit()
    return Response(status_code=204)


class AccountEmail(BaseModel):
    email:str=Field(min_length=5,max_length=320)


class VerificationCode(BaseModel):
    code:str=Field(min_length=20,max_length=100)


class ResetPassword(VerificationCode):
    password:str=Field(min_length=12,max_length=128)


def require_account_mail():
    if settings.mail_delivery_mode == "disabled":
        raise HTTPException(status_code=503, detail="El envío de correos está desactivado. La recuperación y la confirmación de cuentas no están disponibles por el momento.")


@router.post("/request-verification")
def request_verification(db=Depends(get_db),user=Depends(current_user)):
    from app.account_mail import issue_token
    if not user.email_verified:
        require_account_mail()
        wait=issue_token(db,user,"VERIFY_EMAIL")
        if wait:
            raise HTTPException(status_code=429, detail="Ya pediste un enlace recientemente. Esperá antes de reenviarlo.", headers={"Retry-After":str(wait)})
        db.commit()
    return {"ok":True, "already_verified":user.email_verified, **({"delivery_mode":"preview"} if settings.mail_delivery_mode=="preview" else {})}


@router.post("/verify-email")
def verify_email(payload:VerificationCode,request:Request,db=Depends(get_db)):
    from app.account_mail import consume_token
    user=consume_token(db,payload.code,"VERIFY_EMAIL")
    email_changed=False
    if user is None:
        user=consume_token(db,payload.code,"CHANGE_EMAIL")
        email_changed=user is not None
    if user is None:
        raise HTTPException(status_code=400,detail="El enlace venció o ya fue usado. Pedí uno nuevo.")
    try:
        user.email_verified_at=utcnow()
        if email_changed:
            user.email=user.pending_email
            user.pending_email=None
            db.execute(update(AccountToken).where(AccountToken.user_id==user.id,AccountToken.consumed_at.is_(None)).values(consumed_at=utcnow(),email_status="CANCELLED"))
            db.execute(update(AuthSession).where(AuthSession.user_id==user.id,AuthSession.revoked_at.is_(None)).values(revoked_at=utcnow()))
        claim_reserved_access(db, user)
        from app.product_analytics import record
        record(db,"email_verified",user.id,request=request,user=user)
        db.execute(update(Notification).where(Notification.owner_id==user.id,Notification.email_status=="PENDING").values(email_available_at=utcnow()))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Ese correo ya está en uso. Elegí otro desde Mi cuenta.") from exc
    return {"ok":True,"email_changed":email_changed}


@router.post("/password-reset")
def password_reset(payload:AccountEmail,db=Depends(get_db)):
    from app.account_mail import issue_token
    require_account_mail()
    email=payload.email.strip().lower()
    user=db.scalar(select(User).where(User.email==email,User.status=="ACTIVE"))
    if user:
        issue_token(db,user,"RESET_PASSWORD")
        db.commit()
    # Do not disclose whether the address belongs to a registered account.
    return {"ok":True, **({"delivery_mode":"preview"} if settings.mail_delivery_mode == "preview" else {})}


@router.post("/reset-password")
def reset_password(payload:ResetPassword,request:Request,db=Depends(get_db)):
    from app.account_mail import consume_token
    user=consume_token(db,payload.code,"RESET_PASSWORD")
    if user is None:
        raise HTTPException(status_code=400,detail="El enlace venció o ya fue usado. Pedí uno nuevo.")
    user.password_hash=hash_password(payload.password)
    user.email_verified_at=utcnow()
    claim_reserved_access(db, user)
    from app.product_analytics import record
    record(db,"email_verified",user.id,request=request,user=user)
    db.execute(update(AuthSession).where(AuthSession.user_id==user.id,AuthSession.revoked_at.is_(None)).values(revoked_at=utcnow()))
    db.execute(update(Notification).where(Notification.owner_id==user.id,Notification.email_status=="PENDING").values(email_available_at=utcnow()))
    db.commit()
    return {"ok":True}


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(current_user)):
    return user


class ContactUpdate(BaseModel):
    model_config=ConfigDict(extra="forbid")
    name: str=Field(min_length=1,max_length=120)
    phone: str | None=Field(default=None,max_length=32)
    email: str=Field(min_length=5,max_length=320)
    password: str | None=Field(default=None,max_length=128)


class AccountDelete(BaseModel):
    model_config=ConfigDict(extra="forbid")
    password: str=Field(min_length=1,max_length=128)
    confirmation: Literal["ELIMINAR"]


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)
    confirm_password: str = Field(min_length=12, max_length=128)


def confirm_password(user, password):
    check_login_budget(user.email)
    if not password or not verify_password(password,user.password_hash):
        raise HTTPException(400,"La contraseña actual no es correcta.")


@router.post("/change-password")
def change_password(payload: PasswordChange, db=Depends(get_db), user=Depends(current_user), token=Depends(oauth2_scheme)):
    from app.account_management import lock_account
    user = lock_account(db, user, token)
    confirm_password(user, payload.current_password)
    if payload.new_password != payload.confirm_password:
        raise HTTPException(422, "Las contraseñas nuevas no coinciden.")
    if payload.new_password == payload.current_password:
        raise HTTPException(422, "Elegí una contraseña diferente de la actual.")
    now = utcnow()
    session_id = UUID(decode_token_claims(token)["jti"])
    user.password_hash = hash_password(payload.new_password)
    db.execute(update(AuthSession).where(
        AuthSession.user_id == user.id, AuthSession.id != session_id,
        AuthSession.revoked_at.is_(None),
    ).values(revoked_at=now))
    db.execute(update(AccountToken).where(
        AccountToken.user_id == user.id, AccountToken.kind == "RESET_PASSWORD",
        AccountToken.consumed_at.is_(None),
    ).values(consumed_at=now, email_status="CANCELLED"))
    db.commit()
    return {"ok": True}


def require_token_budget(db,user,kind):
    from app.account_mail import issue_token
    wait=issue_token(db,user,kind)
    if wait:
        raise HTTPException(429,"Esperá antes de pedir otro enlace.",headers={"Retry-After":str(wait)})


@router.patch("/contact",response_model=UserRead)
def update_contact(payload:ContactUpdate,db=Depends(get_db),user=Depends(current_user),token=Depends(oauth2_scheme)):
    from app.account_management import lock_account
    user=lock_account(db,user,token)
    email=payload.email.strip().lower()
    name=payload.name.strip()
    if not name or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",email):
        raise HTTPException(422,"Revisá el nombre y el correo electrónico.")
    if email!=user.email:
        confirm_password(user,payload.password)
        if db.scalar(select(User.id).where(User.email==email,User.id!=user.id)):
            raise HTTPException(409,"Ese correo ya está en uso.")
        require_account_mail()
        user.pending_email=email
        require_token_budget(db,user,"CHANGE_EMAIL")
    user.name=name
    user.phone=(payload.phone or "").strip() or None
    db.commit()
    db.refresh(user)
    return user


@router.post("/contact/email/resend")
def resend_email_change(db=Depends(get_db),user=Depends(current_user),token=Depends(oauth2_scheme)):
    from app.account_management import lock_account
    user=lock_account(db,user,token)
    if not user.pending_email:
        raise HTTPException(409,"No hay un cambio de correo pendiente.")
    require_account_mail()
    require_token_budget(db,user,"CHANGE_EMAIL")
    db.commit()
    return {"ok":True}


@router.post("/contact/email/cancel",response_model=UserRead)
def cancel_email_change(db=Depends(get_db),user=Depends(current_user),token=Depends(oauth2_scheme)):
    from app.account_management import lock_account
    user=lock_account(db,user,token)
    user.pending_email=None
    db.execute(update(AccountToken).where(AccountToken.user_id==user.id,AccountToken.kind=="CHANGE_EMAIL",AccountToken.consumed_at.is_(None)).values(consumed_at=utcnow(),email_status="CANCELLED"))
    db.commit()
    db.refresh(user)
    return user


@router.delete("/me",status_code=204)
def remove_account(payload:AccountDelete,db=Depends(get_db),user=Depends(current_user),token=Depends(oauth2_scheme)):
    from app.account_management import lock_account,delete_account
    user=lock_account(db,user,token)
    confirm_password(user,payload.password)
    delete_account(db,user)
    return Response(status_code=204)


@router.patch("/notification-preferences", response_model=UserRead)
def notification_preferences(payload: NotificationPreferences, user: User = Depends(current_user), db: Session = Depends(get_db)):
    user.notification_preferences = {**user.notification_preferences, "email": payload.email}
    db.commit()
    db.refresh(user)
    return user

