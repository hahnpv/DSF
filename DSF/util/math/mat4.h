/**
 * @file mat4.h
 * @brief 4x4 matrix class for quaternion kinematics.
 *
 * Used primarily for quaternion derivative computation via the
 * 4×4 omega matrix multiplication (Mat4 * Quaternion).
 */
#pragma once

#include <iostream>
#include "quat.h"

namespace dsf
{
    namespace util
    {
        class Quaternion;

        /**
         * @brief 4x4 matrix class.
         *
         * Stores 16 elements as individual named members (a00..a33).
         * Supports determinant, inverse, transpose, and quaternion multiplication.
         */
        class Mat4
        {
        public:
            /// @name Constructors
            /// @{
            Mat4() {};                              ///< Default constructor.

            /**
             * @brief Construct from 16 elements (row-major).
             */
            Mat4( double, double, double, double,
                  double, double, double, double,
                  double, double, double, double,
                  double, double, double, double );
            /// @}

            ~Mat4() {};                             ///< Destructor.

            /// @name Elements
            /// @{
            double a00, a01, a02, a03;  ///< Row 0 elements.
            double a10, a11, a12, a13;  ///< Row 1 elements.
            double a20, a21, a22, a23;  ///< Row 2 elements.
            double a30, a31, a32, a33;  ///< Row 3 elements.
            /// @}

            /// @name Matrix Operations
            /// @{
            double det();               ///< Compute determinant.
            Mat4   inv();               ///< Compute inverse.
            Mat4   transpose();         ///< Compute transpose.
            /// @}

            /// @name Operator Overloads
            /// @{

            /**
             * @brief Function-style element assignment.
             */
            Mat4 operator()(double, double, double, double,
                            double, double, double, double,
                            double, double, double, double,
                            double, double, double, double);

            /// Quaternion multiplication (angular velocity matrix form).
            Quaternion operator*(Quaternion q);
            /// @}
        };
    }
}

/// Stream output operator for Mat4.
std::ostream &operator<<( std::ostream &stream, dsf::util::Mat4 mat);
