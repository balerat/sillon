import h5py
import numpy as np
import pytest
from sqlmodel import SQLModel, Session, create_engine

from silloncommon.database import SimulationTable, ArtifactTable, FigureTable

import sillonlab as sl

RUN_A_UUID = "11111111-aaaa-bbbb-cccc-000000000001"
RUN_B_UUID = "11111111-aaaa-bbbb-cccc-000000000002"
ARTIFACT_ID = "22222222-aaaa-bbbb-cccc-000000000001"
FIGURE_ID = "33333333-aaaa-bbbb-cccc-000000000001"


@pytest.fixture()
def project_dir(tmp_path):
    """Builds a fake but complete sillon project on disk (db + glob + artifact)."""
    sillon_dir = tmp_path / ".sillon"
    glob_dir = sillon_dir / "glob" / RUN_A_UUID
    artifact_dir = sillon_dir / "artifact" / RUN_A_UUID / ARTIFACT_ID
    figure_dir = sillon_dir / "figure" / RUN_A_UUID / FIGURE_ID
    glob_dir.mkdir(parents=True)
    artifact_dir.mkdir(parents=True)
    figure_dir.mkdir(parents=True)

    (artifact_dir / "mesh.txt").write_text("artifact content")
    (figure_dir / "fit.png").write_bytes(b"\x89PNG fake image bytes")

    with h5py.File(glob_dir / "glob.hdf5", "w") as g:
        g.create_dataset("result/coef", data=np.array([1.323, 323.0]))
        g.create_dataset("metadata/main_source", data="print('hello sillon')")
        # A heavy parameter array offloaded to the glob 'parameter' group.
        g.create_dataset("parameter/big_param", data=np.arange(1000, dtype=float))

    engine = create_engine("sqlite:///" + str(sillon_dir / "database.sql"))
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            SimulationTable(
                uuid=RUN_A_UUID,
                name="run_a",
                date="2026-06-01-10:00:00",
                parameters={
                    "learning_rate": 0.01,
                    "optimizer": "adam",
                    # Heavy array param: DB keeps only a marker, data is in the glob.
                    "big_param": {
                        "__sillon_array_ref__": True,
                        "pointer": "big_param",
                        "shape": [1000],
                        "dtype": "float64",
                    },
                },
                results={"coef": "coef", "external": "/data/external.txt"},
                meta_data={"sillon.language": "python 3.13"},
                tag=["baseline"],
                note=["first try"],
                runtime="0:00:01",
                status="SUCCESS",
                platform="python",
                hostname="testhost",
                organisation="",
                author="tester",
                project="lab_test",
                hashes={},
                sillonversion="0.2.0",
                artifacts=[ArtifactTable(name="mesh", hsh="abc123", path=ARTIFACT_ID)],
                figures=[
                    FigureTable(
                        name="fit",
                        hsh="fig456",
                        path=FIGURE_ID,
                        meta={
                            "used": ["learning_rate", "coef"],
                            "caption": "Linear fit",
                            "format": "png",
                        },
                        date="2026-06-01-10:00:00",
                    )
                ],
            )
        )
        session.add(
            SimulationTable(
                uuid=RUN_B_UUID,
                name="run_b",
                date="2026-06-02-10:00:00",
                parameters={"learning_rate": 0.02},
                results={},
                meta_data={},
                tag=[],
                note=[],
                runtime="0:00:02",
                status="FAILED",
                platform="python",
                hostname="testhost",
                organisation="",
                author="tester",
                project="lab_test",
                hashes={},
                sillonversion="0.2.0",
            )
        )
        session.commit()
    engine.dispose()
    return tmp_path


# ==========================================
#               PROJECT
# ==========================================


def test_load_project_not_a_project(tmp_path):
    with pytest.raises(FileNotFoundError):
        sl.load_project(tmp_path)


def test_load_project_and_list_runs(project_dir):
    project = sl.load_project(project_dir)
    assert len(project) == 2
    assert project.runs().list() == ["run_a", "run_b"]


def test_project_context_overview(project_dir):
    context = sl.load_project(project_dir).context()
    assert context["mode"] == "overview"
    assert len(context["runs"]) == 2


