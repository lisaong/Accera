////////////////////////////////////////////////////////////////////////////////////////////////////
//  Copyright (c) Microsoft Corporation. All rights reserved.
//  Licensed under the MIT License. See LICENSE in the project root for license information.
//  Authors: Kern Handa
////////////////////////////////////////////////////////////////////////////////////////////////////

#pragma once

#include "ScalarOperations.h"
#include "Value.h"

namespace accera
{
namespace value
{

    /// <summary> A View type that wraps a Value instance and enforces a memory layout that represents a single value </summary>
    class Scalar
    {
    public:
        Scalar();

        /// <summary> Constructor that wraps the provided instance of Value </summary>
        /// <param name="value"> The Value instance to wrap </param>
        /// <param name="name"> The optional name </param>
        Scalar(Value value, const std::string& name = "");

        /// <summary> Constructs an instance from a fundamental type value </summary>
        /// <typeparam name="T"> Any fundamental type accepted by Value </typeparam>
        /// <param name="t"> The value to wrap </param>
        /// <param name="name"> The optional name </param>
        template <typename T>
        Scalar(T t, const std::string& name = "") :
            Scalar(Value(t), name)
        {}

        Scalar(const Scalar&);
        Scalar(Scalar&&) noexcept;
        Scalar& operator=(const Scalar&);
        Scalar& operator=(Scalar&&) noexcept;
        ~Scalar();

        /// <summary> Gets the underlying wrapped Value instance </summary>
        Value GetValue() const;

        /// <summary> Creates a new Scalar instance that contains the same value as this instance </summary>
        /// <returns> A new Scalar instance that points to a new, distinct memory that contains the same value as this instance </returns>
        Scalar Copy() const;

        /// <summary> Arithmetic operators </summary>
        Scalar& operator+=(Scalar);
        Scalar& operator*=(Scalar);
        Scalar& operator-=(Scalar);
        Scalar& operator/=(Scalar);
        Scalar& operator%=(Scalar);

        /// <summary> Returns true if the instance holds constant data </summary>
        bool IsConstant() const
        {
            return _value.IsConstant();
        }

        /// <summary> Retrieve the underlying value as a fundamental type </summary>
        /// <typeparam name="T"> The C++ fundamental type that is being retrieved from the instance </typeparam>
        /// <returns> If the wrapped Value instance's type matches that of the fundamental type, returns the value, otherwise throws </returns>
        template <typename T>
        T Get() const
        {
            return *_value.Get<T*>();
        }

        void SetName(const std::string& name);
        std::string GetName() const;

        /// <summary> Retrieves the type of data stored in the wrapped Value instance </summary>
        /// <returns> The type </returns>
        ValueType GetType() const;

    private:
        friend Scalar operator+(Scalar, Scalar);
        friend Scalar operator*(Scalar, Scalar);
        friend Scalar operator-(Scalar, Scalar);
        friend Scalar operator/(Scalar, Scalar);
        friend Scalar operator%(Scalar, Scalar);

        friend Scalar operator-(Scalar);

        friend Scalar operator++(Scalar);
        friend Scalar operator++(Scalar, int);
        friend Scalar operator--(Scalar);
        friend Scalar operator--(Scalar, int);

        friend Scalar operator==(Scalar, Scalar);
        friend Scalar operator!=(Scalar, Scalar);
        friend Scalar operator<(Scalar, Scalar);
        friend Scalar operator<=(Scalar, Scalar);
        friend Scalar operator>(Scalar, Scalar);
        friend Scalar operator>=(Scalar, Scalar);

        friend Scalar operator&&(Scalar, Scalar);
        friend Scalar operator||(Scalar, Scalar);

        Value _value;
    };

    Scalar MakeScalar(ValueType type, const std::string& name = "");

    template <typename T, std::enable_if_t<std::is_convertible_v<std::vector<T>, detail::ConstantData>, void*> = nullptr>
    Scalar MakeScalar(const std::string& name = "")
    {
        return MakeScalar(GetValueType<T>(), name);
    }

} // namespace value
} // namespace accera

#pragma region implementation

namespace accera
{
namespace value
{
    template <typename T, std::enable_if_t<std::is_arithmetic_v<T>, void*>>
    Scalar Cast(T t, ValueType type)
    {
        switch (type)
        {
        case ValueType::Boolean:
            return Scalar(static_cast<utilities::Boolean>(t));
        case ValueType::Byte:
            return Scalar(static_cast<uint8_t>(t));
        case ValueType::Int8:
            return Scalar(static_cast<int8_t>(t));
        case ValueType::Int16:
            return Scalar(static_cast<int16_t>(t));
        case ValueType::Int32:
            return Scalar(static_cast<int32_t>(t));
        case ValueType::Int64:
            return Scalar(static_cast<int64_t>(t));
        case ValueType::Uint16:
            return Scalar(static_cast<uint16_t>(t));
        case ValueType::Uint32:
            return Scalar(static_cast<uint32_t>(t));
        case ValueType::Uint64:
            return Scalar(static_cast<uint64_t>(t));
        case ValueType::Index:
            return Scalar(static_cast<index_t>(t));
        case ValueType::Float16:
            return Scalar(float16_t{static_cast<float16_t::underlying_type>(t)});
        case ValueType::Float:
            return Scalar(static_cast<float>(t));
        case ValueType::Double:
            return Scalar(static_cast<double>(t));
        default:
            throw utilities::LogicException(utilities::LogicExceptionErrors::illegalState);
        }
    }
} // namespace value
} // namespace accera

#pragma endregion implementation
