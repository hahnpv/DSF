"""
Monte Carlo plotting utilities for DSF.

Loads all case CSV outputs from an MC batch directory and generates
overlay/envelope/histogram plots for statistical analysis.

Usage:
    from dsf.mc_plot import MCPlotter
    plotter = MCPlotter("/path/to/mc_1000_full")
    plotter.spaghetti("CruiseMissile_Altitude")
    plotter.envelope("CruiseMissile_Altitude")
    plotter.histogram("CruiseMissile_Altitude", t=50.0)
    plotter.scatter("CruiseMissile_Latitude", "CruiseMissile_Longitude", t=-1)
"""

import json
import numpy as np
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection


def _load_case_csv(csv_path):
    """Load a DSF CSV file, skipping the units row."""
    with open(csv_path, 'r') as f:
        header_line = f.readline()
        _units_line = f.readline()  # skip units row
        headers = [h.strip() for h in header_line.split(',')]

    data = np.genfromtxt(csv_path, delimiter=',', skip_header=2)
    return headers, data


class MCPlotter:
    """Monte Carlo batch plotter.

    Loads all case CSVs from an MC output directory into a common time grid
    and provides plotting methods for statistical analysis.
    """

    def __init__(self, mc_dir, max_cases=None):
        """Load MC batch data.

        Args:
            mc_dir: Path to MC output directory (containing case_NNNN/ subdirs)
            max_cases: Optional limit on number of cases to load
        """
        self.mc_dir = Path(mc_dir)
        self.cases = []
        self.headers = None
        self.draws = None

        # Load draw metadata
        draws_file = self.mc_dir / 'mc_draws.json'
        if draws_file.exists():
            self.draws = json.loads(draws_file.read_text())

        # Find and load case CSVs
        case_dirs = sorted(self.mc_dir.glob('case_????'))
        if max_cases:
            case_dirs = case_dirs[:max_cases]

        print(f"Loading {len(case_dirs)} cases from {mc_dir}...")
        for case_dir in case_dirs:
            # Find the CSV — could be case.csv, output1.csv, etc.
            csvs = sorted(case_dir.glob('case.csv')) + sorted(case_dir.glob('output*.csv'))
            csvs = [c for c in csvs if c.is_file() and not c.is_symlink()]
            if not csvs:
                continue

            try:
                headers, data = _load_case_csv(csvs[0])
                if data.ndim == 2 and data.shape[0] > 1:
                    self.cases.append(data)
                    if self.headers is None:
                        self.headers = headers
            except Exception:
                continue

        if not self.cases:
            raise ValueError(f"No valid case data found in {mc_dir}")

        print(f"Loaded {len(self.cases)} cases, {len(self.headers)} columns, "
              f"~{np.mean([c.shape[0] for c in self.cases]):.0f} rows/case")

        # Build common time grid (use shortest case)
        self.n_cases = len(self.cases)
        self._col_idx = {h: i for i, h in enumerate(self.headers)}

    def _find_col(self, name):
        """Find column index by substring match."""
        # Try exact match first
        if name in self._col_idx:
            return self._col_idx[name]
        # Substring match
        matches = [h for h in self.headers if name.lower() in h.lower()]
        if len(matches) == 1:
            return self._col_idx[matches[0]]
        elif len(matches) > 1:
            # Prefer shortest match
            matches.sort(key=len)
            return self._col_idx[matches[0]]
        raise KeyError(f"Column '{name}' not found. Available: {self.headers}")

    def _col_name(self, name):
        """Get the actual column name."""
        idx = self._find_col(name)
        return self.headers[idx]

    def _get_timeseries(self, var_name):
        """Get time + variable arrays for all cases.

        Returns list of (t, y) tuples.
        """
        col = self._find_col(var_name)
        time_col = self._find_col('Time')

        series = []
        for case_data in self.cases:
            t = case_data[:, time_col]
            y = case_data[:, col]
            series.append((t, y))
        return series

    def _get_at_time(self, var_name, t):
        """Get variable value at a specific time across all cases.

        Args:
            var_name: Variable name
            t: Time value. Use -1 for final value.

        Returns:
            1D array of values, one per case
        """
        col = self._find_col(var_name)
        time_col = self._find_col('Time')

        values = []
        for case_data in self.cases:
            if t == -1:
                values.append(case_data[-1, col])
            else:
                idx = np.argmin(np.abs(case_data[:, time_col] - t))
                values.append(case_data[idx, col])
        return np.array(values)

    def spaghetti(self, var_name, out_file=None, title=None, alpha=0.1,
                  color='steelblue', figsize=(14, 6)):
        """Overlay all cases on a single plot.

        Args:
            var_name: Variable name (substring match)
            out_file: Output file path (default: auto-generate)
            title: Plot title
            alpha: Line transparency (lower = better for many cases)
            color: Line color
            figsize: Figure size
        """
        series = self._get_timeseries(var_name)
        col_name = self._col_name(var_name)

        fig, ax = plt.subplots(figsize=figsize)

        for t, y in series:
            ax.plot(t, y, color=color, alpha=alpha, linewidth=0.5)

        ax.set_xlabel('Time (s)')
        ax.set_ylabel(col_name)
        ax.set_title(title or f'Monte Carlo Spaghetti: {col_name} ({self.n_cases} cases)')
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        out = out_file or str(self.mc_dir / f'spaghetti_{col_name.replace(" ", "_")}.png')
        fig.savefig(out, dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f"Saved: {out}")
        return out

    def envelope(self, var_name, out_file=None, title=None,
                 percentiles=(5, 95), figsize=(14, 6)):
        """Plot mean with percentile envelope.

        Args:
            var_name: Variable name (substring match)
            out_file: Output file path
            title: Plot title
            percentiles: Tuple of (lower, upper) percentiles for the envelope
            figsize: Figure size
        """
        series = self._get_timeseries(var_name)
        col_name = self._col_name(var_name)

        # Interpolate all cases onto common time grid
        t_min = max(s[0][0] for s in series)
        t_max = min(s[0][-1] for s in series)
        t_grid = np.linspace(t_min, t_max, 500)

        interp_data = np.zeros((self.n_cases, len(t_grid)))
        for i, (t, y) in enumerate(series):
            interp_data[i, :] = np.interp(t_grid, t, y)

        mean = np.mean(interp_data, axis=0)
        median = np.median(interp_data, axis=0)
        p_lo = np.percentile(interp_data, percentiles[0], axis=0)
        p_hi = np.percentile(interp_data, percentiles[1], axis=0)
        y_min = np.min(interp_data, axis=0)
        y_max = np.max(interp_data, axis=0)

        fig, ax = plt.subplots(figsize=figsize)

        ax.fill_between(t_grid, y_min, y_max, alpha=0.1, color='steelblue',
                        label='Min/Max')
        ax.fill_between(t_grid, p_lo, p_hi, alpha=0.3, color='steelblue',
                        label=f'{percentiles[0]}-{percentiles[1]}th percentile')
        ax.plot(t_grid, mean, color='navy', linewidth=1.5, label='Mean')
        ax.plot(t_grid, median, color='darkorange', linewidth=1, linestyle='--',
                label='Median')

        ax.set_xlabel('Time (s)')
        ax.set_ylabel(col_name)
        ax.set_title(title or f'Monte Carlo Envelope: {col_name} ({self.n_cases} cases)')
        ax.legend(loc='best')
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        out = out_file or str(self.mc_dir / f'envelope_{col_name.replace(" ", "_")}.png')
        fig.savefig(out, dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f"Saved: {out}")
        return out

    def histogram(self, var_name, t=-1, out_file=None, title=None,
                  bins=50, figsize=(10, 6)):
        """Plot histogram of variable values at a specific time.

        Args:
            var_name: Variable name (substring match)
            t: Time at which to sample (-1 = final value)
            out_file: Output file path
            title: Plot title
            bins: Number of histogram bins
            figsize: Figure size
        """
        values = self._get_at_time(var_name, t)
        col_name = self._col_name(var_name)

        fig, ax = plt.subplots(figsize=figsize)

        _, bins_edges, patches = ax.hist(values, bins=bins, edgecolor='white',
                                          color='steelblue', alpha=0.8)

        # Add statistics
        mu, sigma = np.mean(values), np.std(values)
        t_label = f"t={t:.1f}s" if t >= 0 else "t=final"
        ax.axvline(mu, color='navy', linewidth=2, linestyle='-',
                   label=f'Mean: {mu:.2f}')
        ax.axvline(mu - 2*sigma, color='red', linewidth=1, linestyle='--',
                   label=f'±2σ: [{mu-2*sigma:.2f}, {mu+2*sigma:.2f}]')
        ax.axvline(mu + 2*sigma, color='red', linewidth=1, linestyle='--')

        ax.set_xlabel(col_name)
        ax.set_ylabel('Count')
        ax.set_title(title or f'MC Histogram: {col_name} @ {t_label} '
                     f'({self.n_cases} cases, μ={mu:.2f}, σ={sigma:.2f})')
        ax.legend(loc='best')
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        out = out_file or str(self.mc_dir / f'hist_{col_name.replace(" ", "_")}_{t_label}.png')
        fig.savefig(out, dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f"Saved: {out}")
        return out

    def scatter(self, var_x, var_y, t=-1, out_file=None, title=None,
                color_var=None, figsize=(10, 8)):
        """Scatter plot of two variables at a specific time.

        Args:
            var_x: X-axis variable name
            var_y: Y-axis variable name
            t: Time at which to sample (-1 = final value)
            out_file: Output file path
            title: Plot title
            color_var: Optional variable to use for point color
            figsize: Figure size
        """
        x = self._get_at_time(var_x, t)
        y = self._get_at_time(var_y, t)
        x_name = self._col_name(var_x)
        y_name = self._col_name(var_y)
        t_label = f"t={t:.1f}s" if t >= 0 else "t=final"

        fig, ax = plt.subplots(figsize=figsize)

        if color_var:
            c = self._get_at_time(color_var, t)
            c_name = self._col_name(color_var)
            sc = ax.scatter(x, y, c=c, cmap='viridis', s=10, alpha=0.7)
            plt.colorbar(sc, label=c_name)
        else:
            ax.scatter(x, y, color='steelblue', s=10, alpha=0.5)

        # Add mean marker
        ax.scatter(np.mean(x), np.mean(y), color='red', s=100, marker='+',
                   linewidths=2, label='Mean', zorder=5)

        ax.set_xlabel(x_name)
        ax.set_ylabel(y_name)
        ax.set_title(title or f'MC Scatter: {x_name} vs {y_name} @ {t_label} '
                     f'({self.n_cases} cases)')
        ax.legend(loc='best')
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        out = out_file or str(self.mc_dir / f'scatter_{t_label}.png')
        fig.savefig(out, dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f"Saved: {out}")
        return out

    def summary_panel(self, variables=None, out_file=None, figsize=(16, 12)):
        """Generate a multi-panel summary with spaghetti + envelope + histogram.

        Args:
            variables: List of variable names. Default: auto-select interesting ones.
            out_file: Output file path
            figsize: Figure size
        """
        if variables is None:
            # Auto-select interesting variables
            priority = ['Altitude', 'Velocity', 'speed', 'AGL', 'range',
                        'prop_mass', 'thrust', 'throttle']
            variables = []
            for p in priority:
                matches = [h for h in self.headers if p.lower() in h.lower()]
                for m in matches:
                    if m not in variables and m.strip() != 'Time':
                        variables.append(m)
                        break
                if len(variables) >= 4:
                    break

        n_vars = len(variables)
        fig, axes = plt.subplots(n_vars, 3, figsize=(figsize[0], 4 * n_vars))
        if n_vars == 1:
            axes = axes[np.newaxis, :]

        for row, var_name in enumerate(variables):
            series = self._get_timeseries(var_name)
            col_name = self._col_name(var_name)

            # --- Spaghetti ---
            ax = axes[row, 0]
            for t, y in series:
                ax.plot(t, y, color='steelblue', alpha=0.05, linewidth=0.5)
            ax.set_title(f'{col_name}')
            ax.set_xlabel('Time (s)')
            ax.grid(True, alpha=0.3)

            # --- Envelope ---
            ax = axes[row, 1]
            t_min = max(s[0][0] for s in series)
            t_max = min(s[0][-1] for s in series)
            t_grid = np.linspace(t_min, t_max, 300)
            interp = np.zeros((self.n_cases, len(t_grid)))
            for i, (t, y) in enumerate(series):
                interp[i, :] = np.interp(t_grid, t, y)

            mean = np.mean(interp, axis=0)
            p5 = np.percentile(interp, 5, axis=0)
            p95 = np.percentile(interp, 95, axis=0)
            y_min = np.min(interp, axis=0)
            y_max = np.max(interp, axis=0)

            ax.fill_between(t_grid, y_min, y_max, alpha=0.1, color='steelblue')
            ax.fill_between(t_grid, p5, p95, alpha=0.3, color='steelblue')
            ax.plot(t_grid, mean, color='navy', linewidth=1.5)
            ax.set_title(f'{col_name} (envelope)')
            ax.set_xlabel('Time (s)')
            ax.grid(True, alpha=0.3)

            # --- Histogram at final time ---
            ax = axes[row, 2]
            final_vals = self._get_at_time(var_name, -1)
            mu, sigma = np.mean(final_vals), np.std(final_vals)
            ax.hist(final_vals, bins=40, color='steelblue', alpha=0.8,
                    edgecolor='white')
            ax.axvline(mu, color='navy', linewidth=2)
            if sigma > 0:
                ax.axvline(mu - 2*sigma, color='red', linewidth=1, linestyle='--')
                ax.axvline(mu + 2*sigma, color='red', linewidth=1, linestyle='--')
            ax.set_title(f'{col_name} @ final (μ={mu:.1f}, σ={sigma:.2f})')
            ax.set_xlabel(col_name)
            ax.grid(True, alpha=0.3)

        fig.suptitle(f'Monte Carlo Summary — {self.n_cases} Cases', fontsize=16, y=1.01)
        plt.tight_layout()
        out = out_file or str(self.mc_dir / 'mc_summary.png')
        fig.savefig(out, dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f"Saved: {out}")
        return out
