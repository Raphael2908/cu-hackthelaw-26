from __future__ import annotations

from celery.signals import task_postrun, task_prerun

from app.core.context import set_agent_run_id, set_task_id


@task_prerun.connect
def _bind_context(task_id=None, task=None, args=None, kwargs=None, **_extra):  # noqa: ANN001
    # First positional arg of every stage task is the domain task_id.
    if args:
        set_task_id(str(args[0]))


@task_postrun.connect
def _clear_context(**_extra):  # noqa: ANN001
    set_task_id(None)
    set_agent_run_id(None)
