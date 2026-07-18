import unittest
from unittest.mock import MagicMock, patch


class TestLookupWord(unittest.TestCase):
    """Tests for dict_lookup.lookup_word using mocked wn and _get_ipa."""

    def _make_word_entry(self, pos: str, definitions: list[str]) -> MagicMock:
        """Helper to create a mock wn Word object."""
        senses = []
        for defn in definitions:
            synset = MagicMock()
            synset.definition.return_value = defn
            sense = MagicMock()
            sense.synset.return_value = synset
            senses.append(sense)

        word_entry = MagicMock()
        word_entry.pos = pos
        word_entry.senses.return_value = senses
        return word_entry

    @patch("dict_lookup._get_ipa", return_value="hɛˈloʊ")
    @patch("dict_lookup.wn")
    def test_known_word_returns_correct_keys(
        self, mock_wn: MagicMock, mock_ipa: MagicMock
    ) -> None:
        import dict_lookup

        mock_wn.words.return_value = [
            self._make_word_entry("n", ["a greeting"]),
        ]
        result = dict_lookup.lookup_word("hello")

        self.assertIn("url", result)
        self.assertIn("ipa", result)
        self.assertIn("means", result)

    @patch("dict_lookup._get_ipa", return_value="hɛˈloʊ")
    @patch("dict_lookup.wn")
    def test_known_word_has_definitions(
        self, mock_wn: MagicMock, mock_ipa: MagicMock
    ) -> None:
        import dict_lookup

        mock_wn.words.return_value = [
            self._make_word_entry("n", ["a greeting"]),
            self._make_word_entry("v", ["to say hello"]),
        ]
        result = dict_lookup.lookup_word("hello")
        means = result["means"]

        self.assertIsInstance(means, list)
        self.assertEqual(len(means), 2)
        self.assertEqual(means[0], "(noun) a greeting")
        self.assertEqual(means[1], "(verb) to say hello")

    @patch("dict_lookup._get_ipa", return_value="")
    @patch("dict_lookup.wn")
    def test_unknown_word_returns_empty_means(
        self, mock_wn: MagicMock, mock_ipa: MagicMock
    ) -> None:
        import dict_lookup

        mock_wn.words.return_value = []
        result = dict_lookup.lookup_word("xyznonexistent")

        self.assertEqual(result["means"], [])
        self.assertIsInstance(result["url"], str)
        self.assertEqual(result["ipa"], "")

    @patch("dict_lookup._get_ipa", return_value="rən")
    @patch("dict_lookup.wn")
    def test_url_contains_word(self, mock_wn: MagicMock, mock_ipa: MagicMock) -> None:
        import dict_lookup

        mock_wn.words.return_value = []
        result = dict_lookup.lookup_word("run")

        self.assertIn("run", result["url"])
        self.assertTrue(result["url"].startswith("https://en.wiktionary.org/wiki/"))

    @patch("dict_lookup._get_ipa", return_value="rən")
    @patch("dict_lookup.wn")
    def test_ipa_returned_for_known_word(
        self, mock_wn: MagicMock, mock_ipa: MagicMock
    ) -> None:
        import dict_lookup

        mock_wn.words.return_value = [
            self._make_word_entry("n", ["a fast pace"]),
        ]
        result = dict_lookup.lookup_word("run")

        self.assertEqual(result["ipa"], "rən")

    @patch("dict_lookup._get_ipa", return_value="")
    @patch("dict_lookup.wn")
    def test_ipa_empty_for_unknown_word(
        self, mock_wn: MagicMock, mock_ipa: MagicMock
    ) -> None:
        import dict_lookup

        mock_wn.words.return_value = []
        result = dict_lookup.lookup_word("xyzzy")

        self.assertEqual(result["ipa"], "")

    @patch("dict_lookup._get_ipa", return_value="tɛst")
    @patch("dict_lookup.wn")
    def test_pos_labels(self, mock_wn: MagicMock, mock_ipa: MagicMock) -> None:
        import dict_lookup

        mock_wn.words.return_value = [
            self._make_word_entry("n", ["a thing"]),
            self._make_word_entry("v", ["to do"]),
            self._make_word_entry("a", ["describing"]),
            self._make_word_entry("r", ["in a way"]),
        ]
        result = dict_lookup.lookup_word("test")
        means = result["means"]

        self.assertTrue(means[0].startswith("(noun)"))
        self.assertTrue(means[1].startswith("(verb)"))
        self.assertTrue(means[2].startswith("(adj)"))
        self.assertTrue(means[3].startswith("(adv)"))

    @patch("dict_lookup._get_ipa", return_value="hɛˈloʊ")
    @patch("dict_lookup.wn")
    def test_wn_exception_returns_empty_means(
        self, mock_wn: MagicMock, mock_ipa: MagicMock
    ) -> None:
        import dict_lookup

        mock_wn.words.side_effect = RuntimeError("db error")
        result = dict_lookup.lookup_word("hello")

        self.assertEqual(result["means"], [])
        # IPA should still work even if WordNet fails
        self.assertEqual(result["ipa"], "hɛˈloʊ")

    @patch("dict_lookup._get_ipa", return_value="")
    @patch("dict_lookup.wn")
    def test_ipa_failure_returns_empty_ipa(
        self, mock_wn: MagicMock, mock_ipa: MagicMock
    ) -> None:
        import dict_lookup

        mock_wn.words.return_value = [
            self._make_word_entry("n", ["a greeting"]),
        ]
        result = dict_lookup.lookup_word("hello")

        self.assertEqual(result["ipa"], "")
        # Definitions should still work even if IPA fails
        self.assertEqual(len(result["means"]), 1)


