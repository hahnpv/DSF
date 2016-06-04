#include <vector>

	// should be able to create a TSpecificFunctor that doesn't need the *fpt until calling operator()
	// -> this would let us instantiate one TSpecificFunctor per class and re-use it for init, update, rpt, etc.
namespace dsf
{
	namespace util
	{
			///	Take a pointer to a (void) object member and recurse over an 
			/// a std::vector<> using operator()
		template <class TClass> class TSpecificFunctor
		{
		public:
			TSpecificFunctor()//void(TClass::*fpt)(void))
			{ 
//				this->fpt = fpt; 
			};

			virtual void operator()(std::vector<TClass*> &pt2Object, void(TClass::*fpt)(void))
			{
				for (unsigned int i=0; i < pt2Object.size(); i++)
				{
					this->fpt = fpt; 

					(*pt2Object[i].*fpt)();			// execute member function

					if (pt2Object[i]->child())		// recurse through children
						(*this)(pt2Object[i]->children, fpt);
				}
			};  
			
		private:
			void (TClass::*fpt)(void);				// pointer to member function
		};

			///	Take a pointer to a (void) object member and recurse over an 
			/// a std::vector<> using operator(), setting an object reference
			/// Object reference must be valid at template instantiation.
			/// \param TClass Class type of the graph.
			/// \param RClass Class type of the object reference.
		template <class TClass, class RClass> class TSpecificRefFunctor
		{
		public:
			TSpecificRefFunctor(void(TClass::*fpt)(RClass *), RClass &c)
			{ 
				this->fpt = fpt; 
				this->c   = &c;
			};

			virtual void operator()(std::vector<TClass*> &pt2Object)
			{
				for (unsigned int i=0; i < pt2Object.size(); i++)
				{
					(*pt2Object[i].*fpt)(c);			// execute member function

					if (pt2Object[i]->child())		// recurse through children
						(*this)(pt2Object[i]->children);
				}
			};  
			
		private:
			void (TClass::*fpt)(RClass *c);				// pointer to member function
			RClass *c;
		};

			//
			//	Take a pointer to a (RClass) object member and iterate over an array using  
			//	operator(), passing reference c of type RClass
			//
			//	try passing at the function level
			//
	
			///	Take a pointer to a (void) object member and recurse over an 
			/// a std::vector<> using operator(), setting an object reference
			/// Object reference type must be known template instantiation, however \n
			/// reference is not actually needed until operator() is invoked.
			/// \param TClass Class type of the graph.
			/// \param RClass Class type of the object reference.
		template <class TClass, class RClass> class TSpecificRefFunctor2
		{
		public:
			TSpecificRefFunctor2(void(TClass::*fpt)(RClass *))
			{ 
				this->fpt = fpt; 
			};

			virtual void operator()(std::vector<TClass*> &pt2Object, RClass &c)
			{
				for (unsigned int i=0; i < pt2Object.size(); i++)
				{
					(*pt2Object[i].*fpt)(&c);			// execute member function

					if (pt2Object[i]->child())		// recurse through children
						(*this)(pt2Object[i]->children, c);
				}
			};  
			
		private:
			void (TClass::*fpt)(RClass *c);				// pointer to member function
		};
	}
}