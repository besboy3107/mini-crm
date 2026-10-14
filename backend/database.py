from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import List, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base, Client, Deal, Task

_engine = None
_SessionLocal = None


def get_engine(db_url: str = "sqlite:///data/crm.db"):
    global _engine, _SessionLocal
    if _engine is None:
        _engine = create_engine(db_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(_engine)
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


@contextmanager
def get_db(db_url: str = "sqlite:///data/crm.db"):
    get_engine(db_url)
    session: Session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------

class CRMDatabase:
    def __init__(self, db_url: str = "sqlite:///data/crm.db"):
        self.db_url = db_url
        get_engine(db_url)

    # --- clients ---

    def create_client(self, **kwargs) -> Client:
        with get_db(self.db_url) as db:
            client = Client(**kwargs)
            db.add(client)
            db.flush()
            db.refresh(client)
            return client

    def get_client(self, client_id: int) -> Optional[Client]:
        with get_db(self.db_url) as db:
            return db.query(Client).filter(Client.id == client_id).first()

    def list_clients(
        self,
        status: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Client]:
        with get_db(self.db_url) as db:
            q = db.query(Client)
            if status:
                q = q.filter(Client.status == status)
            if search:
                like = f"%{search}%"
                q = q.filter(
                    Client.name.ilike(like)
                    | Client.email.ilike(like)
                    | Client.company.ilike(like)
                )
            return q.order_by(Client.created_at.desc()).offset(offset).limit(limit).all()

    def update_client(self, client_id: int, **kwargs) -> Optional[Client]:
        with get_db(self.db_url) as db:
            client = db.query(Client).filter(Client.id == client_id).first()
            if not client:
                return None
            for k, v in kwargs.items():
                setattr(client, k, v)
            client.updated_at = datetime.utcnow()
            db.flush()
            db.refresh(client)
            return client

    def delete_client(self, client_id: int) -> bool:
        with get_db(self.db_url) as db:
            client = db.query(Client).filter(Client.id == client_id).first()
            if not client:
                return False
            db.delete(client)
            return True

    # --- deals ---

    def create_deal(self, **kwargs) -> Deal:
        with get_db(self.db_url) as db:
            deal = Deal(**kwargs)
            db.add(deal)
            db.flush()
            db.refresh(deal)
            return deal

    def get_deal(self, deal_id: int) -> Optional[Deal]:
        with get_db(self.db_url) as db:
            return db.query(Deal).filter(Deal.id == deal_id).first()

    def list_deals(
        self,
        client_id: Optional[int] = None,
        stage: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Deal]:
        with get_db(self.db_url) as db:
            q = db.query(Deal)
            if client_id:
                q = q.filter(Deal.client_id == client_id)
            if stage:
                q = q.filter(Deal.stage == stage)
            return q.order_by(Deal.created_at.desc()).offset(offset).limit(limit).all()

    def update_deal(self, deal_id: int, **kwargs) -> Optional[Deal]:
        with get_db(self.db_url) as db:
            deal = db.query(Deal).filter(Deal.id == deal_id).first()
            if not deal:
                return None
            for k, v in kwargs.items():
                setattr(deal, k, v)
            deal.updated_at = datetime.utcnow()
            db.flush()
            db.refresh(deal)
            return deal

    def delete_deal(self, deal_id: int) -> bool:
        with get_db(self.db_url) as db:
            deal = db.query(Deal).filter(Deal.id == deal_id).first()
            if not deal:
                return False
            db.delete(deal)
            return True

    # --- tasks ---

    def create_task(self, **kwargs) -> Task:
        with get_db(self.db_url) as db:
            task = Task(**kwargs)
            db.add(task)
            db.flush()
            db.refresh(task)
            return task

    def get_task(self, task_id: int) -> Optional[Task]:
        with get_db(self.db_url) as db:
            return db.query(Task).filter(Task.id == task_id).first()

    def list_tasks(
        self,
        client_id: Optional[int] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Task]:
        with get_db(self.db_url) as db:
            q = db.query(Task)
            if client_id:
                q = q.filter(Task.client_id == client_id)
            if status:
                q = q.filter(Task.status == status)
            if priority:
                q = q.filter(Task.priority == priority)
            return q.order_by(Task.created_at.desc()).offset(offset).limit(limit).all()

    def update_task(self, task_id: int, **kwargs) -> Optional[Task]:
        with get_db(self.db_url) as db:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                return None
            for k, v in kwargs.items():
                setattr(task, k, v)
            task.updated_at = datetime.utcnow()
            db.flush()
            db.refresh(task)
            return task

    def delete_task(self, task_id: int) -> bool:
        with get_db(self.db_url) as db:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                return False
            db.delete(task)
            return True

    # --- stats ---

    def get_stats(self) -> dict:
        with get_db(self.db_url) as db:
            total_clients = db.query(Client).count()
            active_clients = db.query(Client).filter(Client.status == "active").count()
            total_deals = db.query(Deal).count()
            won_deals = db.query(Deal).filter(Deal.stage == "won").count()
            open_tasks = db.query(Task).filter(Task.status != "done").count()

            from sqlalchemy import func
            revenue = (
                db.query(func.sum(Deal.amount))
                .filter(Deal.stage == "won")
                .scalar()
            ) or 0.0

            pipeline = (
                db.query(func.sum(Deal.amount))
                .filter(Deal.stage.in_(["new", "negotiation"]))
                .scalar()
            ) or 0.0

            return {
                "total_clients": total_clients,
                "active_clients": active_clients,
                "total_deals": total_deals,
                "won_deals": won_deals,
                "open_tasks": open_tasks,
                "revenue": round(revenue, 2),
                "pipeline": round(pipeline, 2),
            }
