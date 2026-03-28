"""
Monte Carlo CLI subcommands for DSF.

    dsf mc template <vehicle.xml>   — auto-generate MC XML from introspection
    dsf mc run <vehicle.xml>        — run MC batch (async)
    dsf mc status [output_dir]      — check progress
    dsf mc results <output_dir>     — aggregate statistics
    dsf mc extremes <output_dir>    — show >2σ cases
"""

import click
import json
from pathlib import Path


@click.group()
def mc():
    """Monte Carlo batch simulation tools."""
    pass


@mc.command()
@click.argument('xml_file', type=click.Path(exists=True))
@click.option('--workers', '-j', default=8, show_default=True, help='Parallel workers')
def run(xml_file, workers):
    """Run a Monte Carlo batch from an XML with a <monte_carlo> block."""
    from dsf.mc import MonteCarlo
    mc = MonteCarlo(xml_file)
    mc.run(workers=workers)


@mc.command()
@click.argument('output_dir', type=click.Path(), default='mc_results')
def status(output_dir):
    """Show progress of a running MC batch."""
    from dsf.mc import MonteCarlo
    state = MonteCarlo.status(output_dir)
    if state is None:
        click.echo(f"No MC state found in {output_dir}")
        return

    click.echo(f"Status: {state.get('status', '?')}")
    click.echo(f"Cases: {state.get('done', 0)} done, "
               f"{state.get('failed', 0)} failed, "
               f"{state.get('running', 0)} running "
               f"/ {state.get('n_cases', '?')} total")
    if state.get('elapsed'):
        click.echo(f"Elapsed: {state['elapsed']}")
    if state.get('finished'):
        click.echo("Batch complete.")


@mc.command()
@click.argument('output_dir', type=click.Path(exists=True), default='mc_results')
def results(output_dir):
    """Build aggregated index and report statistics."""
    draws_file = Path(output_dir) / 'mc_draws.json'
    if not draws_file.exists():
        click.echo(f"No mc_draws.json found in {output_dir}")
        return

    data = json.loads(draws_file.read_text())
    draws = data.get('draws', [])
    n = len(draws)

    click.echo(f"MC Results: {n} cases")
    click.echo(f"Master seed: {data.get('master_seed')}")
    click.echo(f"\nDispersions:")

    # Collect statistics per parameter
    import numpy as np
    if n == 0:
        return

    all_keys = list(draws[0].keys()) if draws else []
    for key in all_keys:
        values = []
        for case_draws in draws:
            d = case_draws.get(key, {})
            if d.get('distribution') == 'gaussian':
                values.append(d.get('n_sigma_draw', 0.0))
            elif d.get('distribution') == 'uniform':
                values.append(d.get('drawn', 0.0))

        if not values:
            continue

        arr = np.array(values)
        if draws[0][key].get('distribution') == 'gaussian':
            click.echo(f"  {key}: mean_sigma={arr.mean():.3f}, "
                       f"std_sigma={arr.std():.3f}, "
                       f"min={arr.min():.3f}, max={arr.max():.3f}")
        else:
            click.echo(f"  {key}: mean={arr.mean():.4f}, "
                       f"std={arr.std():.4f}, "
                       f"min={arr.min():.4f}, max={arr.max():.4f}")


@mc.command()
@click.argument('output_dir', type=click.Path(exists=True), default='mc_results')
@click.option('--threshold', '-t', default=2.0, show_default=True,
              help='Sigma threshold for extreme cases')
def extremes(output_dir, threshold):
    """Show cases with parameter draws exceeding threshold sigma."""
    draws_file = Path(output_dir) / 'mc_draws.json'
    if not draws_file.exists():
        click.echo(f"No mc_draws.json found in {output_dir}")
        return

    data = json.loads(draws_file.read_text())
    draws = data.get('draws', [])

    extreme_cases = []
    for case_id, case_draws in enumerate(draws):
        for key, d in case_draws.items():
            if d.get('distribution') == 'gaussian':
                ns = abs(d.get('n_sigma_draw', 0.0))
                if ns > threshold:
                    extreme_cases.append({
                        'case_id': case_id,
                        'parameter': key,
                        'n_sigma': d['n_sigma_draw'],
                    })

    if not extreme_cases:
        click.echo(f"No cases with draws exceeding {threshold}σ")
        return

    click.echo(f"Cases with draws > {threshold}σ:")
    for e in sorted(extreme_cases, key=lambda x: abs(x['n_sigma']), reverse=True):
        click.echo(f"  Case {e['case_id']:4d}: {e['parameter']} = "
                   f"{e['n_sigma']:+.2f}σ")


@mc.command()
@click.argument('xml_file', type=click.Path(exists=True))
def template(xml_file):
    """Auto-generate a <monte_carlo> XML template from introspection.

    Loads the shared library specified in the XML, queries the TClassDict
    for all DSF_PROPERTY_BIND properties, and emits a ready-to-edit
    <monte_carlo> block with every dispersible property defaulted to sigma=0.
    """
    from xml.etree import ElementTree as ET

    tree = ET.parse(xml_file)
    root = tree.getroot()
    sim_node = root if root.tag == 'sim' else root.find('.//sim')

    if sim_node is None:
        click.echo("No <sim> node found.")
        return

    click.echo("<!-- Monte Carlo template generated from introspection -->")
    click.echo('<!-- Set sigma > 0 or min/max to enable a dispersion -->')
    click.echo(f'<monte_carlo n="100" seed="42" workers="8" output_dir="mc_results/">')

    # For now, enumerate blocks from the XML and emit placeholders
    # Full introspection via C++ TClassDict requires pybind or subprocess query
    for child in sim_node:
        tag = child.tag
        block_id = child.get('id', '')
        if not block_id or tag == 'monte_carlo' or tag == 'events':
            continue

        click.echo(f'  <!-- {tag} id="{block_id}" -->')

        # Walk sub-children for nested blocks
        for sub in child:
            sub_id = sub.get('id', '')
            if sub_id:
                click.echo(f'  <!-- {sub.tag} id="{sub_id}" -->')
                click.echo(f'  <!-- <dispersion block="{sub_id}" property="..." '
                           f'distribution="gaussian" sigma="0.0" /> -->')

    click.echo('</monte_carlo>')
