import asyncio, time
from temporalio.client import Client
from apps.agent_brain.graph import compiled
from apps.temporal_worker.workflows import TraderWorkflow


async def main():
    # Build a proposal using the agent stub
    draft = {"text": "Demo headline: BTC ETF inflows"}
    result = compiled.invoke(draft)
    proposal = result["proposal"]

    client = await Client.connect("localhost:7233")
    wf_id = f"demo-{int(time.time())}"
    handle = await client.start_workflow(
        TraderWorkflow.run,
        proposal,
        id=wf_id,
        task_queue="trader-tq",
    )
    out = await handle.result()
    print({"workflow_id": wf_id, "result": out})


if __name__ == "__main__":
    asyncio.run(main())


