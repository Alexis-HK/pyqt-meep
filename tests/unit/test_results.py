from __future__ import annotations

from meep_gui.analysis import ArtifactResult, PlotResult, RunResult
from meep_gui.model import PlotRecord, ResultArtifact, RunRecord
from meep_gui.results import (
    CurveArtifact,
    ImageArtifact,
    RawDataArtifact,
    TableArtifact,
    TextArtifact,
    display_entries_from_run_record,
    typed_artifacts_from_run_record,
    typed_artifacts_from_run_result,
)


def test_run_record_outputs_normalize_to_typed_artifacts() -> None:
    run = RunRecord(
        run_id="r1",
        analysis_kind="harminv",
        artifacts=[
            ResultArtifact(kind="frequency_domain_field_png", label="field.png", path="/tmp/field.png"),
            ResultArtifact(
                kind="harminv_text",
                label="harminv.txt",
                path="",
                meta={"lines": "harminv: freq=0.2"},
            ),
            ResultArtifact(kind="custom_blob", label="raw.bin", path="/tmp/raw.bin"),
        ],
        plots=[
            PlotRecord(
                title="Spectrum",
                x_label="Frequency",
                y_label="Response",
                csv_path="/tmp/spectrum.csv",
                png_path="/tmp/spectrum.png",
            )
        ],
    )

    artifacts = typed_artifacts_from_run_record(run)

    assert isinstance(artifacts[0], ImageArtifact)
    assert isinstance(artifacts[1], TextArtifact)
    assert isinstance(artifacts[2], RawDataArtifact)
    assert isinstance(artifacts[3], CurveArtifact)
    assert artifacts[1].text == "harminv: freq=0.2"
    assert artifacts[3].csv_path == "/tmp/spectrum.csv"
    assert artifacts[3].png_path == "/tmp/spectrum.png"


def test_plot_record_normalizes_to_curve_and_deduplicates_plot_csv_against_artifact() -> None:
    run = RunRecord(
        run_id="tx1",
        analysis_kind="transmission_spectrum",
        artifacts=[
            ResultArtifact(kind="transmission_csv", label="tx.csv", path="/tmp/tx.csv"),
        ],
        plots=[
            PlotRecord(
                title="Transmission Spectrum",
                x_label="Frequency",
                y_label="Response",
                csv_path="/tmp/tx.csv",
                png_path="/tmp/tx.png",
            )
        ],
    )

    entries = display_entries_from_run_record(run)

    assert [entry.list_label for entry in entries] == [
        "transmission_csv: tx.csv",
        "Transmission Spectrum (PNG)",
    ]


def test_run_result_normalization_preserves_inline_text_and_csv_outputs() -> None:
    result = RunResult(
        status="completed",
        artifacts=[
            ArtifactResult(kind="harminv_text", label="harminv.txt", path="", meta={"lines": "mode 1"}),
            ArtifactResult(kind="transmission_csv", label="tx.csv", path="/tmp/tx.csv"),
        ],
        plots=[
            PlotResult(
                title="Bands",
                x_label="k-index",
                y_label="Frequency",
                csv_path="/tmp/bands.csv",
                png_path="",
            )
        ],
    )

    artifacts = typed_artifacts_from_run_result(result)

    assert isinstance(artifacts[0], TextArtifact)
    assert artifacts[0].text == "mode 1"
    assert isinstance(artifacts[1], TableArtifact)
    assert isinstance(artifacts[2], CurveArtifact)


def test_domain_preview_png_normalizes_as_image_artifact() -> None:
    result = RunResult(
        status="completed",
        artifacts=[
            ArtifactResult(
                kind="domain_preview_png",
                label="domain_preview.png",
                path="/tmp/domain_preview.png",
            )
        ],
    )

    artifacts = typed_artifacts_from_run_result(result)

    assert len(artifacts) == 1
    assert isinstance(artifacts[0], ImageArtifact)
