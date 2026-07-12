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
		void IntegratorRK4::propagate(Block * simulation) 
		{
			dsf::util::TFunctor<Block>( simulation->getChildren(), &Block::update);

			clock->set(false);

			// Stage times ride on Clock::set_stage_offset (uniform with RK45)
			// instead of mid-step ticks; the two macro ticks are committed
			// together once the step's states are final. Stage times are
			// unchanged: k2/k3 at t+dt/2, k4 and the final update at t+dt.
			for (unsigned int pass=0; pass<=3; pass++)
			{
				rk4( pass);

				if (pass == 0)
					clock->set_stage_offset(clock->dt() / 2.);
				if (pass == 2)
					clock->set_stage_offset(clock->dt());

				// Post-integration constraint hook: pass 3 committed the
				// step's final states, so commit the macro ticks (offset back
				// to zero — end-of-step time is pure tick time) and let blocks
				// project states onto constraints and update discrete modes
				// ONCE per step (see Block::constrain). The update() below
				// then re-evaluates derived outputs and derivatives at the
				// constrained state, so events and reports observe
				// post-constraint values.
				if (pass == 3)
				{
					clock->set_stage_offset(0.0);
					clock->increment();
					clock->increment();
					dsf::util::TFunctor<Block>( simulation->getChildren(), &Block::constrain);
				}

				dsf::util::TFunctor<Block>( simulation->getChildren(), &Block::update);
			}

			clock->set(true);
		}

		/// Perform the rk4 integration at the specified pass.
		void IntegratorRK4::rk4( int pass)
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