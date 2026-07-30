import unittest
from pathlib import Path


MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "20260730000000_serialize_credit_spend.sql"
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


if __name__ == "__main__":
    unittest.main()
