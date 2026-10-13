import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from core.account_manager import MultiAccountContextManager, AccountProfile, AccountHealth

logger = logging.getLogger("AccountPoolManager")


class EnterpriseAccountPool:
    """
    Enterprise-Grade Account Pool with Automated Failover & Cooldown Recovery.
    1. Distributes scraping and distribution velocity across multiple accounts (Round-Robin).
    2. Automatic Cooldown Management: When an account receives a 429 or checkpoint,
       it is automatically quarantined for a cooldown window (default 90 mins) and
       the pool immediately fails over to healthy standby accounts.
    3. Session Freshness & Re-authentication Triggers.
    """

    def __init__(
        self,
        account_manager: Optional[MultiAccountContextManager] = None,
        cooldown_duration_minutes: int = 90,
    ):
        self.manager = account_manager or MultiAccountContextManager()
        self.cooldown_duration = timedelta(minutes=cooldown_duration_minutes)
        self.account_cooldown_timers: Dict[str, datetime] = {}
        self._current_index: Dict[str, int] = {"x": 0, "instagram": 0}

    def get_healthy_account(self, platform: str) -> Optional[AccountProfile]:
        """
        Retrieves next healthy account using round-robin load distribution.
        Checks if quarantined accounts have completed their cooldown window.
        """
        plat = platform.lower()
        now = datetime.utcnow()

        # 1. Recover accounts whose cooldown has elapsed
        for acc_id, cooldown_end in list(self.account_cooldown_timers.items()):
            if now >= cooldown_end:
                if acc_id in self.manager.accounts:
                    self.manager.accounts[acc_id].health = AccountHealth.ACTIVE
                    self.manager.accounts[acc_id].consecutive_errors = 0
                    self.manager.save_registry()
                    del self.account_cooldown_timers[acc_id]
                    logger.info("Account [%s] cooldown expired. Restored to ACTIVE pool.", acc_id)

        # 2. Filter available active accounts
        eligible_accounts = [
            acc for acc in self.manager.accounts.values()
            if acc.platform == plat and acc.health == AccountHealth.ACTIVE
        ]

        if not eligible_accounts:
            logger.error("CRITICAL: No healthy accounts available in pool for %s. All in cooldown or expired.", plat.upper())
            return None

        # 3. Round-Robin selection
        idx = self._current_index.get(plat, 0) % len(eligible_accounts)
        selected_account = eligible_accounts[idx]
        self._current_index[plat] = (idx + 1) % len(eligible_accounts)

        logger.info("Selected account from pool: [%s] (Total active: %d)", selected_account.account_id, len(eligible_accounts))
        return selected_account

    def quarantine_account(self, account_id: str, reason: str = "Rate Limit / Checkpoint") -> None:
        """Puts an account into cooldown quarantine and triggers immediate failover."""
        cooldown_until = datetime.utcnow() + self.cooldown_duration
        self.account_cooldown_timers[account_id] = cooldown_until
        self.manager.mark_account_degraded(account_id, AccountHealth.COOLDOWN)
        logger.warning(
            "Quarantined account [%s] until %s UTC. Reason: %s",
            account_id,
            cooldown_until.strftime("%H:%M:%S"),
            reason,
        )

    def get_pool_health_status(self) -> Dict[str, Any]:
        """Returns diagnostic telemetry of account availability across platforms."""
        status = {"total_registered": len(self.manager.accounts), "platforms": {}}
        for plat in ["x", "instagram"]:
            all_plat = [a for a in self.manager.accounts.values() if a.platform == plat]
            active_plat = [a for a in all_plat if a.health == AccountHealth.ACTIVE]
            cooldown_plat = [a for a in all_plat if a.health == AccountHealth.COOLDOWN]
            status["platforms"][plat] = {
                "total": len(all_plat),
                "active": len(active_plat),
                "in_cooldown": len(cooldown_plat),
            }
        return status
