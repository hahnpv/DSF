//
//	Based off of Hainz and Costello, constants from Fortran
//

// 	NOT a CMD class, rather a private object of Guidance.
//	(for now) will need table/filer objects
 
//
//	Note: time in changed from State::t to Time
//

#include "linear.h"

 // Updating for DSF

#include <cmath>
#include <complex>
#include <iostream>

#include <iostream>
#include <fstream>
using namespace std;
using namespace dsf::util;

//using namespace tframes;
using std::complex;

Linear::Linear(double ds, double updateint, double sf) 
{
	i 	 = complex<double>(0,1);	
	two  = complex<double>(2,0);
	four = complex<double>(4,0);

	// Load data from tables (need to re-work)
	char *fname 	= "config/6dofTables.dat";
	cx0Tab		= new Table(fname,"[Cx0]");
	cna1Tab 	= new Table(fname,"[CnA]");
	cypaTab 	= new Table(fname,"[CypA]");
	clpTab		= new Table(fname,"[Clp]");
	cmqTab		= new Table(fname,"[Cmq]");
	cmaTab		= new Table(fname,"[Cma]");
	cnpaTab		= new Table(fname,"[CnpA]");
	SITable 	= new Table(fname,"[SI]");

	// Get constants from data
   	IXX 	= 0.000311;			// Ixx MOI, kg*m2 
   	IYY 	= 0.00488;			// Iyy MOI, kg*m2
  	mass 	= 1.495;			// mass, kg  	
   	D 		= 0.039;			// Diameter, m   
	g 		= 9.801;			// gravity
   	pi		= 3.14159265358979;	// PI
   	SLCG 	= 0.18694;      	// stationline of the CG, m
   	SIGMA   = 0.0;     			// Wind Speed 
   	PSIWIND = 0.0;    			// Wind Azimuth Angle, rad  

	DS 		  = ds;
	UPDATEINT = updateint;
	SF 		  = sf;
}


