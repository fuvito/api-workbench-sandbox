"""Projects and their tasks (a task belongs to exactly one project)."""

from fastapi import APIRouter, Depends, Header, Response
from pydantic import Field

from app.ok.common import (
    ApiError,
    BoolText,
    Page,
    PatchModel,
    StrictModel,
    as_bool,
    check_if_match,
    not_found,
    paged,
    with_etag,
)
from app.ok.listing import get_page
from app.store import Store


class ProjectInput(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class ProjectPatch(PatchModel):
    name: str = Field(default=None, min_length=1, max_length=100)
    description: str = Field(default=None, max_length=500)


class TaskInput(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    done: bool = False


class TaskPatch(PatchModel):
    title: str = Field(default=None, min_length=1, max_length=200)
    done: bool = Field(default=None)


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
    async def list_projects(response: Response, page: Page = Depends(get_page)) -> dict:
        return paged(await store.list("projects"), page, response)

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

    @router.patch("/projects/{project_id}")
    async def update_project(project_id: str, body: ProjectPatch) -> dict:
        project = await store.get("projects", project_id)
        if project is None:
            raise not_found("project", project_id)
        project.update(body.changes())
        await store.update("projects", project_id, project)
        return project

    @router.delete("/projects/{project_id}", status_code=204)
    async def delete_project(project_id: str, cascade: BoolText | None = None) -> Response:
        """A project with open tasks (not done) is protected: 409, unless ?cascade=true.
        Whenever the delete goes through, the project's remaining tasks go with it."""
        async with store.tx() as tx:
            if tx.get("projects", project_id) is None:
                raise not_found("project", project_id)
            tasks = [t for t in tx.list("tasks") if t["projectId"] == project_id]
            open_tasks = [t for t in tasks if not t["done"]]
            if open_tasks and not as_bool(cascade):
                raise ApiError(
                    409,
                    "has_open_tasks",
                    f"project {project_id!r} has {len(open_tasks)} open task(s); use ?cascade=true",
                )
            for task in tasks:
                tx.delete("tasks", task["id"])
            tx.delete("projects", project_id)
        return Response(status_code=204)

    # --- tasks ---

    @router.get("/projects/{project_id}/tasks")
    async def list_tasks(
        project_id: str,
        response: Response,
        page: Page = Depends(get_page),
        done: BoolText | None = None,
    ) -> dict:
        await require_project(project_id)
        items = [t for t in await store.list("tasks") if t["projectId"] == project_id]
        if as_bool(done) is not None:
            items = [t for t in items if t["done"] == as_bool(done)]
        return paged(items, page, response)

    @router.post("/projects/{project_id}/tasks", status_code=201)
    async def create_task(project_id: str, body: TaskInput, response: Response) -> dict:
        await require_project(project_id)
        task = await store.create_auto(
            "tasks", "t", {"projectId": project_id, **body.model_dump()}
        )
        return with_etag(response, task)

    @router.get("/projects/{project_id}/tasks/{task_id}")
    async def get_task(project_id: str, task_id: str, response: Response) -> dict:
        return with_etag(response, await require_task(project_id, task_id))

    # On tasks If-Match is optional: when sent it must match (412), when absent the write
    # goes through. Orders make it mandatory (428).

    @router.put("/projects/{project_id}/tasks/{task_id}")
    async def replace_task(
        project_id: str,
        task_id: str,
        body: TaskInput,
        response: Response,
        if_match: str | None = Header(default=None),
    ) -> dict:
        current = await require_task(project_id, task_id)
        check_if_match(if_match, current, required=False)
        record = {"id": task_id, "projectId": project_id, **body.model_dump()}
        await store.update("tasks", task_id, record)
        return with_etag(response, record)

    @router.patch("/projects/{project_id}/tasks/{task_id}")
    async def update_task(
        project_id: str,
        task_id: str,
        body: TaskPatch,
        response: Response,
        if_match: str | None = Header(default=None),
    ) -> dict:
        task = await require_task(project_id, task_id)
        check_if_match(if_match, task, required=False)
        task.update(body.changes())
        await store.update("tasks", task_id, task)
        return with_etag(response, task)

    @router.delete("/projects/{project_id}/tasks/{task_id}", status_code=204)
    async def delete_task(project_id: str, task_id: str) -> Response:
        await require_task(project_id, task_id)
        await store.delete("tasks", task_id)
        return Response(status_code=204)

    return router
