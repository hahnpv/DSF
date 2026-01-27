/**
 * @file TFunctor.h
 * @brief Recursive functor for executing member functions across block trees.
 * 
 * Provides template functions to invoke member functions on all blocks
 * in a hierarchical tree structure, automatically recursing through children.
 */
#pragma once

#include <vector>

namespace dsf
{
    namespace util
    {
        /**
         * @brief Execute a void member function recursively on a block tree.
         * 
         * Iterates through the vector and calls the member function on each object,
         * then recursively processes any children.
         * 
         * @tparam TClass Class type that has getChildren() and has_children().
         * @param objvec Vector of pointers to objects.
         * @param fpt    Pointer to member function to call.
         * 
         * ## Usage
         * @code{.cpp}
         * TFunctor<Block>(blocks, &Block::init);
         * TFunctor<Block>(blocks, &Block::update);
         * @endcode
         */
        template <class TClass> 
        void TFunctor(std::vector<TClass*>  objvec, void(TClass::*fpt)(void))
        {
            for (unsigned int i=0; i < objvec.size(); i++)
            {
                (*objvec[i].*fpt)();
                if (objvec[i]->has_children())
                    TFunctor<TClass>(objvec[i]->getChildren(), fpt);
            }
        }

        /**
         * @brief Execute a member function with argument recursively on a block tree.
         * 
         * Like the void version, but passes an object reference to each invocation.
         * 
         * @tparam TClass Class type of the tree nodes.
         * @tparam RClass Class type of the reference argument.
         * @param fpt    Pointer to member function taking RClass*.
         * @param objvec Vector of pointers to objects.
         * @param c      Reference object to pass to each call.
         * 
         * ## Usage
         * @code{.cpp}
         * TFunctor<Block, Clock>(&Block::ClockRef, blocks, clock);
         * @endcode
         */
        template <class TClass, class RClass>
        void TFunctor(void(TClass::*fpt)(RClass *), std::vector<TClass*>  objvec, RClass &c)
        {
            for (unsigned int i=0; i < objvec.size(); i++)
            {
                (*objvec[i].*fpt)(&c);
                if (objvec[i]->has_children())
                    TFunctor<TClass, RClass>(fpt, objvec[i]->getChildren(), c);
            }
        } 
    }
}
