#include "integratorRK4.h"
#include "../util/TFunctor.h"
#include "sim.h"
#include "block.h"
#include "clock.h"

namespace dsf
{
	namespace sim 
	{
		/// Propagate the simulation by integrating the state and derivative pairs.
		void Integrator::propagate(Block * simulation) 
		{
			dsf::util::TFunctor<Block>( simulation->getChildren(), &Block::update);

			clock->set(false);

			for (unsigned int pass=0; pass<=3; pass++) 
			{
				rk4( pass);

				if (pass == 0 || pass == 2)
					clock->increment();

				dsf::util::TFunctor<Block>( simulation->getChildren(), &Block::update);
			}

			clock->set(true);
		}

		/// Perform the rk4 integration at the specified pass.
		void Integrator::rk4( int pass)
		{
			TClassIntegrandDict<Block> * d = TClassIntegrandDict<Block>::Instance();

			for(unsigned int i=0; i < d->x.size(); i++) 
			{
				d->xdd[pass][i] = *d->xd[i];

				if ( pass == 0 ) 
					d->x0[i] = *d->x[i];

				if ( pass == 0 || pass == 1)
					*d->x[i] =  d->x0[i] + clock->dt() / 2. * d->xdd[pass][i];

				if (pass == 2)
					*d->x[i] =  d->x0[i] + clock->dt() * d->xdd[pass][i];

				if (pass == 3)
					*d->x[i] =  d->x0[i] + clock->dt() / 6. * ( d->xdd[0][i] + 2 * d->xdd[1][i] + 2 * d->xdd[2][i] + d->xdd[3][i] );
			}
		}
	}
}