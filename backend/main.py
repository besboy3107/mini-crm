import os
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .database import CRMDatabase
from .schemas import (
    ClientCreate, ClientOut, ClientUpdate,
    DealCreate, DealOut, DealUpdate,
    StatsOut,
    TaskCreate, TaskOut, TaskUpdate,
)

DB_URL = os.getenv("DATABASE_URL", "sqlite:///data/crm.db")
db = CRMDatabase(db_url=DB_URL)

app = FastAPI(title="Mini CRM API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/stats", response_model=StatsOut)
def get_stats():
    return db.get_stats()


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------

@app.post("/api/clients", response_model=ClientOut, status_code=201)
def create_client(body: ClientCreate):
    return db.create_client(**body.model_dump())


@app.get("/api/clients", response_model=List[ClientOut])
def list_clients(
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
):
    return db.list_clients(status=status, search=search, limit=limit, offset=offset)


@app.get("/api/clients/{client_id}", response_model=ClientOut)
def get_client(client_id: int):
    client = db.get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@app.patch("/api/clients/{client_id}", response_model=ClientOut)
def update_client(client_id: int, body: ClientUpdate):
    updated = db.update_client(client_id, **body.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Client not found")
    return updated


@app.delete("/api/clients/{client_id}", status_code=204)
def delete_client(client_id: int):
    if not db.delete_client(client_id):
        raise HTTPException(status_code=404, detail="Client not found")


# ---------------------------------------------------------------------------
# Deals
# ---------------------------------------------------------------------------

@app.post("/api/deals", response_model=DealOut, status_code=201)
def create_deal(body: DealCreate):
    return db.create_deal(**body.model_dump())


@app.get("/api/deals", response_model=List[DealOut])
def list_deals(
    client_id: Optional[int] = None,
    stage: Optional[str] = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
):
    return db.list_deals(client_id=client_id, stage=stage, limit=limit, offset=offset)


@app.get("/api/deals/{deal_id}", response_model=DealOut)
def get_deal(deal_id: int):
    deal = db.get_deal(deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    return deal


@app.patch("/api/deals/{deal_id}", response_model=DealOut)
def update_deal(deal_id: int, body: DealUpdate):
    updated = db.update_deal(deal_id, **body.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Deal not found")
    return updated


@app.delete("/api/deals/{deal_id}", status_code=204)
def delete_deal(deal_id: int):
    if not db.delete_deal(deal_id):
        raise HTTPException(status_code=404, detail="Deal not found")


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

@app.post("/api/tasks", response_model=TaskOut, status_code=201)
def create_task(body: TaskCreate):
    return db.create_task(**body.model_dump())


@app.get("/api/tasks", response_model=List[TaskOut])
def list_tasks(
    client_id: Optional[int] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
):
    return db.list_tasks(client_id=client_id, status=status, priority=priority, limit=limit, offset=offset)


@app.get("/api/tasks/{task_id}", response_model=TaskOut)
def get_task(task_id: int):
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.patch("/api/tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: int, body: TaskUpdate):
    updated = db.update_task(task_id, **body.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Task not found")
    return updated


@app.delete("/api/tasks/{task_id}", status_code=204)
def delete_task(task_id: int):
    if not db.delete_task(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