class TestGetIpa(unittest.TestCase):
    """Tests for dict_lookup._get_ipa."""

    @patch("dict_lookup._eng_to_ipa")
    def test_known_word(self, mock_ipa: MagicMock) -> None:
        import dict_lookup

        mock_ipa.convert.return_value = "hɛˈloʊ"
        self.assertEqual(dict_lookup._get_ipa("hello"), "hɛˈloʊ")

    @patch("dict_lookup._eng_to_ipa")
    def test_unknown_word_asterisk(self, mock_ipa: MagicMock) -> None:
        import dict_lookup

        mock_ipa.convert.return_value = "xyzzy*"
        self.assertEqual(dict_lookup._get_ipa("xyzzy"), "")

    @patch("dict_lookup._eng_to_ipa")
    def test_exception_returns_empty(self, mock_ipa: MagicMock) -> None:
        import dict_lookup

        mock_ipa.convert.side_effect = RuntimeError("ipa error")
        self.assertEqual(dict_lookup._get_ipa("hello"), "")


class TestLookupWordFr(unittest.TestCase):
    """Tests for dict_lookup.lookup_word_fr using mocked wn."""

    def _make_word_entry(self, pos: str, definitions: list[str]) -> MagicMock:
        """Helper to create a mock wn Word object."""
        senses = []
        for defn in definitions:
            en_synset = MagicMock()
            en_synset.definition.return_value = defn
            synset = MagicMock()
            synset.translate.return_value = [en_synset]
            sense = MagicMock()
            sense.synset.return_value = synset
            senses.append(sense)

        word_entry = MagicMock()
        word_entry.pos = pos
        word_entry.senses.return_value = senses
        return word_entry

    @patch("dict_lookup.wn")
    def test_known_word_returns_correct_keys(self, mock_wn: MagicMock) -> None:
        import dict_lookup

        mock_wn.words.return_value = [
            self._make_word_entry("n", ["a house"]),
        ]
        result = dict_lookup.lookup_word_fr("maison")

        self.assertIn("url", result)
        self.assertIn("ipa", result)
        self.assertIn("means", result)
        self.assertEqual(result["ipa"], "")

    @patch("dict_lookup.wn")
    def test_known_word_has_definitions(self, mock_wn: MagicMock) -> None:
        import dict_lookup

        mock_wn.words.return_value = [
            self._make_word_entry("n", ["a house"]),
            self._make_word_entry("adj", ["domestic"]),
        ]
        result = dict_lookup.lookup_word_fr("maison")
        means = result["means"]

        self.assertIsInstance(means, list)
        self.assertEqual(len(means), 2)
        self.assertEqual(means[0], "(noun) a house")
        self.assertEqual(means[1], "(adj) domestic")

    @patch("dict_lookup.wn")
    def test_unknown_word_returns_empty_means(self, mock_wn: MagicMock) -> None:
        import dict_lookup

        mock_wn.words.return_value = []
        result = dict_lookup.lookup_word_fr("xyznonexistent")

        self.assertEqual(result["means"], [])
        self.assertEqual(result["ipa"], "")

    @patch("dict_lookup.wn")
    def test_url_contains_word(self, mock_wn: MagicMock) -> None:
        import dict_lookup

        mock_wn.words.return_value = []
        result = dict_lookup.lookup_word_fr("maison")

        self.assertIn("maison", result["url"])
        self.assertTrue(result["url"].startswith("https://fr.wiktionary.org/wiki/"))

    @patch("dict_lookup.wn")
    def test_wn_exception_returns_empty_means(self, mock_wn: MagicMock) -> None:
        import dict_lookup

        mock_wn.words.side_effect = RuntimeError("db error")
        result = dict_lookup.lookup_word_fr("maison")

        self.assertEqual(result["means"], [])


if __name__ == "__main__":
    unittest.main()
