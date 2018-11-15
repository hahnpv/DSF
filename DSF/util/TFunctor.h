#include <vector>

namespace dsf
{
	namespace util
	{
		///	Take a pointer to a (void) object member and recurse over an 
		/// a std::vector executing member objvec.
		/// \param TClass Class type of the graph.
		/// \param fpt Pointer to member function
		template <class TClass> 
//MSVC		void TFunctor(std::vector<TClass*> &objvec, void(TClass::*fpt)(void))
		void TFunctor(std::vector<TClass*>  objvec, void(TClass::*fpt)(void))
		{
			for (unsigned int i=0; i < objvec.size(); i++)
			{
				(*objvec[i].*fpt)();
				if (objvec[i]->has_children())
					TFunctor<TClass>(objvec[i]->getChildren(), fpt);
			}
		}

		///	Take a pointer to a (void) object member and recurse over an 
		/// a std::vector<> using operator(), passing an object of type RClass
		/// to member objvec
		/// \param TClass Class type of the graph.
		/// \param RClass Class type of the object reference.
		/// \param fpt Pointer to member function
		/// \param c Object to pass to fpt
		template <class TClass, class RClass>
//MSVC		void TFunctor(void(TClass::*fpt)(RClass *), std::vector<TClass*> &objvec, RClass &c)
		void TFunctor(void(TClass::*fpt)(RClass *), std::vector<TClass*>  objvec, RClass &c)
		{
			for (unsigned int i=0; i < objvec.size(); i++)
			{
				(*objvec[i].*fpt)(&c);
				if (objvec[i]->has_children())
					TFunctor<TClass, RClass>(fpt, objvec[i]->getChildren(), c);
			}
		} 

		///	Take a pointer to a (void) object member and recurse over an 
		/// a std::vector executing member objvec.
		/// Store value returned 
		/// NONRECURSIVE UNTIL NEEDED!!!
		/// \param TClass Class type of the graph.
/*		/// \param fpt Pointer to member function
		template <class TClass, class RType> 
		RType TFunctor(std::vector<TClass*> &objvec, void(TClass::*fpt)(void))
		{
			RType retval;
			for (unsigned int i=0; i < objvec.size(); i++)
			{
				retval += (*objvec[i].*fpt)();
			//	if (objvec[i]->has_children())
			//		TFunctor<TClass>(objvec[i]->getChildren(), fpt);
			}
			return retval;
		}
		*/
	}
}
