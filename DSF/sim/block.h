#pragma once

#include "clock.h"
#include "RTclock.h"
#include <vector>

#include "../util/xml/xml.h"
#include "../util/xml/xmlnode.h"

#include "TClassDict.h"

namespace dsf
{
	namespace sim 
	{
		class Output;
		class Clock;

		/// The block class is the base class on which all simulation members are derived.
		class Block 
		{
		public:
			Block()					{ parent = 0; };			///< Default constructor; null parent pointer.
			virtual ~Block()        {};							///< Destructor.
			virtual void configure(dsf::xml::xmlnode n)			///< XML model configuration
			{
				rptRate = n.attrAsDouble("rpt");
				name = n.parent().attrAsString("name");
			}
			virtual void init()     {};							///< Initialization function
			virtual void update()	{};							///< Update differential equations
			virtual void rpt()      {};							///< Reporting function called once per integration cycle
			virtual void rptSim() { if( sample(rptRate) ) rpt(); };
			virtual void finalize() {};							///< Finalize function
	
			/// Time Functions
			double  t()				{ return clock->t();  };	///< Return the simulation time from Clock
			double dt()				{ return clock->dt(); };	///< Return the simulation rate from Clock
			void set_dt(double dt)	{ clock->set_dt( dt); };	///< Modify the simulation rate from Clock
			void end(void)			{ clock->end(); };			///< End simulation by setting state in Clock
			bool sample(double t=0) { return clock->Sample(t); };	///< Returns false if integrating (t=0), false if not an even increment of (t!=)

			/// Reference Functions
			void ClockRef(Clock *_clock) { clock = _clock; };	///< Function used by Sim to set the clock reference using TFunctor
			void OutputRef(Output *_o) { o = _o; };				///< Function used by Sim to set the output reference using TFunctor

			/// Graph Functions
			void addChild( Block *b)				///< Add Block as child to current Block. Allows for graph topology
			{
				b->parent = this;
				children.push_back( b);
			}
			bool has_children()						///< Return true if children exist; false if there are no children
			{										///  Could eliminate if children stays public.
				if (children.size() != 0)
					return true;
				else
					return false;
			}
			Block * getParent()	{ return parent; };						///< Return the parent class
			Block * getChild(int i) { return children[i]; };			///< Return a given child
			std::vector< Block *> getChildren() { return children; };	///< Returns the child vector

		protected:
			std::vector< Block *>children;		///< Children Block models. Can we protect and provide adequate accessors?
			Block * parent;						///< Parent Block model.
			Output *o;							///< Output reference.
			Clock *clock;						///< Clock reference.
			double rptRate;						///< Report Rate
			std::string name;					///< Model name
		};
	}
}