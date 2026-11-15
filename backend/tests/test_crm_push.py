"""A change recorded for the CRM is pushed right after its commit (no database needed: the sync itself is stubbed)."""

import asyncio
import unittest
from unittest import mock

from app.core import crm_events


class PushNowTests(unittest.TestCase):
    def test_a_commit_that_recorded_something_pushes_once_and_a_burst_goes_round_again(self):
        calls = []

        async def deliver(self):
            calls.append(1)
            if len(calls) == 1:
                await crm_events.push_now()  # a second change arrives while the first push is running
            return {}

        async def go():
            with mock.patch("app.services.crm_sync.CrmSync.deliver_due", deliver):
                await crm_events.push_now()

        asyncio.run(go())
        self.assertEqual(len(calls), 2)

    def test_nothing_recorded_means_no_push(self):
        session = mock.Mock(info={})
        with mock.patch.object(asyncio, "get_running_loop") as loop:
            crm_events._after_commit(session)
        loop.assert_not_called()

    def test_without_an_event_loop_the_cron_job_does_it(self):
        session = mock.Mock(info={crm_events.ADDED_KEY: True})
        crm_events._after_commit(session)  # no running loop here: must not raise
        self.assertEqual(session.info, {})


if __name__ == "__main__":
    unittest.main()
