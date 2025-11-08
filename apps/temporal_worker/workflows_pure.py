from temporalio import workflow
from typing import Any, Dict, Optional
from datetime import timedelta


@workflow.defn
class TraderWorkflow:
    @workflow.run
    async def run(self, proposal: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        with workflow.unsafe.imports_passed_through():
            from apps.temporal_worker import activities as acts

        # Allow empty/manual starts from UI: fall back to a safe stub proposal
        if not proposal:
            proposal = {
                "action": "open",
                "symbol": "BTCUSDT",
                "side": "buy",
                "size_bps_equity": 4.0,
                "horizon_minutes": 120,
                "thesis": "stub",
                "risk": {"stop_loss_bps": 60, "take_profit_bps": 120, "max_slippage_bps": 3},
                "evidence": [{"url": "https://www.binance.com/en/support/announcement", "type": "exchange_status"}],
                "confidence": 0.7,
            }

        # Collect docs (RAG)
        docs = await workflow.execute_activity(
            acts.collect_docs, proposal, start_to_close_timeout=timedelta(seconds=30)
        )

        # Verify evidence (provenance + hash/C2PA)
        ver = await workflow.execute_activity(
            acts.verify_evidence, proposal.get("evidence", []), start_to_close_timeout=timedelta(seconds=60)
        )
        if not ver:
            return {"status": "denied", "reason": "evidence_failed"}

        # ASLF attention/liquidity gate
        aslf = await workflow.execute_activity(
            acts.compute_aslf_activity, proposal, start_to_close_timeout=timedelta(seconds=15)
        )
        gate = await workflow.execute_activity(
            acts.gate_policy, {**proposal, "_aslf": aslf.get("aslf")}, start_to_close_timeout=timedelta(seconds=10)
        )
        if not gate:
            return {"status": "denied", "reason": "policy_denied", "aslf": aslf}

        # Risk simulation guard
        risk_ok = await workflow.execute_activity(acts.risk_simulate, proposal, start_to_close_timeout=timedelta(seconds=15))
        if not risk_ok.get("ok"):
            return {"status": "denied", "reason": "risk_sim_denied", "sim": risk_ok}

        # Probe->Promote bandit for size multiplier
        band = await workflow.execute_activity(acts.bandit_decide, proposal, start_to_close_timeout=timedelta(seconds=5))

        # Choose execution style
        choice = await workflow.execute_activity(acts.choose_execution, proposal, 25.0, start_to_close_timeout=timedelta(seconds=10))
        # Size selection (probe override uses PROBE_SIZE_BPS)
        force_bps = float(band.get("probe_bps", 0.0)) if band.get("is_probe") else None
        quote_base = await workflow.execute_activity(acts.compute_trade_size, {**proposal, "_aslf": aslf.get("aslf")}, start_to_close_timeout=timedelta(seconds=10), force_probe_bps=force_bps)
        quote_qty = max(5.0, quote_base * float(band.get("size_multiplier", 1.0))) if force_bps is None else quote_base
        context = {"aslf": aslf.get("aslf"), "style": choice.get("style"), "impact_bps": choice.get("impact_bps")}
        if choice.get("style") == "MARKET":
            exec_res = await workflow.execute_activity(acts.call_executor, {"proposal": proposal, "idempotency_key": f"wf-{proposal.get('symbol','')}", "quote_qty": quote_qty}, start_to_close_timeout=timedelta(seconds=30))
        else:
            await workflow.start_child_workflow("MetaOrderWorkflow", {"proposal": proposal, "slices": choice.get("slices", 3), "quote_qty": quote_qty}, id=f"meta-{workflow.info().workflow_id}", task_queue="trader-tq")
            exec_res = {"code": 202, "body": {"status": "sliced", "symbol": proposal.get("symbol"), "order_id": None}}
        await workflow.execute_activity(acts.attribute_trade, exec_res, context, start_to_close_timeout=timedelta(seconds=10))
        # Record hypothesis outcome (bandit upsert)
        # Build minimal exec_ctx with status and symbol
        exec_ctx = {"status": (exec_res.get("body", {}) or {}).get("status"), "symbol": proposal.get("symbol")}
        await workflow.execute_activity(acts.record_hypothesis_outcome, exec_ctx, start_to_close_timeout=timedelta(seconds=10))

        # Postmortem enqueue as activity (can compute immediately or schedule)
        await workflow.execute_activity(
            acts.postmortem_enqueue, exec_res, start_to_close_timeout=timedelta(seconds=10)
        )
        return {"status": "executed", "order": exec_res}


@workflow.defn
class PostmortemWorkflow:
    @workflow.run
    async def run(self, exec_result: Dict[str, Any]) -> None:
        with workflow.unsafe.imports_passed_through():
            from apps.temporal_worker import activities as acts
        await workflow.execute_activity(
            acts.compute_counterfactual, exec_result, start_to_close_timeout=timedelta(seconds=30)
        )

@workflow.defn
class MetaOrderWorkflow:
    @workflow.run
    async def run(self, params: Dict[str, Any]) -> None:
        with workflow.unsafe.imports_passed_through():
            from apps.temporal_worker import activities as acts
        proposal = params.get("proposal", {})
        slices = int(params.get("slices", 3))
        quote_qty = float(params.get("quote_qty", 20))
        per_slice = max(1.0, quote_qty / max(1, slices))
        for i in range(slices):
            await workflow.execute_activity(acts.call_executor, {"proposal": proposal, "idempotency_key": f"slice-{i}-{proposal.get('symbol','')}", "quote_qty": per_slice}, start_to_close_timeout=timedelta(seconds=20))
            await workflow.sleep(timedelta(seconds=1))