def test_project_getitem(project_dir):
    project = sl.load_project(project_dir)
    assert project[0].name == "run_a"
    assert project["run_b"].name == "run_b"


def test_project_get_missing_run(project_dir):
    with pytest.raises(LookupError):
        sl.load_project(project_dir).get("does_not_exist")


def test_project_details(project_dir):
    details = sl.load_project(project_dir).details(
        run_names="run_a", parameters=True
    )
    keys = {row.key for row in details["parameter"]}
    assert keys == {"learning_rate", "optimizer", "big_param"}


def test_project_add_note_and_tag(project_dir):
    project = sl.load_project(project_dir)
    out = project.add("run_b", notes="checked", tags="reviewed")
    assert out["status"] == "success"
    run = project.get("run_b")
    assert "checked" in run.notes
    assert "reviewed" in run.tags


# ==========================================
#                 RUN
# ==========================================


def test_run_tracked_data(project_dir):
    run = sl.load_project(project_dir).get("run_a")
    assert run.uuid == RUN_A_UUID
    assert run.status == "SUCCESS"
    assert run.parameters["learning_rate"] == 0.01
    assert run.parameters["optimizer"] == "adam"
    assert run.tags == ["baseline"]
    assert run.notes == ["first try"]
    assert set(run.results) == {"coef", "external", "mesh"}


def test_run_load_parameter(project_dir):
    run = sl.load_project(project_dir).get("run_a")
    assert run.load_parameter("learning_rate") == 0.01
    assert run.load_parameter("learning_rate", "optimizer") == [0.01, "adam"]
    with pytest.raises(LookupError):
        run.load_parameter("nope")
    with pytest.raises(ValueError):
        run.load_parameter()


def test_run_load_large_parameter_from_glob(project_dir):
    run = sl.load_project(project_dir).get("run_a")
    # Heavy array param: load_parameter reads it back from the glob as the array,
    # while the raw .parameters dict only exposes the lightweight marker.
    big = run.load_parameter("big_param")
    assert np.allclose(big, np.arange(1000, dtype=float))
    assert run.parameters["big_param"]["__sillon_array_ref__"] is True
    assert run.parameters["big_param"]["shape"] == [1000]


def test_run_load_result_from_glob(project_dir):
    run = sl.load_project(project_dir).get("run_a")
    coef = run.load_result("coef")
    assert np.allclose(coef, [1.323, 323.0])


def test_run_load_result_plain_value(project_dir):
    run = sl.load_project(project_dir).get("run_a")
    assert run.load_result("external") == "/data/external.txt"


def test_run_load_artifact(project_dir):
    run = sl.load_project(project_dir).get("run_a")
    artifact_path = run.load_artifact("mesh")
    assert artifact_path.name == "mesh.txt"
    assert artifact_path.read_text() == "artifact content"
    # An artifact is also reachable through load_result
    assert run.load_result("mesh") == artifact_path


def test_run_load_source(project_dir):
    run = sl.load_project(project_dir).get("run_a")
    assert run.load_source() == "print('hello sillon')"


def test_run_load_by_uuid(project_dir):
    run = sl.load_project(project_dir).get(RUN_A_UUID)
    assert run.name == "run_a"


# ==========================================
#             RUN COLLECTION
# ==========================================


def test_collection_access(project_dir):
    runs = sl.load_project(project_dir).runs()
    assert len(runs) == 2
    assert runs["run_a"].name == "run_a"
    assert runs[0].name == "run_a"
    assert len(runs[0:1]) == 1
    with pytest.raises(KeyError):
        runs["nope"]


def test_collection_filter(project_dir):
    runs = sl.load_project(project_dir).runs()
    failed = runs.filter(lambda run: run.status == "FAILED")
    assert failed.list() == ["run_b"]


# ==========================================
#          FETCH, SIZES AND EXPORT
# ==========================================


def test_fetch_result_glob_to_npy(project_dir, tmp_path):
    run = sl.load_project(project_dir).get("run_a")
    dest = tmp_path / "fetched"
    target = run.fetch_result("coef", dest)
    assert target == dest / "coef.npy"
    assert np.allclose(np.load(target), [1.323, 323.0])


