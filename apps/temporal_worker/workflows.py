from temporalio import workflow
from datetime import timedelta
from apps.temporal_worker.postmortem import PostmortemWorkflow


@workflow.defn
class TraderWorkflow:
    @workflow.run
    async def run(self, proposal: dict):
        # Import heavy modules lazily to avoid sandbox import issues
        from apps.temporal_worker import activities as acts
        ok = await workflow.execute_activity(
            acts.verify_evidence,
            proposal["evidence"],
            start_to_close_timeout=30,
            retry_policy=workflow.RetryPolicy(maximum_attempts=3),
        )
        if not ok:
            return {"status": "rejected", "reason": "evidence_failed"}

        gated = await workflow.execute_activity(
            acts.gate_policy,
            proposal,
            start_to_close_timeout=10,
            retry_policy=workflow.RetryPolicy(maximum_attempts=3),
        )
        if not gated:
            return {"status": "rejected", "reason": "policy_denied"}

        # ASLF attention/liquidity gate
        aslf = await workflow.execute_activity(
            acts.compute_aslf_activity,
            proposal,
            start_to_close_timeout=20,
        )
        if aslf.get("decision") != "allow":
            return {"status": "rejected", "reason": "aslf_denied", "aslf": aslf}

        # Venue rules pre-check
        rules_ok = await workflow.execute_activity(
            acts.validate_venue_rules,
            proposal,
            start_to_close_timeout=15,
        )
        if not rules_ok:
            return {"status": "rejected", "reason": "venue_rules"}

        # Re-verify evidence integrity before executing
        ok2 = await workflow.execute_activity(
            acts.reverify_evidence,
            proposal["evidence"],
            start_to_close_timeout=20,
            retry_policy=workflow.RetryPolicy(maximum_attempts=2),
        )
        if not ok2:
            return {"status": "rejected", "reason": "evidence_changed"}

        # Risk sizing via fractional Kelly (scaffold)
        # Inject ASLF for sizing
        prop2 = dict(proposal)
        prop2["_aslf"] = float(aslf.get("aslf", 0.0))
        quote_qty = await workflow.execute_activity(
            acts.compute_trade_size,
            prop2,
            start_to_close_timeout=10,
        )

        # Pass idempotency based on workflow id + symbol
        idem = f"{workflow.info().workflow_id}:{proposal.get('symbol','')}"
        exec_res = await workflow.execute_activity(
            acts.call_executor,
            {"proposal": proposal, "idempotency_key": idem, "quote_qty": quote_qty},
            start_to_close_timeout=30,
            retry_policy=workflow.RetryPolicy(maximum_attempts=3),
        )
        # Record execution
        await workflow.execute_activity(acts.record_execution, idem, proposal, exec_res, start_to_close_timeout=20)
        # Derive entry price best-effort for postmortem
        entry_price = None
        try:
            body = exec_res.get("body", {})
            entry_price = float(body.get("avg_price") or body.get("fills", [{}])[0].get("price"))
        except Exception:
            entry_price = None
        if entry_price:
            # Update equity immediately and start postmortem
            await workflow.execute_activity(acts.update_equity_stats, proposal.get("symbol", "BTCUSDT"), entry_price, start_to_close_timeout=15)
            await workflow.start_child_workflow(PostmortemWorkflow.run, proposal.get("symbol", "BTCUSDT"), entry_price, int(proposal.get("horizon_minutes", 1)), idem)
        return {"status": "submitted", "execution": exec_res}


