////////////////////////////////////////////////////////////////////////////////////////////////////
//  Copyright (c) Microsoft Corporation. All rights reserved.
//  Licensed under the MIT License. See LICENSE in the project root for license information.
////////////////////////////////////////////////////////////////////////////////////////////////////

#include "nest/Range.h"
#include "nest/LoopNestAttributes.h"
#include "nest/LoopNestOps.h"

#include <utilities/include/MathUtil.h>
#include <utilities/include/TypeTraits.h>

#include <llvm/ADT/Hashing.h>
#include <mlir/Dialect/StandardOps/IR/Ops.h>
#include <mlir/IR/Visitors.h>

#include <iostream>
#include <ostream>

using namespace accera::utilities;

namespace accera::ir
{
namespace loopnest
{
    Range::Range(int64_t begin, int64_t end, int64_t increment) :
        _begin(begin),
        _end(end),
        _increment(increment)
    {}

    Range::Range(int64_t begin, mlir::Value end, int64_t increment) :
        _begin(begin),
        _increment(increment)
    {
        auto op = end.getDefiningOp();
        if (auto dimSizeOp = mlir::dyn_cast_or_null<DimSizeOp>(op))
        {
            auto index = dimSizeOp.dimensionIndex();
            _end = index.getValue();
        }
        else if (auto constantEnd = mlir::dyn_cast_or_null<mlir::ConstantOp>(op))
        {
            auto constantAttr = constantEnd.getValue();
            assert(constantAttr.isa<mlir::IntegerAttr>() && "Range Ends must be an integer constant");
            auto constantVal = constantAttr.cast<mlir::IntegerAttr>().getInt();
            _end = static_cast<int64_t>(constantVal);
        }
        else
        {
            assert(false && "Unknown value type");
        }
    }

    Range::Range(int64_t begin, Index endIndex, int64_t increment) :
        _begin(begin),
        _end(endIndex),
        _increment(increment)
    {}

    Range::Range(int64_t begin, OperandIndex endIndex, int64_t increment) :
        _begin(begin),
        _end(endIndex),
        _increment(increment)
    {}

    int64_t Range::Begin() const { return _begin; }

    int64_t Range::End() const
    {
        return std::visit(
            VariantVisitor{
                [](int64_t endVal) -> int64_t {
                    return endVal;
                },
                [](Index endIndex) -> int64_t {
                    assert(false && "Range must be resolved before requesting End()");
                    return 0;
                },
                [](OperandIndex endIndex) -> int64_t {
                    assert(false && "Range must be resolved before requesting End()");
                    return 0;
                },
                [](auto&& endVal) -> int64_t {
                    assert(false && "Unsupported end value type");
                    return -1;
                } },
            _end);
    }

    Index Range::EndIndex() const
    {
        return std::visit(
            VariantVisitor{
                [](int64_t endVal) -> Index {
                    assert(false && "Calling EndIndex() on a constant range");
                    return {};
                },
                [](Index endVal) -> Index {
                    return endVal;
                },
                [](OperandIndex endIndex) -> Index {
                    assert(false && "Calling EndIndex() on an OperandIndex range");
                    return {};
                },
                [](auto&& endVal) -> Index {
                    assert(false && "Unsupported end value type");
                    return {};
                } },
            _end);
    }

    OperandIndex Range::EndOperandIndex() const
    {
        return std::visit(
            VariantVisitor{
                [](int64_t endOpIdx) -> OperandIndex {
                    assert(false && "Calling EndOperandIndex() on a constant range");
                    return {};
                },
                [](Index endOpIdx) -> OperandIndex {
                    assert(false && "Calling EndOperandIndex() on an Index range");
                    return {};
                },
                [](OperandIndex endOpIdx) -> OperandIndex {
                    return endOpIdx;
                },
                [](auto&& endOpIdx) -> OperandIndex {
                    assert(false && "Unsupported end value type");
                    return {};
                } },
            _end);
    }

    bool Range::HasConstantEnd() const
    {
        return std::holds_alternative<int64_t>(_end);
    }

    bool Range::HasIndexEnd() const
    {
        return std::holds_alternative<Index>(_end);
    }

    bool Range::HasOperandIndexEnd() const
    {
        return std::holds_alternative<OperandIndex>(_end);
    }

    int64_t Range::Size() const { return End() - Begin(); }

    int64_t Range::Increment() const { return _increment; }

    int64_t Range::NumIterations() const
    {
        return CeilDiv(End() - Begin(), Increment());
    }

    int64_t Range::LastIterationBegin() const
    {
        auto result = End() - (Size() % Increment());
        if (result == End()) // not a boundary
        {
            result = End() - Increment();
        }
        return result;
    }

    std::ostream& operator<<(std::ostream& os, const Range& r)
    {
        os << "[" << r.Begin() << "," << r.End() << ":" << r.Increment() << ")";
        return os;
    }

    bool operator==(const Range& i1, const Range& i2)
    {
        if (i1.HasConstantEnd() && i2.HasConstantEnd())
        {
            return (i1.Begin() == i2.Begin()) && (i1.End() == i2.End()) && (i1.Increment() == i2.Increment());
        }
        else if (i1.HasIndexEnd() && i2.HasIndexEnd())
        {
            // Both i1 and i2 are unresolved Index values, now they're only equal if they have the same index
            return i1.EndIndex() == i2.EndIndex();
        }
        else if (i1.HasOperandIndexEnd() && i2.HasOperandIndexEnd())
        {
            // Both i1 and i2 are unresolved OperandIndex values, now they're only equal if they have the same index
            return i1.EndOperandIndex() == i2.EndOperandIndex();
        }
        else
        {
            // Can't determine at this time if a constant is equal to an un-resolved value
            return false;
        }
    }

    bool operator!=(const Range& i1, const Range& i2)
    {
        return !(i1 == i2);
    }

    bool operator<(const Range& i1, const Range& i2)
    {
        if (i1.Begin() != i2.Begin())
        {
            return i1.Begin() < i2.Begin();
        }
        else if (i1.HasConstantEnd() && i2.HasConstantEnd())
        {
            return i1.End() < i2.End();
        }
        else if (i1.HasIndexEnd() && i2.HasIndexEnd())
        {
            return i1.EndIndex() < i2.EndIndex();
        }
        else if (i1.HasOperandIndexEnd() && i2.HasOperandIndexEnd())
        {
            return i1.EndOperandIndex() < i2.EndOperandIndex();
        }
        else
        {
            // if only one is resolved, then examine the increment
            return i1.Increment() < i2.Increment();
        }
    }

    bool operator<=(const Range& i1, const Range& i2)
    {
        return i1 < i2 || i1 == i2;
    }

    bool Intersects(const Range& a, const Range& b)
    {
        // std::cout << "Checking intersection of ranges " << a << " and " << b << std::endl;

        int64_t aIter = a.NumIterations();
        int64_t bIter = b.NumIterations();

        if (aIter == 0 || bIter == 0)
        {
            return false;
        }
        auto aLast = a.Begin() + (aIter - 1) * a.Increment();
        auto bLast = b.Begin() + (bIter - 1) * b.Increment();

        return aLast >= b.Begin() && a.Begin() <= bLast;
    }

} // namespace loopnest
} // namespace accera::ir
