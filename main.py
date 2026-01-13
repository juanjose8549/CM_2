from fastapi import FastAPI, HTTPException, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models import User, UserUpdate
import bcrypt
from datetime import datetime
from database import get_db, session, audit_collection, engine, Base

app = FastAPI()

Base.metadata.create_all(engine)

db = get_db()

@app.patch("/users/{user_id}")
def update_user(
    user_id: int,
    update: UserUpdate,
    updater_id: int = Header(..., alias="X-User-ID")
):
    result = db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate
    if update.password is not None and not update.password.strip():
        raise HTTPException(status_code=400, detail="Invalid password")
    if update.is_active is not None and not isinstance(update.is_active, bool):
        raise HTTPException(status_code=400, detail="Invalid is_active")

    # Update fields
    if update.name is not None:
        user.name = update.name
    if update.surname is not None:
        user.surname = update.surname
    if update.password is not None:
        user.password_hash = bcrypt.hashpw(update.password.encode(), bcrypt.gensalt()).decode()
    if update.is_active is not None:
        user.is_active = update.is_active

    user.updated_by = updater_id
    user.updated_at = datetime.utcnow()

    db.commit()

    changes = {k: v for k, v in update.dict(exclude_unset=True).items() if k != 'password'}
    if 'password' in update.dict(exclude_unset=True):
        changes['password_updated'] = True

    log = {
        "user_id": user_id,
        "updated_by": updater_id,
        "updated_at": user.updated_at.isoformat(),
        "changes": changes
    }
    audit_collection.insert_one(log)

    return {"message": "User updated successfully"}