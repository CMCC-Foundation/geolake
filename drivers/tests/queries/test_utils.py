from intake_geokube.queries import utils as ut


class TestUtils:
    def test_find_key_root_level_recusrive_switched_off(self):
        assert ut.find_value({"a": 0, "b": 10}, "b", recursive=False) == 10

    def test_find_key_root_level_recusrive_switched_on(self):
        assert ut.find_value({"a": 0, "b": 10}, "b", recursive=True) == 10

    def test_return_none_on_missing_key_root_level(self):
        assert ut.find_value({"a": 0, "b": 10}, "c", recursive=True) is None

    def test_return_none_on_missing_key_another_level(self):
        assert (
            ut.find_value({"a": 0, "b": {"c": 10}}, "d", recursive=True)
            is None
        )

    def test_find_key_another_level_recursive_switched_off(self):
        assert (
            ut.find_value({"a": 0, "b": {"c": "ccc"}}, "c", recursive=False)
            is None
        )

    def test_find_key_another_level_recursive_switched_on(self):
        assert (
            ut.find_value({"a": 0, "b": {"c": "ccc"}}, "c", recursive=True)
            == "ccc"
        )

    def test_find_list_first(self):
        assert (
            ut.find_value(
                {"a": 0, "b": [{"c": "ccc"}, {"d": "ddd"}]},
                "c",
                recursive=True,
            )
            == "ccc"
        )

    def test_find_list_not_first(self):
        assert (
            ut.find_value(
                {"a": 0, "b": [{"d": "ddd"}, {"c": "ccc"}]},
                "c",
                recursive=True,
            )
            == "ccc"
        )
