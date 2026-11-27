import unittest

from app.matching import classify, score_match, similarity, yo_variants
from app.paths import parent_relative, playlist_filename, smb_dir_url, smb_url, unc_path


class MatchTests(unittest.TestCase):
    def test_yo(self):
        self.assertEqual(similarity("Ёлки", "Елки"), 1)

    def test_yo_variants_flip_one_letter_then_pairs(self):
        self.assertEqual(
            yo_variants("Зеленая книга"),
            ["Зёленая книга", "Зелёная книга", "Зёлёная книга"],
        )
        self.assertIn("Зеленая книга", yo_variants("Зелёная книга"))
        self.assertEqual(yo_variants("Die Hard"), [])
        self.assertIn("Ёлки зелёные", yo_variants("Елки зеленые"))

    def test_year_boost_prefers_exact_film(self):
        exact = score_match("Die Hard", 1988, ["Die Hard"], 1988)
        sequel = score_match("Die Hard", 1988, ["Die Hard 2"], 1990)
        self.assertGreater(exact, sequel)

    def test_classify(self):
        self.assertEqual(classify(0.9, 0.8), "matched")
        self.assertEqual(classify(0.9, 0.87), "ambiguous")
        self.assertEqual(classify(0.6, None), "ambiguous")
        self.assertEqual(classify(0.4, None), "failed")


class PathTests(unittest.TestCase):
    def test_unc_and_parent(self):
        relative = "Paul (2011) BDRip/Paul (2011) BDRip.mkv"
        self.assertEqual(
            unc_path("Keenetic-1601", "ADATA SC610", relative),
            "\\\\Keenetic-1601\\ADATA SC610\\Paul (2011) BDRip\\Paul (2011) BDRip.mkv",
        )
        self.assertEqual(parent_relative(relative), "Paul (2011) BDRip")
        self.assertEqual(parent_relative("film.mkv"), "")

    def test_smb_encodes_space_and_folder_slash(self):
        url = smb_url("Keenetic-1601", "ADATA SC610", "Жмот (2016).mkv")
        self.assertTrue(url.startswith("smb://Keenetic-1601/ADATA%20SC610/"))
        self.assertNotIn(" ", url)
        folder = smb_dir_url("Keenetic-1601", "KINGSTON", "Die Hard")
        self.assertTrue(folder.endswith("/"))

    def test_playlist_filename_uses_video_stem(self):
        self.assertEqual(
            playlist_filename("Paul (2011) BDRip.mkv"),
            "Paul (2011) BDRip.m3u",
        )
        self.assertEqual(playlist_filename("Жмот (2016).mkv"), "Жмот (2016).m3u")
        self.assertEqual(playlist_filename("dir/film.avi"), "film.m3u")
        self.assertEqual(playlist_filename("   "), "movie.m3u")


if __name__ == "__main__":
    unittest.main()
