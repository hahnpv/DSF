/**
 * @file quat.h
 * @brief Quaternion class for attitude representation.
 *
 * Provides a 4-component quaternion (x, y, z, w) with construction
 * from Euler angles, normalization, and Earth-to-body DCM extraction.
 */
#pragma once

#include <iostream>
#include "mat3.h"
#include "mat4.h"

namespace dsf
{
    namespace util
    {
        /**
         * @brief Quaternion for 3D rotation representation.
         *
         * Components stored in (x, y, z, w) order where w is the scalar part.
         * Supports construction from Euler angles (phi, theta, psi) and
         * extraction of the Earth-to-body direction cosine matrix.
         */
        class Quaternion
        {
        public:
            /// @name Constructors
            /// @{
            Quaternion() {};                                    ///< Default constructor.

            /**
             * @brief Construct from Euler angles.
             * @param phi   Roll angle [rad].
             * @param theta Pitch angle [rad].
             * @param psi   Yaw/heading angle [rad].
             */
            Quaternion(double phi, double theta, double psi);

            /**
             * @brief Construct from quaternion components.
             * @param x X component (vector part).
             * @param y Y component (vector part).
             * @param z Z component (vector part).
             * @param w W component (scalar part).
             */
            Quaternion(double x, double y, double z, double w);
            /// @}

            ~Quaternion() {};                                   ///< Destructor.

            /// @name Euler Angle Accessors
            /// @{
            inline double phi()   { return 1.0; };  ///< Roll angle [rad] (stub — not yet implemented).
            inline double theta() { return 1.0; };  ///< Pitch angle [rad] (stub — not yet implemented).
            inline double psi()   { return 1.0; };  ///< Yaw angle [rad] (stub — not yet implemented).
            /// @}

            /// Compute Earth-to-body direction cosine matrix.
            Mat3 Teb();

            /// Normalize to unit quaternion.
            void normalize();

            /// @name Operator Overloads
            /// @{
            Quaternion operator*(double c);                                 ///< Scalar multiplication.
            Quaternion operator()(double phi, double theta, double psi);    ///< Set from Euler angles.
            /// @}

            /// @name Quaternion Components
            /// @{
            double x;   ///< X component (vector part).
            double y;   ///< Y component (vector part).
            double z;   ///< Z component (vector part).
            double w;   ///< W component (scalar part).
            /// @}
        };

        /// Stream output operator for Quaternion.
        std::ostream &operator<<(std::ostream &stream, Quaternion quat);
    }
}