def test_fetch_result_artifact_copy(project_dir, tmp_path):
    run = sl.load_project(project_dir).get("run_a")
    dest = tmp_path / "fetched"
    target = run.fetch_result("mesh", dest)
    assert target == dest / "mesh.txt"
    assert target.read_text() == "artifact content"


def test_fetch_result_figure_copy(project_dir, tmp_path):
    run = sl.load_project(project_dir).get("run_a")
    target = run.fetch_result("fit", tmp_path / "figs")
    assert target.name == "fit.png"
    assert target.exists()


def test_sizes(project_dir):
    run = sl.load_project(project_dir).get("run_a")
    sizes = run.sizes()
    assert sizes["coef"]["kind"] == "result"
    assert sizes["coef"]["bytes"] == 16  # two float64
    assert sizes["mesh"]["kind"] == "artifact"
    assert sizes["mesh"]["bytes"] == len("artifact content")
    assert sizes["fit"]["kind"] == "figure"
    assert sizes["fit"]["bytes"] > 0


def test_export_npz(project_dir, tmp_path):
    run = sl.load_project(project_dir).get("run_a")
    out = run.export(tmp_path / "run_a.npz", format="npz")
    assert out["path"].exists()
    archive = np.load(out["path"], allow_pickle=True)
    assert np.allclose(archive["coef"], [1.323, 323.0])
    assert "coef" in out["exported"]


def test_export_npy_folder(project_dir, tmp_path):
    run = sl.load_project(project_dir).get("run_a")
    out = run.export(tmp_path / "dump", format="npy")
    assert (tmp_path / "dump" / "coef.npy").exists()


def test_export_hdf5_with_identity(project_dir, tmp_path):
    import json

    run = sl.load_project(project_dir).get("run_a")
    out = run.export(tmp_path / "run_a.hdf5", format="hdf5")
    with h5py.File(out["path"], "r") as g:
        assert np.allclose(g["result/coef"][()], [1.323, 323.0])
        assert g.attrs["run_name"] == "run_a"
        assert json.loads(g.attrs["parameters"])["optimizer"] == "adam"


def test_export_bad_format(project_dir):
    run = sl.load_project(project_dir).get("run_a")
    with pytest.raises(ValueError):
        run.export(format="zip")


# ==========================================
#          RUN ANNOTATION
# ==========================================


def test_run_add_note_tag_metadata(project_dir):
    project = sl.load_project(project_dir)
    run = project.get("run_b")

    run.add_note("checked by hand")
    run.add_tag(["reviewed", "v2"])
    run.add_metadata("instrument", "laser-3")
    run.add_metadata({"campaign": "june"})

    fresh = project.get("run_b")
    assert "checked by hand" in fresh.notes
    assert {"reviewed", "v2"} <= set(fresh.tags)
    assert fresh.metadata["instrument"] == "laser-3"
    assert fresh.metadata["campaign"] == "june"


# ==========================================
#          RUN DELETION
# ==========================================


def test_run_delete(project_dir):
    project = sl.load_project(project_dir)
    run = project.get("run_a")

    out = run.delete()
    assert out["status"] == "success"
    assert out["deleted"] == "run_a"

    # The run is gone from the DB and the storage dirs are removed.
    assert project.runs().list() == ["run_b"]
    assert not (project_dir / ".sillon" / "glob" / RUN_A_UUID).exists()
    assert not (project_dir / ".sillon" / "artifact" / RUN_A_UUID).exists()
    assert not (project_dir / ".sillon" / "figure" / RUN_A_UUID).exists()
    with pytest.raises(LookupError):
        project.get("run_a")


def test_sl_delete_run(project_dir):
    project = sl.load_project(project_dir)
    run = project.get("run_b")
    assert sl.delete_run(run)["status"] == "success"
    assert project.runs().list() == ["run_a"]


def test_project_delete_run_by_name(project_dir):
    project = sl.load_project(project_dir)
    out = project.delete_run("run_a")
    assert out["status"] == "success"
    assert "run_a" not in project.runs().list()