map <Vec3, double> Linear::update(Vec3 xyz, Vec3 uvw, Vec3 pqr, Vec3 orientation, double Time) 
{
      	SI = SITable->interp(Time);	// Initial Arclength Value for Linear Calculations, SI

///////////////////////////////////////////////////////////////////////////////
// 	Create a unique file object to dump data to for analysis
///////////////////////////////////////////////////////////////////////////////

	string  name = "results.dat";
	ostringstream myStream;
	myStream << Time << flush;
	name.insert(7,myStream.str());
	cout << "filename: " << name << endl;
	ofstream *fout = new ofstream(name.c_str());
		*fout << "k\tt\tV\tx\ty\tz\tNMD" << endl;

///////////////////////////////////////////////////////////////////////////////
//	Create the map
///////////////////////////////////////////////////////////////////////////////

	map <Vec3, double> LinearizedModel;

///////////////////////////////////////////////////////////////////////////////
//	Initial conditions and Setup (vectorize me plz)
///////////////////////////////////////////////////////////////////////////////

	xlast = xyz.x;
	ylast = xyz.y;
	zlast = xyz.z; 

	u = uvw.x;
	v = uvw.y;
	w = uvw.z;

	philast   = orientation.x;
	thetalast = orientation.y;
	psilast   = orientation.z;

	plast	   = pqr.x;					// initial 
   	qtildelast = pqr.y;					// initial pitch rate	(rad/s) q
   	rtildelast = pqr.z;					// initial yaw rate	(rad/s) r

	// qtildelast, rtildelast were initially set =0 in the original code.
	// I'm not 100% sure that they are pitch and yaw rate, but they seem
	// to improve accuracy slightly (several milimeters)
	// check back here if things go weird

	tlast = Time;	
	Vlast = uvw.mag();

   	vtildelast = cos(philast)*v - sin(philast)*w; 	// Side acceleration (?)
   	wtildelast = sin(philast)*v + cos(philast)*w; 	// Side acceleration (?)

///////////////////////////////////////////////////////////////////////////////
//	Calculation loop starts here
///////////////////////////////////////////////////////////////////////////////

   	numupdates = (int)((SF - SI)/UPDATEINT);		// number of updates necessary
	for (counter = 1; counter < numupdates; counter++) 
	{      	
		// s contains all arclength calculation points
		// first point is SI, subsequent points are SI+n*DS
		s[1] = SI;
        
		k = 1;
		while ( k<=(int)(UPDATEINT/DS) ) 
		{
			s[k+1] = s[k] + DS;
			k++;
		}

		// Atmosphere and speed of sound calculations -> deprecate and get these from the Atmosphere <-
		temp  = 15.04 - (0.00649 * abs(zlast));						// temperature, celsius
		press = 101.29 * pow( ((temp + 273.1)/ 288.08) , 5.256);	// pressure,	kilopascal
		RHO   = press / (0.2869*(temp+273.1));						// density, 	kg/m3
		mach  = Vlast / sqrt(1.4*287*(temp+273.1));					// Mach number

		// interpolate tables
		cx0	 = cx0Tab->interp(mach);
		cna1 = cna1Tab->interp(mach);
		cy0	 = 0.;
		cz0	 = 0.;
		cypa = cypaTab->interp(mach);
		clp	 = clpTab->interp(mach);
		cldd = 0.;
		cmq	 = cmqTab->interp(mach);
		cma	 = cmaTab->interp(mach);
		cnpa = cnpaTab->interp(mach);

		// calculate sl* manually
		slcop	= (cma/cna1)*D;			// center of pressure location
		slcont	= slcop;				// controls location, currently at CP
		slmag	= (cnpa/cypa)*D;		// magnus point location
		slmaga2 = 0;					// third order term
		slmaga4 = 0;					// fifth order term

		// distance along stationline of projectile at which magnus force acts (slmagalpha)
        epsaoa = sqrt(pow(vtildelast,2) + pow(wtildelast,2))/Vlast;
       	slmagalpha = slmag + slmaga2*pow(epsaoa,2) + slmaga4*pow(epsaoa,4);

		// Stationline Locations for cp, magnus and control locations
       	DeltaSL = slcop - SLCG; 
   	 	DeltaSLm = slmagalpha - SLCG; 
		DeltaSLc = slcont - SLCG;

        Ir = IXX;						// clean up notation - just use IXX, IYY massprops
       	Ip = IYY;						// use massprops class

   		// Moments generated by Aeros
        cm0 = cy0*DeltaSLc;
       	cn0 = cz0*DeltaSLc;
	
		// Mean Winds
       	Vmw = SIGMA;					//  Velocity
       	psi_mw = PSIWIND;				//  Angle of attack

///////////////////////////////////////////////////////////////////////////////
//	Epicyclic solution by way of a Laplace transform
///////////////////////////////////////////////////////////////////////////////

		// Determine constants for Epicyclic Equations
		cons = pi*RHO*pow(D,3);
		vstar = -Vmw*(cos(psilast)*sin(psi_mw) - sin(psilast)*cos(psi_mw));
		wstar = -Vmw*(sin(thetalast)*cos(psilast)*cos(psi_mw) + sin(thetalast)*sin(psilast)*sin(psi_mw));

		A = (cons*cna1)/(8.0*mass);
		B = (cons*pow(D,2)*cypa*DeltaSLm*plast)/(16.0*Ip*Vlast);
    	C = (cons*D*cna1*DeltaSL)/(8.0*Ip);
		F = (Ir*D*plast)/(Ip*Vlast); 
		H = (cons*pow(D,2)*cmq)/(16.0*Ip);
		Vf = cons*(cna1*vstar - Vlast*cy0)/(8.0*mass);
		Wf = (g*D*cos(thetalast))/Vlast + cons*(cna1*wstar - Vlast*cz0)/(8.0*mass);
		Qf = cons*((-D*cypa*DeltaSLm*plast*vstar)/(2*Vlast) - cna1*DeltaSL*wstar + Vlast*DeltaSLc*cz0)/(8.0*Ip);
		Rf = cons*(cna1*DeltaSL*vstar - (D*cypa*DeltaSLm*plast*wstar)/(2*Vlast) - Vlast*DeltaSLc*cy0)/(8.0*Ip);


		// Solve Epicyclic Equations using the Laplace Transform
        dz4 = (2*A - 2*H);
       	dz3 = (pow(A,2) + pow(F,2) + pow(H,2) - 2*C - 4*A*H );
       	dz2 = (-2*A*C + 2*B*F + 2*A*pow(F,2) - 2*pow(A,2)*H + 2*C*H + 2*A*pow(H,2));
       	dz1 = (pow(B,2) + pow(C,2) + 2*A*B*F + pow(A,2)*pow(F,2) + 2*A*C*H + pow(A,2)*pow(H,2));

        nz4[1] = vtildelast; 
        nz3[1] = (A - 2*H)*vtildelast - D*rtildelast + Vf;
       	nz2[1] = (pow(F,2) - C - 2*A*H + pow(H,2))*vtildelast - B*wtildelast 
			- D*F*qtildelast + (D*H - A*D)*rtildelast + (A - 2*H)*Vf - D*Rf;
       	nz1[1] = (B*F + A*pow(F,2) + C*H + A*pow(H,2))*vtildelast 
	        + (B*H - C*F)*wtildelast - (B*D + A*D*F)*qtildelast 
			+ (C*D + A*D*H)*rtildelast + (pow(F,2) - 2*A*H + pow(H,2) - C)*Vf 
			- B*Wf - D*F*Qf + (D*H - A*D)*Rf ;
       	nz0[1] = (B*F + A*pow(F,2) + C*H + A*pow(H,2))*Vf + (B*H - C*F)*Wf 
			- (B*D + A*D*F)*Qf + (C*D + A*D*H)*Rf;
     
   		nz4[2] = wtildelast; 
       	nz3[2] = (A - 2*H)*wtildelast + D*qtildelast + Wf; 
       	nz2[2] = B*vtildelast + (pow(H,2) + pow(F,2) - C - 2*A*H)*wtildelast 
			+ (A*D - D*H)*qtildelast - D*F*rtildelast + (A - 2*H)*Wf + D*Qf;
       	nz1[2] = (C*F - B*H)*vtildelast + (B*F + A*pow(F,2) + C*H 
			+ A*pow(H,2))*wtildelast - (C*D + A*D*H)*qtildelast 
			- (B*D + A*D*F)*rtildelast + B*Vf + (pow(F,2) - C - 2*A*H 
			+ pow(H,2))*Wf + (A*D - D*H)*Qf - D*F*Rf;
       	nz0[2] = (C*F - B*H)*Vf + (B*F + A*pow(F,2) + C*H + A*pow(H,2))*Wf 
			- (C*D + A*D*H)*Qf - (B*D + A*D*F)*Rf;  
     
       	nz4[3] = qtildelast;
       	nz3[3] = B*vtildelast/D + C*wtildelast/D + (2*A - H)*qtildelast 
			- F*rtildelast + Qf;
       	nz2[3] = (A*B + C*F - B*H)*vtildelast/D + (A*C - B*F- C*H)*wtildelast/D 
			+ (pow(A,2) - C - 2*A*H)*qtildelast - (B + 2*A*F)*rtildelast 
			+ B*Vf/D + C*Wf/D + (2*A - H)*Qf - F*Rf;
        	nz1[3] = (A*C*F - A*B*H)*vtildelast/D - (pow(B,2) + pow(C,2) + A*B*F 
			+ A*C*H)*wtildelast/D -(A*C + pow(A,2)*H)*qtildelast - (A*B 
			+ pow(A,2)*F)*rtildelast + (A*B + C*F - B*H)*Vf/D 
			+ (A*C - B*F - C*H)*Wf/D + (pow(A,2) - C - 2*A*H)*Qf - (B + 2*A*F)*Rf;
        	nz0[3] = (A*C*F - A*B*H)*Vf/D - (pow(B,2) + pow(C,2) + A*B*F + A*C*H)*Wf/D 
			-(A*C + pow(A,2)*H)*Qf - (A*B + pow(A,2)*F)*Rf;

       	nz4[4] = rtildelast; 
       	nz3[4] = -C*vtildelast/D + B*wtildelast/D + F*qtildelast 
			+ (2*A - H)*rtildelast + Rf;
       	nz2[4] = (B*F - A*C + C*H)*vtildelast/D + (A*B + C*F - B*H)*wtildelast/D 
			+ (B + 2*A*F)*qtildelast + (pow(A,2) - C - 2*A*H)*rtildelast 
			- C*Vf/D + B*Wf/D + F*Qf + (2*A - H)*Rf;
       	nz1[4] = (pow(B,2) + pow(C,2) + A*B*F + A*C*H)*vtildelast/D 
			+ (A*C*F - A*B*H)*wtildelast/D + (A*B + pow(A,2)*F)*qtildelast 
			- (A*C + pow(A,2)*H)*rtildelast + (B*F - A*C + C*H)*Vf/D  
			+ (A*B + C*F - B*H)*Wf/D + (B + 2*A*F)*Qf + (pow(A,2) - C - 2*A*H)*Rf;
       	nz0[4] = (pow(B,2) + pow(C,2) + A*B*F + A*C*H)*Vf/D + (A*C*F - A*B*H)*Wf/D 
			+ (A*B + pow(A,2)*F)*Qf - (A*C + pow(A,2)*H)*Rf;
		// nz0[4] = omegaS, somehow, somewhere ... I don't know how or why. Need to debug it.

		// Solve for the fast and slow natural frequencies and damping rates
		s1 = (i/two)*F + (-A + H)/2 + sqrt(pow(A,2) + (four*i)*B + 4*C + (two*i)*A*F 
		    - pow(F,2) + 2*A*H + (two*i)*F*H + pow(H,2))/two;
       	s2 = (-i/two)*F + (-A + H)/2 + sqrt(pow(A,2) - (four*i)*B + 4*C - (two*i)*A*F 
		    - pow(F,2) + 2*A*H - (two*i)*F*H + pow(H,2))/two; 
       	s3 = (i/two)*F + (-A + H)/2 - sqrt(pow(A,2) + (four*i)*B + 4*C + (two*i)*A*F 
		    - pow(F,2) + 2*A*H + (two*i)*F*H + pow(H,2))/two; 
       	s4 = (-i/two)*F + (-A + H)/2 - sqrt(pow(A,2) - (four*i)*B + 4*C - (two*i)*A*F 
		    - pow(F,2) + 2*A*H - (two*i)*F*H + pow(H,2))/two;

		omegaF = -abs(s1); 
   		zetaF  = real(s1)/abs(s1);
   		omegaS = -abs(s3);
   		zetaS  = real(s3)/abs(s3);

   		lamFR = zetaF*omegaF;
   		lamFI = sqrt(pow(omegaF,2)*(1-pow(zetaF,2)));
   		lamSR = zetaS*omegaS; 
   		lamSI = sqrt(pow(omegaS,2)*(1-pow(zetaS,2)));


/*
!       ------------------------------------------------------------------
!       Each solution can also be written in partial fractions form in terms
!       of the system poles as:
! 
!                 Cz0             Fz1*s + Fz0                         Sz1*s + Sz0
!       zeta(s) = --- + --------------------------------- + ---------------------------------
!                  s    s^2 + 2*zetaF*omegaF*s + omegaF^2   s^2 + 2*zetaS*omegaS*s + omegaS^2
!      
!       By equating this form of the solution to that shown above, the constants
!       Cz0, Fz0, Fz1, Sz0, Sz1 can be determined.
!         NOTE: The term Cz0 is renamed Const0 in the code to avoid confusion with the
!               aerodynamic coefficient of the same name.
*/

		L = pow(omegaF,4) + pow(omegaS,4) - 4*pow(omegaF,3)*omegaS*zetaF*zetaS 
		   - 4*omegaF*pow(omegaS,3)*zetaF*zetaS 
		   + 2*pow(omegaF,2)*pow(omegaS,2)*(-1 + 2*pow(zetaF,2) + 2*pow(zetaS,2));


		// Loop to solve each of the four epicyclic equations.
		for (int j=1; j<=4; j++) 
		{
        	Const0[j] = nz0[j]/(pow(omegaF,2)*pow(omegaS,2)); 
			
			if (j==4) 
			{
				// temporary aproximate hack till we figure out why Const0[4] is getting assigned to omegaS
		        Const0[4] = ((pow(B,2) + pow(C,2) + A*B*F + A*C*H)*Vf/D 
					   + (A*C*F - A*B*H)*Wf/D + (A*B + pow(A,2)*F)*Qf 
					   - (A*C + pow(A,2)*H)*Rf) / (pow(omegaF,2)*pow(omegaS,2));
			}


       		Fz0[j] = (nz1[j]*pow(omegaS,2) - 2*pow(omegaF,3)*zetaF*(nz2[j] 
				- pow(omegaS,2)*(nz4[j] + Const0[j]*(2 - 4*pow(zetaF,2)))) 
				- 2*omegaF*omegaS*zetaF*(Const0[j]*pow(omegaS,3) 
				+ 2*nz1[j]*zetaS) + pow(omegaF,4)*(nz3[j] 
				- 2*nz4[j]*omegaS*zetaS) 
				+ pow(omegaF,2)*(nz1[j]*(-1 + 4*pow(zetaF,2)) 
				+ omegaS*(-(nz3[j]*omegaS) + 2*(nz2[j] 
				+ Const0[j]*pow(omegaS,2)*(-1 + 4*pow(zetaF,2)))*zetaS)))/L;

       		Sz0[j] = (nz1[j]*(pow(omegaF,2) - 4*omegaF*omegaS*zetaF*zetaS 
				+ pow(omegaS,2)*(-1 + 4*pow(zetaS,2))) 
				+ omegaS*(nz3[j]*(-(pow(omegaF,2)*omegaS) + pow(omegaS,3)) 
				- 2*(nz2[j]*omegaS*(-(omegaF*zetaF) + omegaS*zetaS) 
				+ omegaF*(nz4[j]*pow(omegaS,2)*(omegaS*zetaF - omegaF*zetaS) 
				+ Const0[j]*omegaF*(pow(omegaF,2)*zetaS 
				+ omegaF*omegaS*zetaF*(1 - 4*pow(zetaS,2)) 
				+ 2*pow(omegaS,2)*zetaS*(-1 + 2*pow(zetaS,2)))))))/L;

       		Fz1[j] = (nz4[j]*pow(omegaF,4) + nz2[j]*pow(omegaS,2) 
				- Const0[j]*pow(omegaS,4) - 2*nz1[j]*omegaS*zetaS 
				- 4*nz4[j]*pow(omegaF,3)*omegaS*zetaF*zetaS 
				- pow(omegaF,2)*(nz2[j] + omegaS*((Const0[j] 
				- nz4[j])*omegaS*(-1 + 4*pow(zetaF,2)) - 2*nz3[j]*zetaS)) 
				+ 2*omegaF*zetaF*(nz1[j] + pow(omegaS,2)*(-nz3[j] 
				+ 2*Const0[j]*omegaS*zetaS)))/L;
     	
       		Sz1[j] = (-(Const0[j]*pow(omegaF,4)) - nz2[j]*pow(omegaS,2) 
				+ nz4[j]*pow(omegaS,4) + 2*nz1[j]*omegaS*zetaS 
				+ 4*Const0[j]*pow(omegaF,3)*omegaS*zetaF*zetaS 
				- 2*omegaF*zetaF*(nz1[j] + pow(omegaS,2)*(-nz3[j] 
				+ 2*nz4[j]*omegaS*zetaS)) + pow(omegaF,2)*(nz2[j] 
				+ omegaS*(-2*nz3[j]*zetaS + omegaS*(Const0[j] - nz4[j] 
				- 4*(Const0[j] - nz4[j])*pow(zetaS,2)))))/L;

			// Inverse Laplace transform to convert back to arclength domain
       		EF[j] = ((Fz0[j] - Fz1[j]*lamFR)/lamFI);
       		ES[j] = ((Sz0[j] - Sz1[j]*lamSR)/lamSI);
          
			for (int k=1; k<=(int)(UPDATEINT/DS); k++) 
			{
				sk = s[k] - SI;
				zeta[k][j] = Const0[j] 
				  + exp(-lamFR*sk)*(Fz1[j]*cos(lamFI*sk) + EF[j]*sin(lamFI*sk)) 
				  + exp(-lamSR*sk)*(Sz1[j]*cos(lamSI*sk) + ES[j]*sin(lamSI*sk));
			}
		} 

///////////////////////////////////////////////////////////////////////////////
//	Solve states and their constituent constant terms
///////////////////////////////////////////////////////////////////////////////

		C1 = pow(lamFI,2) + pow(lamFR,2);
        C2 = pow(lamSI,2) + pow(lamSR,2);

		for (int j=1; j<=4; j++)			 // was: j<4. Messes up y. 
		{
			C3[j] = EF[j]*lamFI + Fz1[j]*lamFR;
			C4[j] = EF[j]*lamFR - Fz1[j]*lamFI;
        	C5[j] = ES[j]*lamSI + Sz1[j]*lamSR;
	    	C6[j] = ES[j]*lamSR - Sz1[j]*lamSI;
		}

		Den = C1*C2*Vlast;

       	tc1 = thetalast + D*(C2*C3[3] + C1*C5[3])/Den;
       	tc2 = (Const0[3]*D)/Vlast;
       	tc3 = (C2*C3[3]*D)/Den;
       	tc4 = (C1*C5[3]*D)/Den;
       	tc5 = (C2*C4[3]*D)/Den;
       	tc6 = (C1*C6[3]*D)/Den;

       	pc1 = psilast + D*(C2*C3[4] + C1*C5[4])/(cos(thetalast)*Den);
       	pc2 = (Const0[4]*D)/(cos(thetalast)*Vlast);
       	pc3 = (C2*C3[4]*D)/(cos(thetalast)*Den);
       	pc4 = (C1*C5[4]*D)/(cos(thetalast)*Den);
       	pc5 = (C2*C4[4]*D)/(cos(thetalast)*Den);
       	pc6 = (C1*C6[4]*D)/(cos(thetalast)*Den);

        yc1 = ylast + (D*(C2*C3[1] + C1*C5[1] - (C2*lamFR*pc3 + C1*lamSR*pc4 + C2*lamFI*pc5 + C1*lamSI*pc6)*Vlast*cos(thetalast)))/Den;
        yc2 = D*(Const0[1] + pc1*Vlast*cos(thetalast))/Vlast;
        yc3 = 0.5*D*pc2*cos(thetalast);
        yc4 = C2*D*((lamFR*pc3 + lamFI*pc5)*Vlast*cos(thetalast) - C3[1])/Den;
        yc5 = C1*D*((lamSR*pc4 + lamSI*pc6)*Vlast*cos(thetalast) - C5[1])/Den;
        yc6 = C2*D*((lamFR*pc5 - lamFI*pc3)*Vlast*cos(thetalast) - C4[1])/Den;
        yc7 = C1*D*((lamSR*pc6 - lamSI*pc4)*Vlast*cos(thetalast) - C6[1])/Den;

        zc1 = zlast + ((C2*C3[2] + C1*C5[2])*D*cos(thetalast))/Den;
        zc2 = Const0[2]*D*cos(thetalast)/Vlast;
        zc3 = C2*C3[2]*D*cos(thetalast)/Den;
        zc4 = C1*C5[2]*D*cos(thetalast)/Den;
        zc5 = C2*C4[2]*D*cos(thetalast)/Den;
        zc6 = C1*C6[2]*D*cos(thetalast)/Den;

		bv = D*g*sin(thetalast);
		av = (cons*cx0)/(8*mass);
		Cp0 = (2*cldd*Vlast)/(D*clp);
		Cpe1 = plast + (2*cldd*Vlast)/(D*clp);	
		Cpe2 = (cons*pow(D,2)*clp)/(16*Ir);

		for (k=1;k<=(UPDATEINT/DS); k++) 
		{
			sk = s[k] - SI;

			CEF = cos(lamFI*sk)*exp(-lamFR*sk);
	        CES = cos(lamSI*sk)*exp(-lamSR*sk);
			SEF = sin(lamFI*sk)*exp(-lamFR*sk);
			SES = sin(lamSI*sk)*exp(-lamSR*sk);

			theta[k] = tc1 + tc2*sk - tc3*CEF - tc4*CES - tc5*SEF - tc6*SES;
			psi[k] = pc1 + pc2*sk - pc3*CEF - pc4*CES - pc5*SEF - pc6*SES;

			x[k] = xlast + 0.5*D*sk*(cos(theta[k]) + cos(thetalast));
       	 	y[k] = yc1 + yc2*sk + yc3*pow(sk,2) + yc4*CEF + yc5*CES + yc6*SEF + yc7*SES;
			z[k] = zc1 + zc2*sk - 0.5*D*sk*(sin(theta[k]) + sin(thetalast)) - zc3*CEF - zc4*CES - zc5*SEF - zc6*SES;

			V[k] = sqrt((pow(Vlast,2) + bv/av)*exp(-2*av*sk) - bv/av);
        	p[k] = Cpe1*exp(Cpe2*sk) - Cp0;

			phi[k] = (Cpe1*D*(exp(Cpe2*sk) - 1) - Cp0*Cpe2*D*sk + Cpe2*philast*Vlast)/(Cpe2*Vlast);
			t[k] = D*sk/(0.5*V[k] + 0.5*Vlast) + tlast;

			//
			// Print values to the stream
			//

			*fout << k << "\t" << t[k] << "\t" << V[k] << "\t" << x[k] << "\t" << y[k] << "\t" << z[k] 
				<< "\t" << sqrt(pow( 1000 - x[k] , 2) + pow( y[k] , 2) + pow( 1000 + z[k] , 2) ) << endl;
				
			LinearizedModel.insert(pair<Vec3, double>(Vec3(x[k],y[k],z[k]),t[k]));	// should work, if stuff looks bad look here first

		//	cout << "time:" << t[k] << " xyz: " << x[k] << " " << y[k] << " " << z[k] << endl;
		}

		// End states become initial states for next iteration
       	kmax 		= (int)(UPDATEINT/DS);
        tlast 		= t[kmax];
       	xlast 		= x[kmax];
       	ylast 		= y[kmax];
       	zlast 		= z[kmax];
       	philast 	= phi[kmax];
       	thetalast 	= theta[kmax];
       	psilast 	= psi[kmax];
       	Vlast 		= V[kmax];
       	vtildelast 	= zeta[kmax][1];
       	wtildelast 	= zeta[kmax][2];
       	plast 		= p[kmax];
       	qtildelast 	= zeta[kmax][3];
       	rtildelast 	= zeta[kmax][4];
       	SI	 		= s[kmax];
	}

	fout->close();
	delete fout;
	return LinearizedModel; 
}