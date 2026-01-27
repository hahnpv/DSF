/**
 * @file vec3.h
 * @brief 3D vector class for simulation mathematics.
 * 
 * Provides a lightweight 3-component vector with common operations
 * including cross product, dot product, and magnitude.
 */
#pragma once

#include <iostream>

namespace dsf
{
    namespace util
    {
        class Mat3;  // Forward declaration

        /**
         * @brief 3D vector class.
         * 
         * Represents a 3-component vector with x, y, z members.
         * Supports standard vector operations and operator overloading.
         * 
         * ## Usage
         * @code{.cpp}
         * Vec3 position(100, 200, 300);
         * Vec3 velocity(1, 2, 3);
         * Vec3 acceleration = force / mass;
         * double speed = velocity.mag();
         * @endcode
         */
        class Vec3
        {
        public:
            /// @name Constructors
            /// @{
            Vec3() { x=0; y=0; z=0; };          ///< Default constructor (zero vector).
            Vec3(double, double, double);       ///< Construct from components.
            /// @}

            ~Vec3() {};                         ///< Destructor.

            /// @name Public Members
            /// @{
            double x;   ///< X component.
            double y;   ///< Y component.
            double z;   ///< Z component.
            /// @}

            /// @name Vector Operations
            /// @{
            double mag();                       ///< Compute magnitude (L2 norm).
            Vec3   unit();                      ///< Return unit vector.
            Vec3   cross(Vec3 vec);             ///< Cross product with another vector.
            Mat3   skew();                      ///< Skew-symmetric matrix form.
            double dot(Vec3 dot);               ///< Dot product with another vector.
            Vec3   scale(double a);             ///< Scale by scalar.
            /// @}

            /// @name Operator Overloads
            /// @{
            double &operator[](int i);          ///< Array-style access (0=x, 1=y, 2=z).
            Vec3 operator+(Vec3 vec);           ///< Vector addition.
            Vec3 operator*(double c);           ///< Scalar multiplication.
            Vec3 operator/(double c);           ///< Scalar division.
            Vec3 operator*=(double c);          ///< In-place scalar multiply.
            Vec3 operator+=(Vec3 vec);          ///< In-place addition.
            Vec3 operator-=(Vec3 vec);          ///< In-place subtraction.
            Vec3 operator-(Vec3 vec);           ///< Vector subtraction.
            Vec3 operator()(double x, double y, double z);  ///< Function-style assignment.
            /// @}

            /// @name Comparison Operators (STL Compliance)
            /// @{
            bool operator== (const Vec3& right) const;
            bool operator!= (const Vec3& right) const;
            bool operator<  (const Vec3& right) const;
            bool operator>  (const Vec3& right) const;
            /// @}
        };

        /// Stream output operator for Vec3.
        std::ostream &operator<<( std::ostream &stream, Vec3 vec);
    }
}
