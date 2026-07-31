import unittest
from pathlib import Path


MIGRATIONS = Path(__file__).parents[2] / "supabase" / "migrations"
COMPLETIONS = MIGRATIONS / "20260731000000_tour_completions_and_profile_stats.sql"


class TourCompletionSchemaTest(unittest.TestCase):
    def test_completion_is_unique_and_only_allows_own_deletes(self) -> None:
        sql = COMPLETIONS.read_text()

        self.assertIn("unique (tour_id, user_id)", sql)
        self.assertIn("grant select on public.tour_completions to authenticated", sql)
        self.assertNotIn(
            "grant insert on public.tour_completions to authenticated", sql
        )
        self.assertNotIn(
            "grant update on public.tour_completions to authenticated", sql
        )
        self.assertIn("grant delete on public.tour_completions to authenticated", sql)
        self.assertIn("create policy tour_completions_delete_own", sql)
        self.assertIn("for delete to authenticated using (user_id = auth.uid())", sql)

    def test_completion_rpc_has_one_responsibility_and_is_idempotent(self) -> None:
        sql = COMPLETIONS.read_text()

        self.assertIn("on conflict (tour_id, user_id) do nothing", sql)
        completion_function = sql.split(
            "create function public.complete_tour", 1
        )[1].split("revoke all on function public.complete_tour", 1)[0]
        self.assertNotIn("p_rating", completion_function)
        self.assertNotIn("p_body", completion_function)
        self.assertNotIn("tour_reviews", completion_function)

    def test_future_review_writes_mark_completed_without_backfill(self) -> None:
        sql = COMPLETIONS.read_text()

        self.assertIn("after insert or update on public.tour_reviews", sql)
        self.assertIn("insert into public.tour_completions", sql)

    def test_empty_public_tours_do_not_add_community_distance(self) -> None:
        sql = COMPLETIONS.read_text()

        self.assertGreaterEqual(sql.count("case when completions.id is not null"), 2)


if __name__ == "__main__":
    unittest.main()
