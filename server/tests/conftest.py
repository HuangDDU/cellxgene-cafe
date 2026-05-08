"""Pytest fixtures for cafe API tests."""
import pytest
import flask


class FakeServerConfig:
    single_dataset__datapath = None


class FakeAppConfig:
    server_config = FakeServerConfig()

    @staticmethod
    def get_title(adaptor):
        return "test-dataset"


class FakeDataAdaptor:
    def __init__(self, uns_dict=None):
        self.data = type("FakeAnnData", (), {"uns": uns_dict or {}})()

    def get_uns(self):
        return self.data.uns


@pytest.fixture
def app():
    """Create a Flask test app with the cafe blueprint registered."""
    import sys
    import os

    # Ensure the project root is on path
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from server.cafe_api import cafe_bp

    application = flask.Flask(__name__)
    application.config["TESTING"] = True
    application.register_blueprint(cafe_bp)

    return application


@pytest.fixture
def client(app, monkeypatch):
    """Flask test client with mocked data_adaptor."""
    with app.test_client() as test_client:
        # Push app context so current_app works in routes
        ctx = app.app_context()
        ctx.push()

        # Set up mock data adaptor on current_app
        flask.current_app.data_adaptor = FakeDataAdaptor({"cafe": {"trajectory_history_dict": {}}})
        flask.current_app.app_config = FakeAppConfig()

        yield test_client

        ctx.pop()


@pytest.fixture
def client_with_data(app, monkeypatch):
    """Flask test client with trajectory history data."""
    import numpy as np

    with app.test_client() as test_client:
        ctx = app.app_context()
        ctx.push()

        uns = {
            "cafe": {
                "trajectory_history_dict": {
                    "ref": {
                        "trajectory_embedding": {
                            "umap": {
                                "milestone_positions": [
                                    {"milestone_id": "M1", "comp_1": 10.0, "comp_2": 20.0, "group": "M1", "from": "M1", "to": "M2"},
                                    {"milestone_id": "M2", "comp_1": 30.0, "comp_2": 40.0, "group": "M1", "from": "M1", "to": "M2"},
                                ],
                                "wp_segments": [
                                    {"comp_1": 15.0, "comp_2": 25.0, "percentage": 50.0, "group": "M1"},
                                    {"comp_1": 20.0, "comp_2": 30.0, "percentage": 75.0, "group": "M1"},
                                ],
                            }
                        },
                        "milestone_wrapper": {"id_list": ["M1", "M2"], "color_list": ["#ff0000", "#00ff00"]},
                        "metric_dict": {"correlation": 0.95, "F1_branches": 0.88},
                    }
                }
            }
        }

        flask.current_app.data_adaptor = FakeDataAdaptor(uns)
        flask.current_app.app_config = FakeAppConfig()

        yield test_client

        ctx.pop()
