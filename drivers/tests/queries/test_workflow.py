import pytest

from intake_geokube.queries.workflow import Workflow


class TestWorkflow:
    def test_fail_on_missing_dataset_id(self):
        with pytest.raises(
            KeyError,
            match=r"'dataset_id' key was missing. did you defined it for*",
        ):
            Workflow.parse({
                "tasks": [{
                    "id": 0,
                    "op": "subset",
                    "args": {
                        "product_id": "reanalysis",
                    },
                }]
            })

    def test_fail_on_missing_product_id(self):
        with pytest.raises(
            KeyError,
            match=r"'product_id' key was missing. did you defined it for*",
        ):
            Workflow.parse({
                "tasks": [{
                    "id": 0,
                    "op": "subset",
                    "args": {
                        "dataset_id": "era5",
                    },
                }]
            })

    def test_fail_on_nonunique_id(self):
        with pytest.raises(
            ValueError,
            match=r"duplicated key found*",
        ):
            Workflow.parse({
                "tasks": [
                    {
                        "id": 0,
                        "op": "subset",
                        "args": {
                            "dataset_id": "era5",
                            "product_id": "reanalysis",
                        },
                    },
                    {
                        "id": 0,
                        "op": "subset",
                        "args": {
                            "dataset_id": "era5",
                            "product_id": "reanalysis",
                        },
                    },
                ]
            })
