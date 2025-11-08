import asyncio
import pytest
from temporalio.client import Client
from apps.agent_brain.graph import compiled
from apps.temporal_worker.workflows import TraderWorkflow


@pytest.mark.asyncio
async def test_workflow_happy_path(monkeypatch):
    # Ensure dry_run
    monkeypatch.setenv("EXEC_MODE", "dry_run")
    # Proposal via agent stub
    result = compiled.invoke({"text": "Demo"})
    proposal = result["proposal"]
    # Connect to local Temporal (assumes compose running)
    client = await Client.connect("localhost:7233")
    handle = await client.start_workflow(
        TraderWorkflow.run,
        proposal,
        id="test-wf",
        task_queue="trader-tq",
    )
    out = await handle.result()
    assert out["status"] == "submitted"

