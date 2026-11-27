import unittest

from app.cards import clear_movie_card


class _Card:
    def __init__(self) -> None:
        self.relative_path = "films/Armageddec_2013_BDRip_by_Dalemake.avi"
        self.file_name = "Armageddec_2013_BDRip_by_Dalemake.avi"
        self.status = "matched"
        self.kp_checked = True
        self.title_ru = "Армагеддон"
        self.title_en = "Armageddon"
        self.year = 1998
        self.overview_ru = "не тот фильм"
        self.rating_tmdb = 6.0
        self.rating_kp = 7.0
        self.tmdb_id = 1231646
        self.kp_id = 2941
        self.duration_sec = 9000
        self.confidence = 1
        self.error = "старая ошибка"
        self.enriched_at = "когда-то"


class ClearCardTests(unittest.TestCase):
    def test_keeps_file_identity_and_parsed_title(self):
        movie = _Card()
        clear_movie_card(movie)
        self.assertEqual(movie.status, "pending")
        self.assertFalse(movie.kp_checked)
        self.assertEqual(movie.title_ru, "Armageddec")
        self.assertIsNone(movie.title_en)
        self.assertEqual(movie.year, 2013)
        self.assertIsNone(movie.tmdb_id)
        self.assertIsNone(movie.kp_id)
        self.assertIsNone(movie.overview_ru)
        self.assertIsNone(movie.confidence)
        self.assertIsNone(movie.error)
        self.assertIsNone(movie.enriched_at)
        self.assertEqual(movie.file_name, "Armageddec_2013_BDRip_by_Dalemake.avi")
        self.assertEqual(movie.relative_path, "films/Armageddec_2013_BDRip_by_Dalemake.avi")


if __name__ == "__main__":
    unittest.main()
