/**
 * @file quat.h
 * @brief Quaternion class for attitude representation.
 *
 * Provides a unit quaternion with Hamilton product, DCM extraction,
 * Euler angle conversion, and integrator-compatible arithmetic.
 *
 * ## Convention
 * Internal storage is (q0, q1, q2, q3) where q0 is the **scalar** part.
 * Named accessors follow the x/y/z/w convention used by Eigen and most
 * graphics libraries: w() = scalar, x()/y()/z() = vector.
 *
 * ## Kinematic Equation
 * @code{.cpp}
 * // Quaternion derivative from angular velocity [rad/s]:
 * Quaternion omega_q(0, pqr.x, pqr.y, pqr.z);  // pure quaternion
 * dq = q.quat_mult(omega_q) * 0.5;
 * @endcode
 */
#pragma once

#include <iostream>
#include <cmath>
#include "mat3.h"

namespace dsf
{
    namespace util
    {
        // Forward declare Mat4 for legacy operator
        class Mat4;

        /**
         * @brief Unit quaternion for 3D rotation representation.
         *
         * Storage order: q0 (scalar), q1, q2, q3 (vector).
         * The Hamilton product convention is used: p ⊗ q.
         */
        class Quaternion
        {
        public:
            /// @name Constructors
            /// @{

            /// Default constructor (identity quaternion: q0=1, q1=q2=q3=0).
            Quaternion() : q0(1), q1(0), q2(0), q3(0) {}

            /**
             * @brief Construct from Euler angles (3-2-1 / ZYX rotation).
             * @param phi   Roll angle [rad].
             * @param theta Pitch angle [rad].
             * @param psi   Yaw/heading angle [rad].
             */
            Quaternion(double phi, double theta, double psi);

            /**
             * @brief Construct from components.
             * @param q0 Scalar part (w).
             * @param q1 Vector-x part.
             * @param q2 Vector-y part.
             * @param q3 Vector-z part.
             */
            Quaternion(double q0, double q1, double q2, double q3);

            /**
             * @brief Construct quaternion from a Direction Cosine Matrix.
             * Uses Shepperd's method for numerical stability.
             * @param R 3×3 rotation matrix, in the inertial-to-body sense
             *          (e.g. T_b_i from geodesy) so that dcm() round-trips.
             * @return Unit quaternion representing the same rotation.
             */
            static Quaternion fromDCM(const Mat3& R)
            {
                double tr = R[0][0] + R[1][1] + R[2][2];
                double s;
                Quaternion q;
                if (tr > 0) {
                    s = 2.0 * std::sqrt(tr + 1.0);
                    q.q0 = 0.25 * s;
                    q.q1 = (R[1][2] - R[2][1]) / s;
                    q.q2 = (R[2][0] - R[0][2]) / s;
                    q.q3 = (R[0][1] - R[1][0]) / s;
                } else if (R[0][0] > R[1][1] && R[0][0] > R[2][2]) {
                    s = 2.0 * std::sqrt(1.0 + R[0][0] - R[1][1] - R[2][2]);
                    q.q0 = (R[1][2] - R[2][1]) / s;
                    q.q1 = 0.25 * s;
                    q.q2 = (R[0][1] + R[1][0]) / s;
                    q.q3 = (R[2][0] + R[0][2]) / s;
                } else if (R[1][1] > R[2][2]) {
                    s = 2.0 * std::sqrt(1.0 + R[1][1] - R[0][0] - R[2][2]);
                    q.q0 = (R[2][0] - R[0][2]) / s;
                    q.q1 = (R[0][1] + R[1][0]) / s;
                    q.q2 = 0.25 * s;
                    q.q3 = (R[1][2] + R[2][1]) / s;
                } else {
                    s = 2.0 * std::sqrt(1.0 + R[2][2] - R[0][0] - R[1][1]);
                    q.q0 = (R[0][1] - R[1][0]) / s;
                    q.q1 = (R[2][0] + R[0][2]) / s;
                    q.q2 = (R[1][2] + R[2][1]) / s;
                    q.q3 = 0.25 * s;
                }
                q.normalize();
                return q;
            }
            /// @}

            ~Quaternion() {}

            /// @name Component Accessors (standard x/y/z/w names)
            /// @{
            inline double w() const { return q0; }   ///< Scalar part.
            inline double x() const { return q1; }   ///< Vector-x.
            inline double y() const { return q2; }   ///< Vector-y.
            inline double z() const { return q3; }   ///< Vector-z.
            inline double scalar() const { return q0; } ///< Scalar part (alias).
            /// @}

            /// @name Euler Angle Extraction
            /// @{

            /** @brief Roll angle from quaternion [rad]. */
            double phi() const;

            /** @brief Pitch angle from quaternion [rad]. */
            double theta() const;

            /** @brief Yaw/heading angle from quaternion [rad]. */
            double psi() const;
            /// @}

            /// @name Rotation Operations
            /// @{

            /**
             * @brief Inertial-to-body direction cosine matrix (T_b_i).
             *
             * Transforms inertial(parent)-frame vectors into body-frame
             * vectors: v_body = dcm() * v_inertial. Equivalent to the
             * geodesy T_b_i(euler, p) convention — e.g. the 6DOF EOM uses
             * uvw_b = attitude_q.dcm() * (uvw - w_e_i x xyz). For the
             * body-to-inertial rotation, use dcm().transpose().
             * @return 3×3 inertial-to-body DCM derived from the quaternion.
             */
            Mat3 dcm() const;

            /** @deprecated Use dcm() instead. */
            Mat3 Teb() { return dcm(); }

            /**
             * @brief Hamilton quaternion product: this ⊗ rhs.
             * @param rhs Right-hand quaternion.
             * @return Product quaternion (not normalized).
             */
            Quaternion quat_mult(const Quaternion& rhs) const;
            /// @}

            /// @name Normalization
            /// @{

            /** @brief Normalize to unit quaternion in-place. */
            void normalize();

            /** @brief Euclidean magnitude. */
            double magnitude() const
            {
                return std::sqrt(q0*q0 + q1*q1 + q2*q2 + q3*q3);
            }
            /// @}

            /// @name Arithmetic Operators (integrator support)
            /// @{
            Quaternion operator*(double c) const;               ///< Scalar multiply.
            Quaternion operator+(const Quaternion& rhs) const;  ///< Component-wise add.
            Quaternion& operator+=(const Quaternion& rhs);      ///< Component-wise add-assign.
            /// @}

            /** @brief Set from Euler angles (mutating). */
            Quaternion operator()(double phi, double theta, double psi);

            /// @name Quaternion Components (scalar-first: q0=scalar, q1/q2/q3=vector)
            /// @{
            double q0;  ///< Scalar part (w).
            double q1;  ///< Vector-x part.
            double q2;  ///< Vector-y part.
            double q3;  ///< Vector-z part.
            /// @}
        };

        /// Stream output: "q0 q1 q2 q3"
        std::ostream &operator<<(std::ostream &stream, Quaternion quat);
    }
}
