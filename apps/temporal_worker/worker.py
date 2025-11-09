import asyncio
from temporalio.client import Client
from temporalio.worker import Worker
from apps.temporal_worker.workflows_pure import TraderWorkflow, PostmortemWorkflow, MetaOrderWorkflow
from apps.temporal_worker.activities import (
    collect_docs,
    verify_evidence,
    compute_aslf_activity,
    gate_policy,
    call_executor,
    postmortem_enqueue,
    compute_counterfactual,
    bandit_decide,
    risk_simulate,
    choose_execution,
    attribute_trade,
    compute_trade_size,
    record_hypothesis_outcome,
)


async def main():
    # Get Temporal address from env or default
    import os
    temporal_address = os.getenv("TEMPORAL_ADDRESS", "temporal:7233")
    
    # Robust connect: wait for Temporal to be ready
    attempt = 0
    delay = 1
    while True:
        try:
            client = await Client.connect(temporal_address)
            break
        except Exception as e:
            attempt += 1
            if attempt > 60:
                print(f"Failed to connect to Temporal at {temporal_address} after 60 attempts")
                raise
            if attempt % 10 == 0:
                print(f"Waiting for Temporal at {temporal_address}... (attempt {attempt})")
            await asyncio.sleep(delay)
            delay = min(delay * 2, 5)
    worker = Worker(
        client,
        task_queue="trader-tq",
        workflows=[TraderWorkflow, PostmortemWorkflow, MetaOrderWorkflow],
        activities=[collect_docs, verify_evidence, compute_aslf_activity, gate_policy, call_executor, postmortem_enqueue, compute_counterfactual, bandit_decide, risk_simulate, choose_execution, attribute_trade, compute_trade_size, record_hypothesis_outcome],
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())


