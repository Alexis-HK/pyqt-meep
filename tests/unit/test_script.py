from __future__ import annotations

import pytest

from meep_gui.model import (
    AnalysisConfig,
    Domain,
    FluxMonitorConfig,
    FrequencyDomainSolverConfig,
    KPoint,
    MeepKPointsConfig,
    MpbModeSolverConfig,
    Parameter,
    ProjectState,
    SourceItem,
    SweepConfig,
    SweepParameter,
    SymmetryItem,
    TransmissionDomainState,
    TransmissionSpectrumConfig,
)
from meep_gui.script import generate_script


def test_harminv_script_writes_outputs_to_subfolder() -> None:
    state = ProjectState(
        domain=Domain(
            symmetry_enabled=True,
            symmetries=[SymmetryItem(name="mx", kind="mirror", direction="x", phase="-1")],
        ),
        analysis=AnalysisConfig(kind="harminv"),
    )

    code = generate_script(state)

    assert "script_dir = os.path.dirname(os.path.abspath(__file__))" in code
    assert "_complex_eval" not in code
    assert "import ast" not in code
    assert "import cmath" not in code
    assert "symmetries = []" in code
    assert "symmetries.append(mp.Mirror(mp.X, phase=-1))" in code
    assert "symmetries=symmetries" in code
    assert "out_dir = os.path.join(script_dir, 'harminv_outputs')" in code
    assert "os.makedirs(out_dir, exist_ok=True)" in code
    assert "run_domain_preview_out = os.path.join(out_dir, 'domain_preview.png')" in code
    assert "anim_out = os.path.join(out_dir, \"harminv_animation.mp4\")" in code
    assert "harminv_out = os.path.join(out_dir, \"harminv.txt\")" in code
    assert "marker_expr=('0', '0')" in code
    assert "with open(harminv_out, 'w', encoding='utf-8') as f:" in code


def test_field_animation_script_uses_out_dir_and_flux_exports() -> None:
    state = ProjectState(
        flux_monitors=[FluxMonitorConfig(name="tx")],
        analysis=AnalysisConfig(kind="field_animation"),
    )

    code = generate_script(state)

    assert "run_domain_preview_out = os.path.join(out_dir, 'domain_preview.png')" in code
    assert "anim_out = os.path.join(out_dir, \"animation.mp4\")" in code
    assert "anim_out = os.path.join(script_dir, \"animation.mp4\")" not in code
    assert "csv_path = os.path.join(out_dir, f'{monitor_name}_flux.csv')" in code
    assert "csv_path = os.path.join(script_dir, f'{monitor_name}_flux.csv')" not in code


def test_mpb_script_includes_te_tm_field_and_tutorial_epsilon_plot() -> None:
    state = ProjectState(
        analysis=AnalysisConfig(
            kind="mpb_modesolver",
            mpb_modesolver=MpbModeSolverConfig(
                run_tm=True,
                run_te=True,
                unit_cells="3",
                kpoints=[KPoint(kx="0", ky="0"), KPoint(kx="0.5", ky="0")],
                field_kpoints=[KPoint(kx="0.2", ky="0.1")],
            ),
        )
    )

    code = generate_script(state)

    assert "run_pols.append('tm')" in code
    assert "run_pols.append('te')" in code
    assert "out_dir = os.path.join(script_dir, 'mpb_outputs')" in code
    assert "os.makedirs(out_dir, exist_ok=True)" in code
    assert "field_k_points = [" in code
    assert "mp.Vector3(0.2, 0.1, 0)" in code
    assert "field_k_points = list(k_points_raw)" not in code
    assert "mode_limit = min(total_mode_images, max_mode_images)" in code
    assert "return getter(band, bloch_phase=True)" in code
    assert "plt.imshow(converted_eps.T, interpolation='spline36', cmap='binary')" in code
    assert "plt.imshow(arr.T, interpolation='spline36', cmap='RdBu'" in code
    assert "mode_{pol}_k{k_idx:03d}_b{band:03d}.png" in code
    assert "domain_preview.png" not in code


