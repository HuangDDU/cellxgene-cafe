"""Integration tests for cafe API routes."""


class TestManifest:
    def test_returns_200(self, client):
        resp = client.get("/api/cafe/manifest")
        assert resp.status_code == 200

    def test_has_expected_keys(self, client):
        resp = client.get("/api/cafe/manifest")
        data = resp.get_json()
        assert "apiVersion" in data
        assert "dataset" in data
        assert "plugin" in data
        assert "capabilities" in data
        assert "modules" in data

    def test_plot_and_explorer_enabled(self, client):
        resp = client.get("/api/cafe/manifest")
        data = resp.get_json()
        modules_by_key = {m["key"]: m["enabled"] for m in data["modules"]}
        assert modules_by_key.get("plot") is True
        assert modules_by_key.get("explorer") is True

    def test_default_tab_is_plot(self, client):
        resp = client.get("/api/cafe/manifest")
        assert resp.get_json()["defaultTab"] == "plot"


class TestContextEmpty:
    def test_returns_200_when_no_trajectories(self, client):
        resp = client.get("/api/cafe/context")
        assert resp.status_code == 200

    def test_returns_empty_trajectories(self, client):
        resp = client.get("/api/cafe/context")
        data = resp.get_json()
        assert data["trajectories"] == []

    def test_returns_empty_current(self, client):
        resp = client.get("/api/cafe/context")
        data = resp.get_json()
        assert data["current"]["trajectory"] == ""


class TestContextWithData:
    def test_returns_trajectories(self, client_with_data):
        resp = client_with_data.get("/api/cafe/context")
        data = resp.get_json()
        assert "ref" in data["trajectories"]

    def test_current_defaults_to_ref(self, client_with_data):
        resp = client_with_data.get("/api/cafe/context")
        data = resp.get_json()
        assert data["current"]["trajectory"] == "ref"
        assert data["current"]["layout"] == "umap"

    def test_preview_has_nodes(self, client_with_data):
        resp = client_with_data.get("/api/cafe/context")
        data = resp.get_json()
        preview = data["plot"]["preview"]
        assert len(preview["nodes"]) == 2  # M1, M2

    def test_preview_has_edges(self, client_with_data):
        resp = client_with_data.get("/api/cafe/context")
        data = resp.get_json()
        assert len(data["plot"]["preview"]["edges"]) == 1  # group M1

    def test_benchmark_rows(self, client_with_data):
        resp = client_with_data.get("/api/cafe/context")
        data = resp.get_json()
        assert len(data["plot"]["benchmarkRows"]) == 1
        assert data["plot"]["benchmarkRows"][0]["id"] == "ref"

    def test_metric_keys(self, client_with_data):
        resp = client_with_data.get("/api/cafe/context")
        data = resp.get_json()
        assert "correlation" in data["plot"]["metricKeys"]
        assert "F1_branches" in data["plot"]["metricKeys"]

    def test_host_info(self, client_with_data):
        resp = client_with_data.get("/api/cafe/context")
        data = resp.get_json()
        assert data["host"]["engine"] == "cellxgene"


class TestStaticPlot:
    def test_no_trajectories_returns_png(self, client):
        resp = client.get("/api/cafe/plot/static?view=trajectory")
        assert resp.status_code == 200
        assert resp.headers["Content-Type"] == "image/png"

    def test_no_trajectories_sets_fallback_header(self, client):
        resp = client.get("/api/cafe/plot/static?view=trajectory")
        assert resp.headers["X-CAFE-PLOT-SOURCE"] == "fallback-no-trajectory"

    def test_invalid_view_defaults_to_trajectory(self, client):
        resp = client.get("/api/cafe/plot/static?view=invalid")
        assert resp.status_code == 200

    def test_stream_view_no_trajectories(self, client):
        resp = client.get("/api/cafe/plot/static?view=stream")
        assert resp.status_code == 200


class TestTrajectorySpec:
    def test_alias_returns_context(self, client):
        resp = client.get("/api/cafe/trajectory/spec")
        assert resp.status_code == 200
        assert "trajectories" in resp.get_json()


class TestGatewayStatus:
    def test_returns_200(self, client):
        resp = client.get("/api/cafe/gateway/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "enabled" in data
        assert "url" in data


class TestJobEndpoints:
    def test_submit_rejects_empty_body(self, client):
        """Submit without required fields returns 400."""
        resp = client.post("/api/cafe/job/submit", json={})
        assert resp.status_code in (400, 422)

    def test_query_unknown_job(self, client):
        """Querying a non-existent job returns 404 from Flask."""
        resp = client.get("/api/cafe/job/nonexistent-job-id")
        # Returns 404 because the _query_method_job raises and is caught
        assert resp.status_code in (404, 500)
