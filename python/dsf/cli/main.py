import click
import sys
import os

@click.group()
def cli():
    """DSF Command Line Interface"""
    pass

@cli.command()
@click.argument('xml_file', type=click.Path(exists=True))
def run(xml_file):
    """Run a simulation from an XML configuration file."""
    # Patch sys.argv for run.main() which expects --fname
    sys.argv = ['dsf-run', '--fname', xml_file]
    
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
def watch(dsf_file, console_rate):
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
        )
    finally:
        if os.path.exists(xml_path):
            try:
                os.remove(xml_path)
            except OSError:
                pass

if __name__ == '__main__':
    cli()
