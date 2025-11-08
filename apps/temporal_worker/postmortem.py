from temporalio import workflow
from datetime import timedelta
# Import heavy modules lazily inside the workflow run to avoid sandbox import issues


@workflow.defn
class PostmortemWorkflow:
    @workflow.run
    async def run(self, symbol: str, entry_price: float, horizon_minutes: int, order_id: str):
        # Sleep for horizon (shortened to avoid long waits in scaffold)
        wait_seconds = min(5, max(1, int(horizon_minutes)))
        await workflow.sleep(timedelta(seconds=wait_seconds))
        from apps.temporal_worker import activities as acts
        res = await workflow.execute_activity(acts.compute_counterfactual, symbol, entry_price, start_to_close_timeout=20)
        await workflow.execute_activity(acts.update_postmortem, order_id, res, start_to_close_timeout=20)
        return {"symbol": symbol, "entry_price": entry_price, **res}


