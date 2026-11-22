"""Projects and their tasks (a task belongs to exactly one project)."""

from fastapi import APIRouter, Response
from pydantic import Field

from app.ok.common import StrictModel, not_found
from app.store import Store


class ProjectInput(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class TaskInput(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    done: bool = False


def build(store: Store) -> APIRouter:
    router = APIRouter()

    def project_record(id_: str, body: ProjectInput) -> dict:
        # description is optional in the spec, so omit it rather than send null.
        return {"id": id_, **body.model_dump(exclude_none=True)}

    async def require_project(project_id: str) -> None:
        if await store.get("projects", project_id) is None:
            raise not_found("project", project_id)

    async def require_task(project_id: str, task_id: str) -> dict:
        await require_project(project_id)
        task = await store.get("tasks", task_id)
        if task is None or task["projectId"] != project_id:
            raise not_found("task", task_id)
        return task

    # --- projects ---

    @router.get("/projects")
    async def list_projects() -> dict:
        items = await store.list("projects")
        return {"items": items, "total": len(items)}

    @router.post("/projects", status_code=201)
    async def create_project(body: ProjectInput) -> dict:
        return await store.create_auto("projects", "pr", body.model_dump(exclude_none=True))

    @router.get("/projects/{project_id}")
    async def get_project(project_id: str) -> dict:
        project = await store.get("projects", project_id)
        if project is None:
            raise not_found("project", project_id)
        return project

    @router.put("/projects/{project_id}")
    async def replace_project(project_id: str, body: ProjectInput) -> dict:
        record = project_record(project_id, body)
        if not await store.update("projects", project_id, record):
            raise not_found("project", project_id)
        return record

    @router.delete("/projects/{project_id}", status_code=204)
    async def delete_project(project_id: str) -> Response:
        if not await store.delete("projects", project_id):
            raise not_found("project", project_id)
        # Interim rule: tasks go with their project. Phase 2 business rules
        # replace this with 409 (open tasks) / ?cascade=true.
        for task in await store.list("tasks"):
            if task["projectId"] == project_id:
                await store.delete("tasks", task["id"])
        return Response(status_code=204)

    # --- tasks ---

    @router.get("/projects/{project_id}/tasks")
    async def list_tasks(project_id: str) -> dict:
        await require_project(project_id)
        items = [t for t in await store.list("tasks") if t["projectId"] == project_id]
        return {"items": items, "total": len(items)}

    @router.post("/projects/{project_id}/tasks", status_code=201)
    async def create_task(project_id: str, body: TaskInput) -> dict:
        await require_project(project_id)
        return await store.create_auto("tasks", "t", {"projectId": project_id, **body.model_dump()})

    @router.get("/projects/{project_id}/tasks/{task_id}")
    async def get_task(project_id: str, task_id: str) -> dict:
        return await require_task(project_id, task_id)

    @router.put("/projects/{project_id}/tasks/{task_id}")
    async def replace_task(project_id: str, task_id: str, body: TaskInput) -> dict:
        await require_task(project_id, task_id)
        record = {"id": task_id, "projectId": project_id, **body.model_dump()}
        await store.update("tasks", task_id, record)
        return record

    @router.delete("/projects/{project_id}/tasks/{task_id}", status_code=204)
    async def delete_task(project_id: str, task_id: str) -> Response:
        await require_task(project_id, task_id)
        await store.delete("tasks", task_id)
        return Response(status_code=204)

    return router