def test_delete_missing_run(project_dir):
    project = sl.load_project(project_dir)
    assert project.delete_run("ghost")["status"] == "error"


def test_sl_delete_run_rejects_non_run(project_dir):
    with pytest.raises(TypeError):
        sl.delete_run("run_a")


def test_run_add_metadata_requires_value(project_dir):
    run = sl.load_project(project_dir).get("run_b")
    with pytest.raises(ValueError):
        run.add_metadata("orphan_key")


# ==========================================
#          PARAMETER QUERIES
# ==========================================


def test_project_query_equality(project_dir):
    project = sl.load_project(project_dir)
    assert project.query(optimizer="adam").list() == ["run_a"]


def test_project_query_predicate(project_dir):
    project = sl.load_project(project_dir)
    matching = project.query(learning_rate=lambda lr: lr > 0.015)
    assert matching.list() == ["run_b"]


def test_project_query_missing_param_excludes(project_dir):
    # run_b has no "optimizer" parameter so any condition on it excludes it
    project = sl.load_project(project_dir)
    assert "run_b" not in project.query(optimizer=lambda v: True).list()


def test_collection_where(project_dir):
    runs = sl.load_project(project_dir).runs()
    assert runs.where(learning_rate=0.01).list() == ["run_a"]
    assert runs.where(learning_rate=lambda v: v <= 0.02).list() == ["run_a", "run_b"]


def test_project_query_has_result(project_dir):
    project = sl.load_project(project_dir)
    # run_a has the "coef" glob result and the "external" plain result; run_b has none
    assert project.query(has_result="coef").list() == ["run_a"]
    assert project.query(has_result="external").list() == ["run_a"]


def test_project_query_has_artifact(project_dir):
    project = sl.load_project(project_dir)
    assert project.query(has_artifact="mesh").list() == ["run_a"]
    assert project.query(has_artifact="does_not_exist").list() == []


def test_project_query_combined(project_dir):
    project = sl.load_project(project_dir)
    assert project.query(optimizer="adam", has_artifact="mesh").list() == ["run_a"]
    # parameter matches run_a but the artifact filter excludes it
    assert project.query(optimizer="adam", has_artifact="ghost").list() == []


def test_collection_where_has_result(project_dir):
    runs = sl.load_project(project_dir).runs()
    assert runs.where(has_result="coef").list() == ["run_a"]
    assert runs.where(has_artifact="mesh").list() == ["run_a"]


def test_project_query_result_value_condition(project_dir):
    project = sl.load_project(project_dir)
    # Equality on a plain (string) result value.
    assert project.query(results={"external": "/data/external.txt"}).list() == ["run_a"]
    # Predicate on a glob-stored array result.
    assert project.query(results={"coef": lambda v: float(v[0]) > 1}).list() == ["run_a"]
    assert project.query(results={"coef": lambda v: float(v[0]) > 999}).list() == []
    # A run missing the result is excluded.
    assert "run_b" not in project.query(results={"coef": lambda v: True}).list()


def test_collection_where_result_value_condition(project_dir):
    runs = sl.load_project(project_dir).runs()
    assert runs.where(results={"external": "/data/external.txt"}).list() == ["run_a"]
    assert runs.where(results={"coef": lambda v: float(v[-1]) == 323.0}).list() == ["run_a"]


def test_project_query_analysis_value_and_presence(project_dir):
    project = sl.load_project(project_dir)
    project.get("run_a").add_analysis("fit_rmse", 0.0005)

    # presence
    assert project.query(has_analysis="fit_rmse").list() == ["run_a"]
    assert project.query(has_analysis="missing").list() == []
    # value predicate
    assert project.query(analyses={"fit_rmse": lambda v: v < 0.001}).list() == ["run_a"]
    assert project.query(analyses={"fit_rmse": lambda v: v > 1.0}).list() == []


def test_collection_where_analysis(project_dir):
    project = sl.load_project(project_dir)
    project.get("run_a").add_analysis("fit_rmse", 0.0005)
    runs = project.runs()
    assert runs.where(has_analysis="fit_rmse").list() == ["run_a"]
    assert runs.where(analyses={"fit_rmse": lambda v: v < 0.001}).list() == ["run_a"]


