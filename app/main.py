
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST
import sqlite3

from app.database import init_db, get_connection, get_all_tasks
from app.models import TaskCreate, TaskUpdate


app = FastAPI(
    title="TaskFlow API",
    description="API de gestion de tâches avec observabilité",
    version="1.0.0"
)

# Métriques Prometheus
tasks_created = Counter(
    "taskflow_tasks_created_total",
    "Nombre total de tâches créées"
)

tasks_deleted = Counter(
    "taskflow_tasks_deleted_total",
    "Nombre total de tâches supprimées"
)

tasks_completed = Counter(
    "taskflow_tasks_completed_total",
    "Nombre total de tâches terminées"
)

tasks_pending = Gauge(
    "taskflow_tasks_pending",
    "Nombre de tâches en attente"
)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/")
def home():
    return {
        "application": "TaskFlow",
        "message": "Bienvenue sur TaskFlow !",
        "status": "running"
    }


@app.get("/api/tasks")
def list_tasks():
    return get_all_tasks()


@app.post("/api/tasks", status_code=201)
def create_task(task: TaskCreate):
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO tasks (title, description)
            VALUES (?, ?)
            """,
            (task.title, task.description)
        )
        task_id = cursor.lastrowid
        connection.commit()

        new_task = connection.execute(
            "SELECT * FROM tasks WHERE id = ?",
            (task_id,)
        ).fetchone()

    tasks_created.inc()
    return dict(new_task)


@app.patch("/api/tasks/{task_id}")
def update_task(task_id: int, task: TaskUpdate):
    changes = task.model_dump(exclude_unset=True)

    if not changes:
        raise HTTPException(400, "Aucune modification fournie")

    with get_connection() as connection:
        existing = connection.execute(
            "SELECT * FROM tasks WHERE id = ?",
            (task_id,)
        ).fetchone()

        if existing is None:
            raise HTTPException(404, "Tâche introuvable")

        was_completed = existing["status"] == "completed"

        allowed = {"title", "description", "status"}
        for field, value in changes.items():
            if field not in allowed:
                continue

            connection.execute(
                f"UPDATE tasks SET {field} = ? WHERE id = ?",
                (value, task_id)
            )

        updated = connection.execute(
            "SELECT * FROM tasks WHERE id = ?",
            (task_id,)
        ).fetchone()

        connection.commit()

    if not was_completed and updated["status"] == "completed":
        tasks_completed.inc()

    return dict(updated)


@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: int):
    with get_connection() as connection:
        cursor = connection.execute(
            "DELETE FROM tasks WHERE id = ?",
            (task_id,)
        )
        connection.commit()

        if cursor.rowcount == 0:
            raise HTTPException(404, "Tâche introuvable")

    tasks_deleted.inc()
    return {"message": "Tâche supprimée avec succès"}


@app.get("/api/stats")
def get_stats():
    with get_connection() as connection:
        total = connection.execute(
            "SELECT COUNT(*) FROM tasks"
        ).fetchone()[0]

        completed = connection.execute(
            "SELECT COUNT(*) FROM tasks WHERE status = 'completed'"
        ).fetchone()[0]

    pending = total - completed
    return {
        "total": total,
        "completed": completed,
        "pending": pending
    }


@app.get("/metrics")
def metrics():
    with get_connection() as connection:
        pending = connection.execute(
            "SELECT COUNT(*) FROM tasks WHERE status = 'pending'"
        ).fetchone()[0]

    tasks_pending.set(pending)

    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )
