#pragma once

namespace dsf
{
	namespace sim 
	{
		class Sim;
		class Clock;
		class Block;
		// Make this a base integrator class; then have derivatives for RK4, A-B-M, euler, etc.
		// pick via xml just like vehicle configuraiton
		// need to register these sim classes with dictionary... don't have common base
		// but we can make a generic SimToolkitBase or something and keep a separate dict which is probably wise...
		class Integrator 
		{
		public:
			Integrator() {};
			void propagate(Block * simulation);				/// Propagate differential equations
			Clock *clock;
		private:
			void rk4( int pass);
		};
	}
}