def test_query_mixed_criteria(project_dir):
    project = sl.load_project(project_dir)
    project.get("run_a").add_analysis("fit_rmse", 0.0005)
    # parameter + result predicate + analysis presence, all must hold
    matching = project.query(
        optimizer="adam",
        results={"coef": lambda v: float(v[0]) > 1},
        has_analysis="fit_rmse",
    )
    assert matching.list() == ["run_a"]


# ==========================================
#       CHEAP DIMENSIONS (metadata/tag/date/fields)
# ==========================================


def test_project_query_metadata(project_dir):
    project = sl.load_project(project_dir)
    assert project.query(metadata={"sillon.language": "python 3.13"}).list() == ["run_a"]
    assert project.query(has_metadata="sillon.language").list() == ["run_a"]
    assert project.query(metadata={"sillon.language": lambda v: "3.13" in v}).list() == ["run_a"]


def test_project_query_tag(project_dir):
    project = sl.load_project(project_dir)
    assert project.query(tags="baseline").list() == ["run_a"]
    assert project.query(has_tag="baseline").list() == ["run_a"]
    assert project.query(tags="missing").list() == []


def test_project_query_date(project_dir):
    project = sl.load_project(project_dir)
    # run_a is 2026-06-01, run_b is 2026-06-02
    assert project.query(before="2026-06-02").list() == ["run_a"]
    assert project.query(after="2026-06-02").list() == ["run_b"]


def test_project_query_fields_status(project_dir):
    project = sl.load_project(project_dir)
    assert project.query(fields={"status": "SUCCESS"}).list() == ["run_a"]
    assert project.query(fields={"status": "FAILED"}).list() == ["run_b"]


def test_collection_where_metadata_and_tag(project_dir):
    runs = sl.load_project(project_dir).runs()
    assert runs.where(metadata={"sillon.language": "python 3.13"}).list() == ["run_a"]
    assert runs.where(tags="baseline").list() == ["run_a"]


# ==========================================
#       TWO-PHASE OPTIMIZATION (glob-open proof)
# ==========================================


def test_pure_cheap_query_reads_no_globs(project_dir, monkeypatch):
    import silloncore.engine as engine

    calls = {"n": 0}
    real = engine.read_glob_many

    def counting(*a, **k):
        calls["n"] += 1
        return real(*a, **k)

    monkeypatch.setattr(engine, "read_glob_many", counting)

    project = sl.load_project(project_dir)
    # Cheap-only query (param + tag + status): must touch zero globs.
    assert project.query(optimizer="adam", tags="baseline",
                         fields={"status": "SUCCESS"}).list() == ["run_a"]
    assert calls["n"] == 0


def test_heavy_query_reads_globs_only_for_survivors(project_dir, monkeypatch):
    import silloncore.engine as engine

    seen_uuids = []
    real = engine.read_glob_many

    def tracking(storage_root, uuid, datasets):
        seen_uuids.append(uuid)
        return real(storage_root, uuid, datasets)

    monkeypatch.setattr(engine, "read_glob_many", tracking)

    project = sl.load_project(project_dir)
    # Cheap filter (optimizer=adam) excludes run_b before any glob is opened;
    # only run_a's glob is read for the result predicate.
    matching = project.query(optimizer="adam", results={"coef": lambda v: float(v[0]) > 1})
    assert matching.list() == ["run_a"]
    assert seen_uuids == [RUN_A_UUID]


# ==========================================
#          FIGURES
# ==========================================


def test_run_figures_provenance(project_dir):
    run = sl.load_project(project_dir).get("run_a")
    figures = run.figures
    assert "fit" in figures
    assert figures["fit"]["used"] == ["learning_rate", "coef"]
    assert figures["fit"]["caption"] == "Linear fit"


def test_run_load_figure(project_dir):
    run = sl.load_project(project_dir).get("run_a")
    path = run.load_figure("fit")
    assert path.name == "fit.png"
    assert path.exists()
    with pytest.raises(LookupError):
        run.load_figure("nope")


