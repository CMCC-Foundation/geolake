import argparse
import intake

parser = argparse.ArgumentParser(
    prog="Cache generator",
    description="The script generating cache for the catalog",
)
parser.add_argument(
    "--cachedir",
    type=str,
    help="Directory where the cache should be saved. Default: .cache",
    default=".cache",
)

if __name__ == "__main__":
    args = parser.parse_args()
    catalog = intake.open_catalog("catalog.yaml")
    for ds in list(catalog):
        for p in list(catalog[ds]):
            print(f"dataset: {ds} product: {p}:")
            catalog = catalog(CACHE_DIR=args.cachedir)
            kube = catalog[ds][p].read()