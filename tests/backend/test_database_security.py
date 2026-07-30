import unittest
from pathlib import Path


MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "20260730000000_harden_tour_production.sql"
)
TOUR_COMMANDS = (
    Path(__file__).parents[2]
    / "supabase"
    / "functions"
    / "tour-commands"
    / "index.ts"
)


class CreditSpendSerializationTest(unittest.TestCase):
    def test_owner_lock_serializes_balance_check_and_debit(self) -> None:
        sql = MIGRATION.read_text()

        owner_lock = (
            "pg_advisory_xact_lock(\n"
            "    hashtextextended(\n"
            "      'tour-production-credit:' || v_tour.owner_id::text,\n"
            "      0\n"
            "    )\n"
            "  )"
        )
        balance_read = "select coalesce(sum(delta), 0) into v_balance"
        debit = "v_tour.owner_id, -1, 'tour_generation'"

        self.assertIn(owner_lock, sql)
        self.assertLess(sql.index(owner_lock), sql.index(balance_read))
        self.assertLess(sql.index(balance_read), sql.index(debit))


class ReadyTourReplayTest(unittest.TestCase):
    def test_ready_replay_skips_job_creation_and_worker_invocation(self) -> None:
        sql = MIGRATION.read_text()
        commands = TOUR_COMMANDS.read_text()

        ready_branch = sql.index("if not v_should_produce then")
        job_insert = sql.index("insert into public.tour_jobs", ready_branch)
        skip_return = sql.index("'invoke_worker', false", ready_branch)

        self.assertLess(skip_return, job_insert)
        self.assertIn("'invoke_worker', v_job.status = 'pending'", sql)
        self.assertIn(
            "if (result.invoke_worker !== false) await invokeWorker(result.job_id);",
            commands,
        )

    def test_new_production_still_creates_and_invokes_a_job(self) -> None:
        sql = MIGRATION.read_text()

        job_insert = sql.index("insert into public.tour_jobs")
        invoke_return = sql.index("'invoke_worker', true", job_insert)

        self.assertLess(job_insert, invoke_return)


if __name__ == "__main__":
    unittest.main()
