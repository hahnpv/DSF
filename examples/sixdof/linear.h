#pragma once

	/*
	Based off of Hainz and Costello; constants from Fortran
	Converted from thesis work as a standalone class to a DSF Block *
	*/

#include "util/math/vec3.h"
#include "util/tbl/tbl.h"
// #include "baseClasses/data.h"

#include <map>
#include <complex>
using std::complex;

class Linear {
public: 
	Linear(double ds, double updateint, double sf);

	std::map<dsf::util::Vec3, double> update(dsf::util::Vec3 xyz, dsf::util::Vec3 uvw, dsf::util::Vec3 pqr, dsf::util::Vec3 orientation, double Time);
protected:
	// Variable declarations
	int counter, j, k, kmax, numupdates;
		  
	complex<double>i;
	complex<double>two;
	complex<double>four;
	complex<double>s1;
	complex<double>s2;
	complex<double>s3;
	complex<double>s4;

	double cma, cnpa;
	double cx0, cy0, cz0, cna1, cypa;
	double clp, cldd, cmq;
	double cm0, cn0;

	double slcop, slcont, slmag, slmaga2, slmaga4;

	double DeltaSL, DeltaSLm, DeltaSLc;

	double epsaoa, slmagalpha;
      
	double density, mach, pi;

	double D, g, Ir, Ip, mass;
    double u, v, w;
	double tlast, xlast, ylast, zlast;

	double philast, thetalast, psilast;

	double Vlast, vtildelast, wtildelast;

	double plast, qtildelast, rtildelast;
      
	double A, B, C, F, H, L;

	double cons, vstar, wstar;

	double Vf, Wf, Qf, Rf;

	double Vmw, psi_mw;

	double av, bv, Cp0, Cpe1, Cpe2;
      
	double Const0[4], EF[4], ES[4];
	double Fz0[4], Sz0[4];

	double Fz1[4], Sz1[4], zeta[10000][4];

	double Den, C1, C2, C3[4], C4[4], C5[4], C6[4];
	double sk;
	double s[10000];
	double RHO, SOS;

	double WEIGHT, SLCG, IXX, IYY, AEROFLAG, GRAVITYFLAG;
	double SI, SF, DS, UPDATEINT;
	double SIGMA, PSIWIND, ATMFLAG;
      
	double dz1, dz2, dz3, dz4;
	double nz4[4], nz3[4], nz2[4], nz1[4], nz0[4];
	double omegaF, omegaS, zetaF, zetaS;
	double lamFR, lamFI, lamSR, lamSI;
	double tc1, tc2, tc3, tc4, tc5, tc6;
	double pc1, pc2, pc3, pc4, pc5, pc6;
	double yc1, yc2, yc3, yc4, yc5, yc6, yc7;
	double zc1, zc2, zc3, zc4, zc5, zc6;
	double CEF, CES, SEF, SES;
	double theta[10000], psi[10000];
	double x[10000], y[10000], z[10000];
	double V[10000], p[10000], phi[10000];
	double t[10000];

	double temp, press;

	// Tables
	dsf::util::Table *cx0Tab;
	dsf::util::Table *cna1Tab;
	dsf::util::Table *cypaTab;
	dsf::util::Table *clpTab;
	dsf::util::Table *cmqTab;
	dsf::util::Table *cmaTab;
	dsf::util::Table *cnpaTab;
	dsf::util::Table *SITable;
};