# ==========================================
#          ANALYSES
# ==========================================


def test_add_and_load_analysis(project_dir):
    project = sl.load_project(project_dir)
    run = project.get("run_a")

    grid = np.linspace(0, 1, 50)
    fitted = 1.323 * grid + 323.0
    row = run.add_analysis("fitted_curve", fitted, inputs=["coef"], comment="fine grid")
    assert row["name"] == "fitted_curve"
    assert row["hsh"]

    # Reload from a brand new handle: data and context survived
    fresh = project.get("run_a")
    assert "fitted_curve" in fresh.analyses
    assert fresh.analyses["fitted_curve"]["inputs"] == ["coef"]
    assert np.allclose(fresh.load_analysis("fitted_curve"), fitted)


def test_load_missing_analysis(project_dir):
    run = sl.load_project(project_dir).get("run_a")
    with pytest.raises(LookupError):
        run.load_analysis("nope")


def test_analysis_in_export_and_sizes(project_dir, tmp_path):
    run = sl.load_project(project_dir).get("run_a")
    run.add_analysis("processed", np.arange(10.0))

    sizes = run.sizes()
    assert sizes["processed"]["kind"] == "analysis"

    out = run.export(tmp_path / "all.npz")
    archive = np.load(out["path"])
    assert np.allclose(archive["analysis.processed"], np.arange(10.0))


# ==========================================
#          CONTEXT REPORT BUNDLE
# ==========================================


def test_run_manifest(project_dir):
    manifest = sl.load_project(project_dir).get("run_a").manifest()
    assert manifest["name"] == "run_a"
    assert manifest["status"] == "SUCCESS"
    assert manifest["parameters"]["optimizer"] == "adam"
    assert manifest["figures"]["fit"]["used"] == ["learning_rate", "coef"]
    assert "coef" in manifest["results"]


def test_run_report_zip_contents(project_dir, tmp_path):
    import zipfile

    run = sl.load_project(project_dir).get("run_a")
    bundle = run.report(tmp_path / "run_a_report.zip")
    assert bundle.exists()

    with zipfile.ZipFile(bundle) as z:
        names = z.namelist()
        assert "manifest.json" in names
        assert "report.md" in names
        assert "source/main.py" in names
        assert "data.hdf5" not in names  # with_data defaults to False
        assert "print('hello sillon')" in z.read("source/main.py").decode()
        assert "run_a" in z.read("report.md").decode()


def test_run_report_with_data(project_dir, tmp_path):
    import zipfile

    run = sl.load_project(project_dir).get("run_a")
    bundle = run.report(tmp_path / "full.zip", with_data=True)
    with zipfile.ZipFile(bundle) as z:
        assert "data.hdf5" in z.namelist()


# ==========================================
#          DATAFRAMES
# ==========================================


def test_collection_to_dataframe_metadata(project_dir):
    pd = pytest.importorskip("pandas")
    runs = sl.load_project(project_dir).runs()
    df = runs.to_dataframe(metadata=True)
    assert len(df) == 2
    assert "learning_rate" in df.columns
    assert "sillon.language" in df.columns
    assert df[df["name"] == "run_a"]["sillon.language"].iloc[0] == "python 3.13"


def test_run_to_dataframe(project_dir):
    pd = pytest.importorskip("pandas")
    run = sl.load_project(project_dir).get("run_a")
    df = run.to_dataframe(metadata=True)
    assert len(df) == 1
    assert df["optimizer"].iloc[0] == "adam"


# ==========================================
#             PRETTY PRINTING
# ==========================================


def test_project_show_overview(project_dir, capsys):
    sl.load_project(project_dir).show()
    out = capsys.readouterr().out
    assert "run_a" in out
    assert "run_b" in out
    assert "2 runs" in out


def test_project_show_specific(project_dir, capsys):
    sl.load_project(project_dir).show("run_a")
    out = capsys.readouterr().out
    assert "run_a" in out
    assert "run_b" not in out


def test_run_show(project_dir, capsys):
    sl.load_project(project_dir).get("run_a").show()
    out = capsys.readouterr().out
    assert "run_a" in out
    assert "learning_rate" in out
    assert "baseline" in out


