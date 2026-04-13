"""Root conftest — registers the --run-live CLI flag for pytest."""


def pytest_addoption(parser):
    parser.addoption(
        "--run-live",
        action="store_true",
        default=False,
        help="Run live scraper tests that hit Indeed/LinkedIn",
    )
