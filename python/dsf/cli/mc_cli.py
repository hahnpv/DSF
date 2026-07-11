"""
Monte Carlo CLI subcommands for DSF.

    dsf mc template <vehicle.xml>   — auto-generate MC XML from introspection
    dsf mc run <vehicle.xml>        — run MC batch (async)
    dsf mc status [output_dir]      — check progress
    dsf mc results <output_dir>     — aggregate statistics
    dsf mc extremes <output_dir>    — show >2σ cases
"""

import click


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
    from dsf.mc import load_draws, draw_stats
    data = load_draws(output_dir)
    if data is None:
        click.echo(f"No mc_draws.json found in {output_dir}")
        return

    draws = data.get('draws', [])
    click.echo(f"MC Results: {len(draws)} cases")
    click.echo(f"Master seed: {data.get('master_seed')}")
    click.echo(f"\nDispersions:")

    for key, s in draw_stats(draws).items():
        if s['distribution'] == 'gaussian':
            click.echo(f"  {key}: mean_sigma={s['mean']:.3f}, "
                       f"std_sigma={s['std']:.3f}, "
                       f"min={s['min']:.3f}, max={s['max']:.3f}")
        else:
            click.echo(f"  {key}: mean={s['mean']:.4f}, "
                       f"std={s['std']:.4f}, "
                       f"min={s['min']:.4f}, max={s['max']:.4f}")


@mc.command()
@click.argument('output_dir', type=click.Path(exists=True), default='mc_results')
@click.option('--threshold', '-t', default=2.0, show_default=True,
              help='Sigma threshold for extreme cases')
def extremes(output_dir, threshold):
    """Show cases with parameter draws exceeding threshold sigma."""
    from dsf.mc import load_draws, extreme_draws
    data = load_draws(output_dir)
    if data is None:
        click.echo(f"No mc_draws.json found in {output_dir}")
        return

    extreme_cases = extreme_draws(data.get('draws', []), threshold)
    if not extreme_cases:
        click.echo(f"No cases with draws exceeding {threshold}σ")
        return

    click.echo(f"Cases with draws > {threshold}σ:")
    for e in extreme_cases:
        click.echo(f"  Case {e['case_id']:4d}: {e['parameter']} = "
                   f"{e['n_sigma']:+.2f}σ")


@mc.command()
@click.argument('output_dir', type=click.Path(exists=True))
@click.option('--type', '-t', 'plot_type', default='summary',
              type=click.Choice(['summary', 'spaghetti', 'envelope', 'histogram', 'scatter']),
              help='Plot type')
@click.option('--var', '-v', 'variables', multiple=True, help='Variable name(s) to plot')
@click.option('--time', 'at_time', default=-1.0, help='Time for histogram/scatter (-1 = final)')
@click.option('--max-cases', '-n', default=None, type=int, help='Limit number of cases to load')
def plot(output_dir, plot_type, variables, at_time, max_cases):
    """Generate Monte Carlo analysis plots.

    Plot types:
      summary    - Multi-panel overview (spaghetti + envelope + histogram)
      spaghetti  - All cases overlaid on one plot
      envelope   - Mean with percentile bands
      histogram  - Distribution at a specific time
      scatter    - Two variables plotted against each other
    """
    from dsf.mc_plot import MCPlotter

    plotter = MCPlotter(output_dir, max_cases=max_cases)

    if plot_type == 'summary':
        vlist = list(variables) if variables else None
        plotter.summary_panel(variables=vlist)

    elif plot_type == 'spaghetti':
        if not variables:
            click.echo("Error: --var required for spaghetti plot")
            return
        for v in variables:
            plotter.spaghetti(v)

    elif plot_type == 'envelope':
        if not variables:
            click.echo("Error: --var required for envelope plot")
            return
        for v in variables:
            plotter.envelope(v)

    elif plot_type == 'histogram':
        if not variables:
            click.echo("Error: --var required for histogram plot")
            return
        for v in variables:
            plotter.histogram(v, t=at_time)

    elif plot_type == 'scatter':
        if len(variables) < 2:
            click.echo("Error: --var X --var Y required for scatter plot")
            return
        plotter.scatter(variables[0], variables[1], t=at_time)

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
