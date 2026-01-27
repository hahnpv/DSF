/**
 * @file mat3.h
 * @brief 3x3 matrix class for rotation and transformation operations.
 * 
 * Provides a 3x3 matrix with determinant, inverse, transpose,
 * and matrix-vector multiplication operations.
 */
#pragma once

#include <iostream>
#include "vec3.h"

namespace dsf
{
    namespace util
    {
        /**
         * @brief 3x3 matrix class.
         * 
         * Stores matrix as three row vectors (a0, a1, a2). Supports
         * common matrix operations for coordinate transformations.
         * 
         * ## Usage
         * @code{.cpp}
         * Mat3 rotation(1,0,0, 0,cos(th),-sin(th), 0,sin(th),cos(th));
         * Vec3 body_velocity = rotation * inertial_velocity;
         * Mat3 inv = rotation.inv();
         * @endcode
         */
        class Mat3
        {
        public:
            /// @name Constructors
            /// @{
            Mat3() {};                          ///< Default constructor.
            
            /**
             * @brief Construct from 9 elements (row-major).
             */
            Mat3( double, double, double,
                 double, double, double,
                 double, double, double );

            /**
             * @brief Construct from 3 row vectors.
             */
            Mat3( Vec3, Vec3, Vec3);
            /// @}

            ~Mat3() {};                         ///< Destructor.

            /// @name Row Vectors
            /// @{
            Vec3 a0;    ///< First row.
            Vec3 a1;    ///< Second row.
            Vec3 a2;    ///< Third row.
            /// @}

            /// @name Matrix Operations
            /// @{
            double det();       ///< Compute determinant.
            Mat3   inv();       ///< Compute inverse.
            Mat3   transpose(); ///< Compute transpose.
            /// @}

            /// @name Operator Overloads
            /// @{
            Vec3 &operator[]( int i);           ///< Row access (0, 1, or 2).
            Mat3 operator+( Mat3 m0);           ///< Matrix addition.
            Mat3 operator-( Mat3 m0);           ///< Matrix subtraction.
            Mat3 operator*( Mat3 m0);           ///< Matrix multiplication.
            Mat3 operator*( double c);          ///< Scalar multiplication.
            Mat3 operator/( double c);          ///< Scalar division.
            Mat3 operator*=( double c);         ///< In-place scalar multiply.
            Mat3 operator+=( Mat3 m);           ///< In-place addition.
            Vec3 operator*( Vec3 v0);           ///< Matrix-vector multiplication.

            /**
             * @brief Function-style element assignment.
             */
            Mat3 operator()(double a00, double a01, double a02,
                            double a10, double a11, double a12,
                            double a20, double a21, double a22);
            /// @}
        };

        /// Stream output operator for Mat3.
        std::ostream &operator<<( std::ostream &stream, Mat3 mat);
    }
}