def test_mpb_script_skips_field_image_fallback_when_no_field_kpoints() -> None:
    state = ProjectState(
        analysis=AnalysisConfig(
            kind="mpb_modesolver",
            mpb_modesolver=MpbModeSolverConfig(
                kpoints=[KPoint(kx="0", ky="0"), KPoint(kx="0.5", ky="0")],
                field_kpoints=[],
            ),
        )
    )

    code = generate_script(state)

    assert "field_k_points = [" in code
    assert "field_k_points = list(k_points_raw)" not in code
    assert "# Field images are only generated for explicitly configured field_k_points." in code
    assert "band_csv = os.path.join(out_dir, 'mpb_bands.csv')" in code
    assert "plt.savefig(os.path.join(out_dir, 'mpb_epsilon.png'))" in code
    assert "domain_preview.png" not in code


def test_transmission_script_uses_split_reference_and_scattering_state() -> None:
    state = ProjectState(
        sources=[
            SourceItem(name="dev_src", kind="gaussian", component="Ez", props={"fcen": "0.2", "df": "0.1"})
        ],
        flux_monitors=[FluxMonitorConfig(name="dev_tx"), FluxMonitorConfig(name="dev_refl")],
        analysis=AnalysisConfig(
            kind="transmission_spectrum",
            transmission_spectrum=TransmissionSpectrumConfig(
                incident_monitor="ref_inc",
                transmission_monitor="dev_tx",
                reflection_monitor="dev_refl",
                reference_reflection_monitor="ref_refl",
                animate_reference=True,
                animate_scattering=True,
                animation_component="Hz",
                animation_interval="2",
                animation_fps="24",
                reference_state=TransmissionDomainState(
                    domain=Domain(
                        symmetry_enabled=True,
                        symmetries=[
                            SymmetryItem(name="ref_sym", kind="mirror", direction="y", phase="-1")
                        ],
                    ),
                    sources=[
                        SourceItem(
                            name="ref_src",
                            kind="gaussian",
                            component="Ez",
                            props={"fcen": "0.2", "df": "0.1"},
                        )
                    ],
                    flux_monitors=[
                        FluxMonitorConfig(name="ref_inc"),
                        FluxMonitorConfig(name="ref_refl"),
                    ],
                ),
            ),
        ),
    )

    code = generate_script(state)

    assert "reference_incident_csv = 'transmission_spectrum.csv'" in code
    assert "reference_incident_path = os.path.join(out_dir, reference_incident_csv)" in code
    assert "use_cached_reference = cached_ref_freqs is not None and cached_incident_ref is not None" in code
    assert "ref_refl_monitor_name = 'ref_refl'" in code
    assert "out_dir = os.path.join(script_dir, 'transmission_outputs')" in code
    assert "os.makedirs(out_dir, exist_ok=True)" in code
    assert "ref_sources = []" in code
    assert "ref_symmetries = []" in code
    assert "_complex_eval" not in code
    assert "ref_symmetries.append(mp.Mirror(mp.Y, phase=-1))" in code
    assert "dev_symmetries = []" in code
    assert "sim_ref = mp.Simulation(" in code
    assert "symmetries=ref_symmetries" in code
    assert "ref_domain_preview_out = os.path.join(out_dir, 'domain_preview_reference.png')" in code
    assert "ref_flux_handles['ref_inc'] = sim_ref.add_flux" in code
    assert "dev_flux_handles['dev_tx'] = sim_dev.add_flux" in code
    assert "symmetries=dev_symmetries" in code
    assert "dev_domain_preview_out = os.path.join(out_dir, 'domain_preview_scattering.png')" in code
    assert "sim_dev.load_minus_flux_data(dev_flux_handles[refl_monitor_name], minus_flux_data)" in code
    assert "def _transmission_stop_condition(domain_name):" in code
    assert "return 200" in code
    assert "ref_anim = mp.Animate2D(fields=anim_component, realtime=False) if animate_ref else None" in code
    assert "dev_anim = mp.Animate2D(fields=anim_component, realtime=False) if animate_dev else None" in code
    assert "sim_ref.run(*ref_step_funcs, until_after_sources=_transmission_stop_condition('reference'))" in code
    assert "sim_dev.run(*dev_step_funcs, until_after_sources=_transmission_stop_condition('scattering'))" in code
    assert "if (not use_cached_reference) and ref_anim is not None:" in code
    assert "ref_anim.to_mp4(anim_fps, os.path.join(out_dir, f\"{safe_prefix}_reference.mp4\"))" in code
    assert "dev_anim.to_mp4(anim_fps, os.path.join(out_dir, f\"{safe_prefix}_scattering.mp4\"))" in code
    assert "if len(freqs) != len(ref_freqs):" in code
    assert "if abs(float(f_dev) - float(f_ref)) > 1e-12:" in code


