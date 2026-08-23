import click
import sys
import os

@click.group()
def cli():
    """DSF Command Line Interface"""
    pass

@cli.command()
@click.argument('xml_file', type=click.Path(exists=True))
@click.option('--h5', is_flag=True, default=False, help="Also write an HDF5 output file.")
@click.option('--not-strict', 'not_strict', is_flag=True, default=False,
              help="Run despite config-validation findings (typo'd attributes, "
                   "failed table loads). Strict mode is the default.")
def run(xml_file, h5, not_strict):
    """Run a simulation from an XML configuration file."""
    argv = ['dsf-run', '--fname', xml_file]
    if h5:
        argv.append('--h5')
    if not_strict:
        argv.append('--not-strict')
    sys.argv = argv

    from dsf.cli import run as dsf_run
    dsf_run.main()

@cli.command()
@click.argument('file', type=click.Path(exists=True), required=False)
@click.option('--import-xml', type=click.Path(exists=True), help="Import DSF XML configuration")
@click.option('--load-lib', multiple=True, help="Load shared library (e.g. libsixdof.so)")
def gui(file, import_xml, load_lib):
    """Launch the DSF interactive GUI."""
    args = ['dsf-gui']
    if import_xml:
        args.extend(['--import-xml', import_xml])
    for lib in load_lib:
        args.extend(['--load-lib', lib])
    if file:
        args.append(file)
    sys.argv = args
    from dsf.gui import main as gui_main
    gui_main.main()

@cli.command()
@click.argument('dsf_file', type=click.Path(exists=True))
@click.option('--console-rate', default=1.0, show_default=True,
              help="Seconds of sim time between console updates.")
@click.option('--h5', is_flag=True, default=False, help="Also write an HDF5 output file.")
def watch(dsf_file, console_rate, h5):
    """
    Run a DSF project with live telemetry output.

    Uses a Python-driven step loop (instead of C++ exec()) to read and display
    variable values after each simulation tick. Slower than 'dsf run' but gives
    per-step visibility. The `watch` list in the project metadata controls which
    variables are displayed.
    """
    from dsf.utils.run_config import load_run_config
    from dsf.utils.convert_dsf_to_xml import convert_dsf_to_xml
    from dsf.cli.watch import run_watch

    try:
        cfg = load_run_config(dsf_file)
    except Exception as e:
        click.echo(f"Error reading project metadata: {e}", err=True)
        sys.exit(1)

    try:
        xml_path = convert_dsf_to_xml(dsf_file)
    except Exception as e:
        click.echo(f"Error converting .dsf to XML: {e}", err=True)
        sys.exit(1)

    rate = console_rate if console_rate else (cfg.console_rate or 1.0)

    try:
        run_watch(
            xml_path=xml_path,
            lib_path=cfg.library,
            dt=cfg.dt,
            tmax=cfg.tmax,
            watch=cfg.watch,
            console_rate=rate,
            is_csv=cfg.is_csv,
            is_hdf5=(cfg.is_hdf5 or h5),
        )
    finally:
        if os.path.exists(xml_path):
            try:
                os.remove(xml_path)
            except OSError:
                pass

@cli.command()
@click.argument('h5_file', type=click.Path(exists=True))
def plot(h5_file):
    """Open an HDF5 output file in the interactive strip-chart viewer."""
    from dsf.cli.plot import run_plot
    run_plot(h5_file)

@cli.command()
@click.argument('h5_file', type=click.Path(exists=True))
def map(h5_file):
    """Open an HDF5 output file in the 2D ground-track map."""
    from dsf.cli.map_view import run_map
    run_map(h5_file)

@cli.command()
@click.argument('h5_file', type=click.Path(exists=True))
def globe(h5_file):
    """Open an HDF5 output file in the 3D orbit globe."""
    from dsf.cli.globe_view import run_globe
    run_globe(h5_file)

@cli.command()
@click.argument('input_file', type=click.Path(exists=True))
@click.option('--terrain-dir', default='', help='Path to terrain/bathymetry tile directory.')
@click.option('--decimation', default=4, help='Terrain grid decimation (lower = finer, default 4).')
@click.option('--cull', default=None, type=float, is_flag=False, flag_value=50.0,
              help='Cull terrain to trajectory bbox grown by percentage. Bare --cull = 50%%. --cull 75 = 75%%.')
@click.option('--z-scale', default=1.0, type=float,
              help='Vertical exaggeration factor (default: 1.0).')
def terrain(input_file, terrain_dir, decimation, cull, z_scale):
    """3D terrain + trajectory visualizer (GPU-accelerated)."""
    from dsf.cli.terrain_view import run_terrain
    run_terrain(input_file, terrain_dir=terrain_dir, decimation=decimation,
                cull_pct=cull, z_scale=z_scale)

@cli.command()
@click.argument('input_file', type=click.Path(exists=True))
@click.option('--port', default=8000, help="Port to run the local server on.")
@click.option('--terrain', default='', help="Path to HGT/DTED terrain data directory.")
def cesium(input_file, port, terrain):
    """Open an HDF5 output file or XML config in the 4D CesiumJS web visualizer."""
    from dsf.cli.cesium_view import run_cesium
    run_cesium(input_file, port=port, terrain_dir=terrain)

# ── Monte Carlo subcommand group ──
from dsf.cli.mc_cli import mc
cli.add_command(mc)

# ── Remote-run subcommand group ──
from dsf.cli.remote_cli import remote
cli.add_command(remote)

if __name__ == '__main__':
    cli()
