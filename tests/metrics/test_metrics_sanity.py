from __future__ import annotations

from fastapi import FastAPI
from prometheus_client import CollectorRegistry, generate_latest

from src.observability.prom_installer import install_prometheus_endpoint


def test_metrics_installer_idempotent_without_duplicates(monkeypatch, caplog) -> None:
    registry = CollectorRegistry()
    caplog.set_level("WARNING")

    app = FastAPI()

    # Ensure metrics register against the isolated registry so we can scrape safely.
    import src.observability.metrics as metrics_module

    monkeypatch.setattr(metrics_module, "REGISTRY", registry)
    monkeypatch.setattr(metrics_module, "_METRICS_BY_NAMESPACE", {})

    metrics_module.get_job_metrics("sanity")
    metrics_module.get_job_metrics("sanity")

    install_prometheus_endpoint(app, registry=registry)
    install_prometheus_endpoint(app, registry=registry)

    metrics_text = generate_latest(registry).decode()

    assert "Duplicated timeseries" not in metrics_text
    assert "Already_registered" not in metrics_text
    assert "ValueError" not in metrics_text

    for record in caplog.records:
        lowered = record.getMessage().lower()
        assert "duplicated timeseries" not in lowered
        assert "already_registered" not in lowered
        assert "valueerror" not in lowered

    # Ensure the installer remains idempotent by invoking it a third time and scraping again.
    install_prometheus_endpoint(app, registry=registry)
    another_scrape = generate_latest(registry).decode()
    assert another_scrape == metrics_text