def test_transmission_script_emits_per_domain_field_decay_stop_conditions() -> None:
    state = ProjectState(
        flux_monitors=[FluxMonitorConfig(name="dev_tx")],
        analysis=AnalysisConfig(
            kind="transmission_spectrum",
            transmission_spectrum=TransmissionSpectrumConfig(
                incident_monitor="ref_inc",
                transmission_monitor="dev_tx",
                stop_condition="field_decay",
                field_decay_component="Hz",
                reference_field_decay_additional_time="a + 5",
                reference_field_decay_point_x="1",
                reference_field_decay_point_y="2",
                reference_field_decay_by="1e-4",
                scattering_field_decay_additional_time="a + 7",
                scattering_field_decay_point_x="3",
                scattering_field_decay_point_y="4",
                scattering_field_decay_by="5e-4",
                reference_state=TransmissionDomainState(
                    flux_monitors=[FluxMonitorConfig(name="ref_inc")]
                ),
            ),
        ),
        parameters=[Parameter(name="a", expr="10")],
    )

    code = generate_script(state)

    assert "def _transmission_stop_condition(domain_name):" in code
    assert "return mp.stop_when_fields_decayed(" in code
    assert "mp.Hz" in code
    assert "mp.Vector3(1, 2, 0)" in code
    assert "mp.Vector3(3, 4, 0)" in code
    assert "a + 5" in code
    assert "a + 7" in code
    assert "ref_domain_preview_out = os.path.join(out_dir, 'domain_preview_reference.png')" in code
    assert "marker_expr=('1', '2')" in code
    assert "dev_domain_preview_out = os.path.join(out_dir, 'domain_preview_scattering.png')" in code
    assert "marker_expr=('3', '4')" in code
    assert "sim_ref.run(*ref_step_funcs, until_after_sources=_transmission_stop_condition('reference'))" in code
    assert "sim_dev.run(*dev_step_funcs, until_after_sources=_transmission_stop_condition('scattering'))" in code


def test_frequency_domain_script_uses_solve_cw_and_omits_flux_exports() -> None:
    state = ProjectState(
        sources=[
            SourceItem(
                name="cw_src",
                kind="continuous",
                component="Hz",
                props={"fcen": "0.2"},
            )
        ],
        flux_monitors=[FluxMonitorConfig(name="unused_flux")],
        analysis=AnalysisConfig(
            kind="frequency_domain_solver",
            frequency_domain_solver=FrequencyDomainSolverConfig(
                component="Hz",
                tolerance="1e-9",
                max_iters="2048",
                bicgstab_l="16",
            ),
        ),
    )

    code = generate_script(state)

    assert "force_complex_fields=True" in code
    assert "field_component = mp.Hz" in code
    assert "sim.init_sim()" in code
    assert "sim.solve_cw(1e-9, int(2048), int(16))" in code
    assert "sample_size = mp.Vector3(10, 10, 0)" in code
    assert "np.squeeze(np.real(field_arr))" in code
    assert "np.savetxt(field_csv, field_arr.T, delimiter=',')" in code
    assert "if hasattr(sim, 'plot2D'):" in code
    assert "sim.plot2D(" in code
    assert "out_dir = os.path.join(script_dir, 'frequency_domain_outputs')" in code
    assert "run_domain_preview_out = os.path.join(out_dir, 'domain_preview.png')" in code
    assert "sim.add_flux" not in code
    assert "for monitor_name, monitor_obj in flux_monitors:" not in code


