"""
Session manager for Jinclaw — conversation persistence via SQLite.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from sqlOrm import JinclawSession as JinclawSessionModel


class JinclawSessionManager:
    """CRUD wrapper around the JinclawSession ORM model."""

    def __init__(self, db: Session):
        self.db = db

    def create_session(self, user_id: int, name: str = "新建会话",
                       workspace_dir: Optional[str] = None) -> int:
        """Create a new session and return its ID."""
        session = JinclawSessionModel(
            user_id=user_id,
            session_name=name or "新建会话",
            messages=[],
            workspace_dir=workspace_dir,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session.id

    def get_session(self, session_id: int, user_id: Optional[int] = None) -> Optional[Dict]:
        """Get session details including messages."""
        query = self.db.query(JinclawSessionModel).filter(
            JinclawSessionModel.id == session_id
        )
        if user_id:
            query = query.filter(JinclawSessionModel.user_id == user_id)
        s = query.first()
        if not s:
            return None
        return {
            "id": s.id,
            "name": s.session_name,
            "messages": s.messages or [],
            "workspace_dir": s.workspace_dir,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        }

    def list_sessions(self, user_id: int) -> List[Dict[str, Any]]:
        """List all sessions for a user, newest first."""
        sessions = (
            self.db.query(JinclawSessionModel)
            .filter(JinclawSessionModel.user_id == user_id)
            .order_by(JinclawSessionModel.updated_at.desc())
            .all()
        )
        return [
            {
                "id": s.id,
                "name": s.session_name,
                "message_count": len(s.messages or []),
                "workspace_dir": s.workspace_dir,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            }
            for s in sessions
        ]

    def update_messages(self, session_id: int, messages: List[Dict],
                        user_id: Optional[int] = None):
        """Update the messages array for a session."""
        query = self.db.query(JinclawSessionModel).filter(
            JinclawSessionModel.id == session_id
        )
        if user_id:
            query = query.filter(JinclawSessionModel.user_id == user_id)
        s = query.first()
        if s:
            s.messages = messages
            s.updated_at = datetime.now()
            self.db.commit()

    def rename_session(self, session_id: int, user_id: int, name: str):
        """Rename a session."""
        s = (
            self.db.query(JinclawSessionModel)
            .filter(
                JinclawSessionModel.id == session_id,
                JinclawSessionModel.user_id == user_id,
            )
            .first()
        )
        if s:
            s.session_name = name[:100]
            s.updated_at = datetime.now()
            self.db.commit()

    def delete_session(self, session_id: int, user_id: int):
        """Delete a session."""
        s = (
            self.db.query(JinclawSessionModel)
            .filter(
                JinclawSessionModel.id == session_id,
                JinclawSessionModel.user_id == user_id,
            )
            .first()
        )
        if s:
            self.db.delete(s)
            self.db.commit()
