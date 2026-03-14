/**
 * @file fptr.h
 * @brief Legacy function pointer recursion templates (deprecated).
 *
 * Provides template classes for recursively invoking member functions
 * across block tree structures. Superseded by TFunctor.h which provides
 * the same functionality with a cleaner API.
 *
 * @deprecated Use dsf::util::TRecursiveFunctor from TFunctor.h instead.
 */
#pragma once

#include <vector>

namespace dsf
{
	namespace util
	{
		/**
		 * @brief Recursive member function invoker (legacy).
		 *
		 * Takes a pointer to a void member function and recurses over
		 * a std::vector<> using operator().
		 *
		 * @tparam TClass Class type of the block tree.
		 * @deprecated Use TRecursiveFunctor from TFunctor.h.
		 */
		template <class TClass> class TSpecificFunctor
		{
		public:
			TSpecificFunctor() {};

			virtual void operator()(std::vector<TClass*> &pt2Object, void(TClass::*fpt)(void))
			{
				for (unsigned int i=0; i < pt2Object.size(); i++)
				{
					this->fpt = fpt; 
					(*pt2Object[i].*fpt)();
					if (pt2Object[i]->child())
						(*this)(pt2Object[i]->children, fpt);
				}
			};  
			
		private:
			void (TClass::*fpt)(void);      ///< Member function pointer.
		};

		/**
		 * @brief Recursive member function invoker with bound reference (legacy).
		 *
		 * Takes a pointer to a member function that accepts a reference parameter.
		 * Reference is bound at construction time.
		 *
		 * @tparam TClass Class type of the block tree.
		 * @tparam RClass Type of the bound reference parameter.
		 * @deprecated Use TRecursiveFunctor from TFunctor.h.
		 */
		template <class TClass, class RClass> class TSpecificRefFunctor
		{
		public:
			/**
			 * @brief Construct with member function pointer and reference.
			 * @param fpt Member function pointer (takes RClass*).
			 * @param c   Reference to bind.
			 */
			TSpecificRefFunctor(void(TClass::*fpt)(RClass *), RClass &c)
			{ 
				this->fpt = fpt; 
				this->c   = &c;
			};

			virtual void operator()(std::vector<TClass*> &pt2Object)
			{
				for (unsigned int i=0; i < pt2Object.size(); i++)
				{
					(*pt2Object[i].*fpt)(c);
					if (pt2Object[i]->child())
						(*this)(pt2Object[i]->children);
				}
			};  
			
		private:
			void (TClass::*fpt)(RClass *c);     ///< Member function pointer.
			RClass *c;                          ///< Bound reference.
		};

		/**
		 * @brief Recursive member function invoker with deferred reference (legacy).
		 *
		 * Similar to TSpecificRefFunctor but the reference is passed at
		 * invocation time rather than construction.
		 *
		 * @tparam TClass Class type of the block tree.
		 * @tparam RClass Type of the reference parameter.
		 * @deprecated Use TRecursiveFunctor from TFunctor.h.
		 */
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
					(*pt2Object[i].*fpt)(&c);
					if (pt2Object[i]->child())
						(*this)(pt2Object[i]->children, c);
				}
			};  
			
		private:
			void (TClass::*fpt)(RClass *c);     ///< Member function pointer.
		};
	}
}