def test_frequency_domain_script_warns_when_no_sources_are_configured() -> None:
    state = ProjectState(analysis=AnalysisConfig(kind="frequency_domain_solver"))

    code = generate_script(state)

    assert "Warning: no sources are configured; frequency-domain solve may produce a zero field." in code


def test_generate_script_rejects_gaussian_source_for_frequency_domain() -> None:
    state = ProjectState(
        sources=[
            SourceItem(
                name="pulse",
                kind="gaussian",
                component="Ez",
                props={"fcen": "0.2", "df": "0.1"},
            )
        ],
        analysis=AnalysisConfig(kind="frequency_domain_solver"),
    )

    with pytest.raises(ValueError, match="Frequency-domain solver supports only continuous sources"):
        generate_script(state)


def test_meep_k_points_script_emits_run_k_points_plot_and_csv() -> None:
    state = ProjectState(
        sources=[
            SourceItem(
                name="pulse",
                kind="gaussian",
                component="Ez",
                props={"fcen": "0.2", "df": "0.1"},
            )
        ],
        flux_monitors=[FluxMonitorConfig(name="unused_flux")],
        analysis=AnalysisConfig(
            kind="meep_k_points",
            meep_k_points=MeepKPointsConfig(
                kpoint_interp="19",
                run_time="300",
                kpoints=[KPoint(kx="0", ky="0"), KPoint(kx="0.5", ky="0")],
            ),
        ),
    )

    code = generate_script(state)

    assert "out_dir = os.path.join(script_dir, 'meep_k_points_outputs')" in code
    assert "k_points = mp.interpolate(int(19), input_k_points)" in code
    assert "all_freqs = sim.run_k_points(300, k_points)" in code
    assert "run_domain_preview_out = os.path.join(out_dir, 'domain_preview.png')" in code
    assert "writer.writerow(['k_index', 'kx', 'ky', 'mode', 'freq_real', 'freq_imag'])" in code
    assert "plt.xlabel('k-index')" in code
    assert "plt.scatter(scatter_x, scatter_y, s=18, color='#1f77b4')" in code
    assert "sim.add_flux" not in code
    assert "for monitor_name, monitor_obj in flux_monitors:" not in code
    assert "plt.xticks(" not in code


def test_meep_k_points_script_uses_raw_points_when_interp_is_zero() -> None:
    state = ProjectState(
        sources=[
            SourceItem(
                name="pulse",
                kind="gaussian",
                component="Ez",
                props={"fcen": "0.2", "df": "0.1"},
            )
        ],
        analysis=AnalysisConfig(
            kind="meep_k_points",
            meep_k_points=MeepKPointsConfig(
                kpoint_interp="0",
                run_time="300",
                kpoints=[KPoint(kx="0", ky="0"), KPoint(kx="0.5", ky="0")],
            ),
        ),
    )

    code = generate_script(state)

    assert "mp.interpolate(" not in code
    assert "k_points = input_k_points" in code


def test_generate_script_rejects_invalid_meep_k_points_inputs() -> None:
    empty_sources = ProjectState(
        analysis=AnalysisConfig(
            kind="meep_k_points",
            meep_k_points=MeepKPointsConfig(
                kpoints=[KPoint(kx="0", ky="0"), KPoint(kx="0.5", ky="0")]
            ),
        )
    )
    with pytest.raises(ValueError, match="requires at least one Gaussian"):
        generate_script(empty_sources)

    continuous = ProjectState(
        sources=[
            SourceItem(
                name="cw",
                kind="continuous",
                component="Ez",
                props={"fcen": "0.2"},
            )
        ],
        analysis=AnalysisConfig(
            kind="meep_k_points",
            meep_k_points=MeepKPointsConfig(
                kpoints=[KPoint(kx="0", ky="0"), KPoint(kx="0.5", ky="0")]
            ),
        ),
    )
    with pytest.raises(ValueError, match="Continuous sources are not supported"):
        generate_script(continuous)

    too_few_points = ProjectState(
        sources=[
            SourceItem(
                name="pulse",
                kind="gaussian",
                component="Ez",
                props={"fcen": "0.2", "df": "0.1"},
            )
        ],
        analysis=AnalysisConfig(
            kind="meep_k_points",
            meep_k_points=MeepKPointsConfig(kpoints=[KPoint(kx="0", ky="0")]),
        ),
    )
    with pytest.raises(ValueError, match="at least two input k-points"):
        generate_script(too_few_points)