def test_collection_show(project_dir, capsys):
    sl.load_project(project_dir).runs().show()
    out = capsys.readouterr().out
    assert "run_a" in out
    assert "run_b" in out


# ==========================================
#          POLISH: rename
# ==========================================


def test_run_rename(project_dir):
    project = sl.load_project(project_dir)
    run = project.get("run_a")
    out = run.rename("renamed_a")
    assert out["status"] == "success"
    assert out["old"] == "run_a" and out["new"] == "renamed_a"
    assert run.name == "renamed_a"
    assert sorted(project.runs().list()) == ["renamed_a", "run_b"]


def test_rename_rejects_existing_name(project_dir):
    project = sl.load_project(project_dir)
    out = project.rename("run_a", "run_b")  # run_b already exists
    assert out["status"] == "error"
    assert "taken" in out["message"]
    assert sorted(project.runs().list()) == ["run_a", "run_b"]


def test_rename_missing_run(project_dir):
    out = sl.load_project(project_dir).rename("ghost", "x")
    assert out["status"] == "error"


# ==========================================
#          POLISH: find-by-hash
# ==========================================


def test_find_by_hash_figure_and_artifact(project_dir):
    project = sl.load_project(project_dir)
    # The fixture's figure 'fit' has hsh 'fig456'; artifact 'mesh' has 'abc123'.
    fig_matches = project.find_by_hash("fig456")
    assert fig_matches == [
        {"run_name": "run_a", "run_uuid": RUN_A_UUID, "kind": "figure", "name": "fit"}
    ]
    art_matches = project.find_by_hash("abc123")
    assert art_matches[0]["kind"] == "artifact"
    assert art_matches[0]["name"] == "mesh"
    assert project.find_by_hash("nope") == []


def test_find_by_hash_from_file(project_dir, tmp_path):
    # Hashing a real file: write content, compute its hash, store an artifact with it.
    from sqlmodel import select
    from silloncore.glob import get_hash

    f = tmp_path / "blob.bin"
    f.write_bytes(b"hello sillon")
    h = get_hash(str(f))
    engine = sl.load_project(project_dir).engine
    with Session(engine) as session:
        run = session.exec(
            select(SimulationTable).where(SimulationTable.name == "run_b")
        ).first()
        session.add(ArtifactTable(name="blob", hsh=h, path="p", run_id=run.id))
        session.commit()
    matches = sl.load_project(project_dir).find_by_hash(str(f))
    assert matches[0]["run_name"] == "run_b" and matches[0]["name"] == "blob"


# ==========================================
#          POLISH: uuid-prefix lookup
# ==========================================


def test_get_by_uuid_and_ambiguous_prefix(project_dir):
    project = sl.load_project(project_dir)
    # Exact uuid resolves.
    assert project.get(RUN_A_UUID).name == "run_a"
    # The two fixture uuids share their first 35 chars, so a short prefix is
    # ambiguous and must be rejected rather than guessed.
    with pytest.raises(LookupError):
        project.get("11111111")


# ==========================================
#          POLISH: notebook repr + metadata short key + dropped log alias
# ==========================================


def test_run_repr_html(project_dir):
    html = sl.load_project(project_dir).get("run_a")._repr_html_()
    assert "<" in html and "run_a" in html


def test_collection_repr_html(project_dir):
    html = sl.load_project(project_dir).runs()._repr_html_()
    assert "run_a" in html and "run_b" in html


def test_query_metadata_short_key(project_dir):
    # Runs logged via sillonpy store user metadata namespaced as
    # 'sillon.user_metadata.<key>'; a query for the short key must still match.
    project = sl.load_project(project_dir)
    project.get("run_a").add_metadata("sillon.user_metadata.dataset", "mnist")
    assert project.query(metadata={"dataset": "mnist"}).list() == ["run_a"]
    assert project.query(has_metadata="dataset").list() == ["run_a"]


def test_sillonpy_log_metadata_is_alias():
    import sillonpy as sp

    assert sp.log_metadata is sp.add_metadata
    assert hasattr(sp, "track_run")
