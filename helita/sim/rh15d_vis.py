"""
Set of programs and tools visualise the output from RH, 1.5D version
"""
import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
from ipywidgets import interact, fixed, Dropdown
from scipy.integrate.quadrature import cumtrapz
from scipy.interpolate import interp1d
from ..utils.utilsmath import planck, int2bt


class Populations:
    def __init__(self, rh_object):
        self.rhobj = rh_object
        self.atoms = [a for a in dir(self.rhobj) if a[:5] == 'atom_']
        self.display()

    def display(self):
        """
        Displays a graphical widget to explore the level populations.
        Works in jupyter only.
        """
        ATOMS = {a.split('_')[1].title(): a for a in self.atoms}
        QUANTS = ['Populations', 'LTE Populations', 'Departure coefficients']
        NLEVEL = getattr(self.rhobj, self.atoms[0]).nlevel
        NX, NY, NZ = self.rhobj.atmos.temperature.shape
        if NX == 1:
            xslider = fixed(0)
        else:
            xslider = (0, NX - 1)
        if NY == 1:
            yslider = fixed(0)
        else:
            yslider = (0, NY - 1)

        def _pop_plot(atom):
            """Starts population plot"""
            pop = getattr(self.rhobj, atom).populations
            height = self.rhobj.atmos.height_scale[0, 0] / 1e6  # in Mm
            fig, ax = plt.subplots()
            pop_plot, = ax.plot(height, pop[0, 0, 0])
            ax.set_xlabel("Height (Mm)")
            ax.set_ylabel("Populations")
            ax.set_title("Level 1")
            return ax, pop_plot

        ax, p_plot = _pop_plot(self.atoms[0])

        @interact(atom=ATOMS, quantity=QUANTS, y_log=False,
                  x=xslider, y=xslider)
        def _pop_update(atom, quantity, y_log=False, x=0, y=0):
            NLEVEL = getattr(self.rhobj, atom).nlevel

            # Atomic level singled out because NLEVEL depends on the atom
            @interact(level=(1, NLEVEL))
            def _pop_update_level(level=1):
                n = getattr(self.rhobj, atom).populations[level - 1, x, y]
                nstar = getattr(self.rhobj, atom).populations_LTE[level - 1, x, y]
                if quantity == 'Departure coefficients':
                    tmp = n / nstar
                    ax.set_ylabel(quantity + ' (n / n*)')
                elif quantity == 'Populations':
                    tmp = n
                    ax.set_ylabel(quantity + ' (m$^{-3}$)')
                elif quantity == 'LTE Populations':
                    tmp = nstar
                    ax.set_ylabel(quantity + ' (m$^{-3}$)')
                p_plot.set_ydata(tmp)
                ax.relim()
                ax.autoscale_view(True, True, True)
                ax.set_title("Level %i, x=%i, y=%i" % (level, x, y))
                if y_log:
                    ax.set_yscale("log")
                else:
                    ax.set_yscale("linear")


class SourceFunction:
    def __init__(self, rh_object):
        self.rhobj = rh_object
        self.display()

    def display(self):
        """
        Displays a graphical widget to explore the source function.
        Works in jupyter only.
        """
        NX, NY, NZ, NWAVE = self.rhobj.ray.source_function.shape
        if NX == 1:
            xslider = fixed(0)
        else:
            xslider = (0, NX - 1)
        if NY == 1:
            yslider = fixed(0)
        else:
            yslider = (0, NY - 1)
        TAU_LEVELS = [0.3, 1., 3.]
        ARROW = dict(facecolor='black', width=1., headwidth=5, headlength=6)
        SCALES = ['Height', 'Optical depth']

        def __get_tau_levels(x, y, wave):
            """
            Calculates height where tau=0.3, 1., 3 for a given
            wavelength index.
            Returns height in Mm and closest indices of height array.
            """
            h = self.rhobj.atmos.height_scale[x, y]
            tau = cumtrapz(self.rhobj.ray.chi[x, y, :, wave], x=-h)
            tau = interp1d(tau, h[1:])(TAU_LEVELS)
            idx = np.around(interp1d(h, np.arange(h.shape[0]))(tau)).astype('i')
            return (tau / 1e6, idx)  # in Mm

        def _sf_plot():
            """Starts source function plot"""
            sf = self.rhobj.ray.source_function[0, 0, :, 0]
            height = self.rhobj.atmos.height_scale[0, 0] / 1e6  # in Mm
            bplanck = planck(self.rhobj.ray.wavelength_selected[0],
                             self.rhobj.atmos.temperature[0, 0], units='Hz')
            fig, ax = plt.subplots()
            ax.plot(height, sf, 'b-', label=r'S$_\mathrm{total}$', lw=1)
            ax.set_yscale('log')
            ax.plot(height, self.rhobj.ray.Jlambda[0, 0, :, 0], 'y-',
                    label='J', lw=1)
            ax.plot(height, bplanck, 'r--', label=r'B$_\mathrm{Planck}$',
                    lw=1)
            ax.set_xlabel("Height (Mm)")
            ax.set_ylabel(r"W m$^{-2}$ Hz$^{-1}$ sr$^{-1}$")
            ax.set_title("%.3f nm" % self.rhobj.ray.wavelength_selected[0])
            lg = ax.legend(loc='upper center')
            lg.draw_frame(0)
            # tau annotations
            tau_v, h_idx = __get_tau_levels(0, 0, 0)
            for i, level in enumerate(TAU_LEVELS):
                xval = tau_v[i]
                yval = sf[h_idx[i]]
                ax.annotate(r'$\tau$=%s' % level,
                            xy=(xval, yval),
                            xytext=(xval, yval / (0.2 - 0.03 * i)),
                            arrowprops=ARROW, ha='center', va='top')
            return ax

        ax = _sf_plot()

        @interact(wavelength=(0, NWAVE, 1), y_log=True,
                  x=xslider, y=xslider)
        def _sf_update(wavelength=0, y_log=True, x=0, y=0):
            bplanck = planck(self.rhobj.ray.wavelength_selected[wavelength],
                             self.rhobj.atmos.temperature[x, y], units='Hz')
            quants = [self.rhobj.ray.source_function[x, y, :, wavelength],
                      self.rhobj.ray.Jlambda[x, y, :, wavelength], bplanck]
            for i, q in enumerate(quants):
                ax.lines[i].set_ydata(q)
            ax.relim()
            ax.autoscale_view(True, True, True)
            ax.set_title("%.3f nm" % self.rhobj.ray.wavelength_selected[wavelength])
            # tau annotations:
            tau_v, h_idx = __get_tau_levels(x, y, wavelength)
            for i in range(len(TAU_LEVELS)):
                xval = tau_v[i]
                yval = self.rhobj.ray.source_function[x, y, h_idx[i], wavelength]
                ax.texts[i].xy = (xval, yval)
                ax.texts[i].set_position((xval, yval / (0.2 - 0.03 * i)))
            if y_log:
                ax.set_yscale("log")
            else:
                ax.set_yscale("linear")