def test_mpb_script_notes_domain_symmetries_are_ignored() -> None:
    state = ProjectState(
        domain=Domain(
            symmetry_enabled=True,
            symmetries=[SymmetryItem(name="mz", kind="mirror", direction="z", phase="1")],
        ),
        analysis=AnalysisConfig(kind="mpb_modesolver"),
    )

    code = generate_script(state)

    assert "# Note: domain symmetries are FDTD-only and are not applied to MPB." in code


def test_generate_script_rejects_non_literal_symmetry_phase() -> None:
    state = ProjectState(
        domain=Domain(
            symmetry_enabled=True,
            symmetries=[SymmetryItem(name="mx", kind="mirror", direction="x", phase="a*1j")],
        ),
        analysis=AnalysisConfig(kind="harminv"),
    )

    try:
        generate_script(state)
    except ValueError as exc:
        assert "symmetry 'mx' phase" in str(exc)
    else:
        raise AssertionError("Expected generate_script() to reject non-literal symmetry phase.")


def test_sweep_enabled_script_emits_runner_and_folder_layout() -> None:
    state = ProjectState(
        analysis=AnalysisConfig(kind="harminv"),
        parameters=[Parameter(name="a", expr="1"), Parameter(name="b", expr="10")],
        sweep=SweepConfig(
            enabled=True,
            params=[
                SweepParameter(name="a", start="1", stop="3", steps="1"),
                SweepParameter(name="b", start="5", stop="7", steps="1"),
            ],
        ),
    )

    code = generate_script(state)

    assert "Sweep configured in GUI; run manually in Python if needed." not in code
    assert "def run_analysis(out_dir, overrides=None):" in code
    assert "analysis_kind = 'harminv'" in code
    assert "sweep_root = _unique_dir(os.path.join(script_dir, f\"{analysis_kind}_sweeps\"))" in code
    assert "row_dir = _unique_dir(os.path.join(sweep_root, _safe_dir_name(f\"{analysis_kind}_{name}\")))" in code
    assert "run_dir = _unique_dir(os.path.join(row_dir, _safe_dir_name(label)))" in code
    assert "run_analysis(run_dir, overrides={name: value})" in code
    assert "print(f\"Sweep {queue_index}/{queue_total}: {label} ({point_index}/{point_total} for {name})\")" in code
    assert "parameter_values = _build_parameter_values(overrides)" in code
    assert "run_domain_preview_out = os.path.join(out_dir, 'domain_preview.png')" in code


def test_sweep_enabled_script_emits_app_like_value_expansion_rules() -> None:
    state = ProjectState(
        analysis=AnalysisConfig(kind="frequency_domain_solver"),
        parameters=[Parameter(name="a", expr="1")],
        sources=[
            SourceItem(
                name="cw_src",
                kind="continuous",
                component="Ez",
                props={"fcen": "0.2"},
            )
        ],
        sweep=SweepConfig(
            enabled=True,
            params=[SweepParameter(name="a", start="1", stop="2", steps="0.5")],
        ),
    )

    code = generate_script(state)

    assert "def _expand_sweep_values(name, start_expr, stop_expr, step_expr, base_values):" in code
    assert "if abs(start - stop) <= eps:" in code
    assert "if abs(step_size) <= eps:" in code
    assert "if stop > start and step_size <= 0:" in code
    assert "if stop < start and step_size >= 0:" in code
    assert "raise ValueError(f\"Sweep parameter '{name}' produced no sweep points.\")" in code
    assert "print(f\"Sweep stopped after {label} failed.\")" in code
    assert "print(f\"Sweep completed. {completed} runs saved under {sweep_root}\")" in code
