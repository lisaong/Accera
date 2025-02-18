#!/usr/bin/env python3
####################################################################################################
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for license information.
####################################################################################################

# Tip: to run a particular test / set of tests:
# python -m unittest discover -k "test_input_array" path_to_accera/test dsl_tests.py
# python -m unittest discover -k "DSLTest_01" path_to_accera/test dsl_tests.py

import logging
import sys
import unittest
import os
import pathlib
import numpy as np
from enum import Enum
from typing import Callable, Tuple

DEV_MODE = False
if "@CMAKE_INSTALL_PREFIX@"[1:-1] != "CMAKE_INSTALL_PREFIX":
    sys.path.insert(1, "@CMAKE_INSTALL_PREFIX@")
else:
    DEV_MODE = True
    sys.path.insert(1, os.getcwd())

from accera import ScalarType, Array, Function, Nest, Target, Package
from accera.test import verifiers

TEST_MODE = Package.Mode.DEBUG if DEV_MODE else Package.Mode.RELEASE
TEST_FORMAT = Package.Format.MLIR_DYNAMIC if DEV_MODE else Package.Format.HAT_DYNAMIC
TEST_PACKAGE_DIR = "test_acccgen"

# Groups of types commonly used for tests
INT_TYPES = [
    ScalarType.int8, ScalarType.int16, ScalarType.int32, ScalarType.int64, ScalarType.uint8, ScalarType.uint16,
    ScalarType.uint32, ScalarType.uint64
]
FLOAT_TYPES = [ScalarType.float16, ScalarType.float32, ScalarType.float64]

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
os.environ["OMP_DISPLAY_AFFINITY"] = "TRUE"


# TODO: Remove all @expectedFailure decorators as implementation converges with spec
class FailedReason(Enum):
    NOT_IN_CORE = "Not yet implemented (core)"
    NOT_IN_PY = "Not yet implemented (python)"
    UNKNOWN = "Unknown failure"
    BUG = "Bug"


def expectedFailure(reason: FailedReason, msg: str, condition: bool = True) -> Callable:
    "Extends the unittest.expectedFailure decorator to print failure details and takes an optional condition"

    def _decorator(func):
        @unittest.expectedFailure
        def _wrapper(x):
            print(f"\n{reason.value}: {msg}")
            try:
                return func(x)
            except Exception as e:
                print(f"\t{e}\n")
                raise (e)

        return _wrapper if condition else func

    return _decorator


class DSLTest_01Arrays(unittest.TestCase):
    def _verify_nest(self, nest, args: Tuple[Array], package_name, correctness_check_values=None) -> None:

        # create a HAT package and add the function to it
        package = Package()
        function = package.add(nest, args, base_name=package_name)
        output_dir = pathlib.Path(TEST_PACKAGE_DIR) / package_name

        # build the HAT package
        with verifiers.VerifyPackage(self, package_name, output_dir) as v:
            package.build(package_name, format=TEST_FORMAT, mode=TEST_MODE, output_dir=output_dir)
            if correctness_check_values:
                v.check_correctness(
                    function.name, before=correctness_check_values["pre"], after=correctness_check_values["post"]
                )

    def test_input_array(self) -> None:
        A = Array(shape=(10, 20), role=Array.Role.INPUT, element_type=ScalarType.float32)
        self.assertIsNotNone(A)

    def test_input_array_standard_layout(self) -> None:
        A = Array(shape=(10, 20), role=Array.Role.INPUT, layout=Array.Layout.LAST_MAJOR)
        # A = Array(shape=(10, 20), layout=Array.Layout.LAST_MAJOR, role=Array.Role.INPUT, element_type=ScalarType.float32)
        self.assertIsNotNone(A)

    def test_input_array_dimension_layout(self) -> None:
        A = Array(role=Array.Role.INPUT, element_type=ScalarType.float32, shape=(10, 20), layout=(1, 10))
        self.assertIsNotNone(A)

        A = Array(role=Array.Role.INPUT, element_type=ScalarType.float32, shape=(10, 20), layout=(10, 1))
        self.assertIsNotNone(A)

        A = Array(role=Array.Role.INPUT, element_type=ScalarType.float32, shape=(10, ), layout=(1, ))
        self.assertIsNotNone(A)

        A = Array(role=Array.Role.INPUT, element_type=ScalarType.float32, shape=(10, 20, 50), layout=(1, 10, 200))
        self.assertIsNotNone(A)

        A = Array(role=Array.Role.INPUT, element_type=ScalarType.float32, shape=(10, 20, 50), layout=(200, 10, 1))
        self.assertIsNotNone(A)

        A = Array(role=Array.Role.INPUT, element_type=ScalarType.float32, shape=(10, 20, 50), layout=(1, 200, 10))
        self.assertIsNotNone(A)

        A = Array(role=Array.Role.INPUT, element_type=ScalarType.float32, shape=(10, 20, 50), layout=(10, 200, 1))
        self.assertIsNotNone(A)

    def test_input_array_infinite_major_dimension(self) -> None:
        from accera import inf

        with self.assertRaises(ValueError):
            Array(role=Array.Role.INPUT_OUTPUT, element_type=ScalarType.float32, shape=(inf, inf))

        A = Array(role=Array.Role.INPUT_OUTPUT, element_type=ScalarType.float32, shape=(10, inf))
        self.assertIsNotNone(A)
        self.assertEqual(A.shape[1], inf)

        nest = Nest(shape=(10, 16))
        i, j = nest.get_indices()

        @nest.iteration_logic
        def _():
            A[i, j] += A[i, j]

        package = Package()
        package.add(nest, (A, ), base_name="inf_test")
        self.assertEqual(A.shape[1], 16)

        package_name = "input_array_inf_test"
        with verifiers.VerifyPackage(self, package_name, TEST_PACKAGE_DIR):
            package.build(package_name, format=TEST_FORMAT, mode=TEST_MODE, output_dir=TEST_PACKAGE_DIR)

    def test_input_output_array(self) -> None:
        A = Array(role=Array.Role.INPUT_OUTPUT, element_type=ScalarType.float32, shape=(10, 20))
        self.assertIsNotNone(A)

    def test_const_array(self) -> None:
        for dt in [
                bool,    # np.bool is deprecated in favor of bool
                np.int8,
                np.int16,
                np.int32,
                np.int64,
                np.uint8,
                np.uint16,
                np.uint32,
                np.uint64,
                np.float16,
                np.float32,
                np.float64
        ]:
            D = np.ones((128, 256), dtype=dt)
            A = Array(role=Array.Role.CONST, data=D)
            self.assertIsNotNone(A)

    def test_const_array_type_layout(self) -> None:
        D = np.ones((128, 256), dtype=np.float64)
        for t in [ScalarType.bool] + INT_TYPES + FLOAT_TYPES:
            A = Array(role=Array.Role.CONST, element_type=t, layout=Array.Layout.LAST_MAJOR, data=D)
            self.assertIsNotNone(A)

    def test_temp_array(self) -> None:
        A = Array(role=Array.Role.TEMP, element_type=ScalarType.float32, layout=Array.Layout.LAST_MAJOR, shape=(10, 20))
        self.assertIsNotNone(A)
        B = Array(
            role=Array.Role.TEMP, element_type=ScalarType.float32, layout=Array.Layout.FIRST_MAJOR, shape=(10, 20)
        )
        self.assertIsNotNone(B)

    def test_temp_array_materialization_1(self) -> None:
        # Materializes (allocates) a TEMP array externally to an added function

        def make_test_fn(package, A, B, C):
            T = Array(role=Array.Role.TEMP, element_type=A.element_type, shape=A.shape)

            nest = Nest(A.shape)
            i, j = nest.get_indices()

            @nest.iteration_logic
            def _():
                T[i, j] = A[i, j] + B[i, j]
                C[i, j] += T[i, j]**2.

            return package.add(nest, args=(A, B, C))

        A = Array(shape=(256, 32), role=Array.Role.INPUT)
        B = Array(shape=(256, 32), role=Array.Role.INPUT)
        C = Array(shape=(256, 32), role=Array.Role.INPUT_OUTPUT)

        package = Package()
        make_test_fn(package, A, B, C)
        package_name = "test_temp_array_materialization_1"
        with verifiers.VerifyPackage(self, package_name, TEST_PACKAGE_DIR):
            package.build(package_name, format=TEST_FORMAT, mode=TEST_MODE, output_dir=TEST_PACKAGE_DIR)

    def test_temp_array_materialization_2(self) -> None:
        # Materializes (allocates) a TEMP array within an added function

        package = Package()
        A = Array(shape=(256, 32), role=Array.Role.INPUT)
        B = Array(shape=(256, 32), role=Array.Role.INPUT_OUTPUT)

        def make_init_function(package, A):
            nest = Nest(A.shape)
            i, j = nest.get_indices()

            @nest.iteration_logic
            def _():
                A[i, j] = 3.14

            return package.add(nest, args=(A, ))

        init_fn = make_init_function(package, B)

        def make_helper_function2(package, A, B):

            nest = Nest(A.shape)
            i, j = nest.get_indices()

            @nest.iteration_logic
            def _():
                B[i, j] += A[i, j] * 2.

            return package.add(nest, args=(A, B))

        helper_fn2 = make_helper_function2(package, A, B)

        def test_fn(A, B):
            T = Array(role=Array.Role.TEMP, element_type=A.element_type, shape=A.shape)
            init_fn(T)
            helper_fn2(T, B)
            helper_fn2(A, B)

        package.add(test_fn, args=(A, B))

        package_name = "test_temp_array_materialization_2"
        with verifiers.VerifyPackage(self, package_name, TEST_PACKAGE_DIR):
            package.build(package_name, format=TEST_FORMAT, mode=TEST_MODE, output_dir=TEST_PACKAGE_DIR)

        def test_fn_wrong_role(A, B):
            T = Array(role=Array.Role.INPUT_OUTPUT, element_type=A.element_type, shape=A.shape)
            init_fn(T)
            helper_fn2(T, B)
            helper_fn2(A, B)

        package.add(test_fn_wrong_role, args=(A, B))

        package_name = "test_temp_array_materialization_2_wrong_role"
        with self.assertRaises(ValueError):
            package.build(package_name, format=TEST_FORMAT, mode=TEST_MODE, output_dir=TEST_PACKAGE_DIR, fail_on_error=True)

    def test_temp_array_materialization_3(self) -> None:
        # Materializes (allocates) a TEMP array within some nest iteration logic
        # *without* passing the array as a function argument

        package = Package()
        A = Array(shape=(256, 32), role=Array.Role.INPUT_OUTPUT)
        B = Array(shape=(256, 32), role=Array.Role.INPUT_OUTPUT)

        nest = Nest(A.shape)
        i, j = nest.get_indices()

        @nest.iteration_logic
        def _():
            T = Array(role=Array.Role.TEMP, element_type=A.element_type, shape=(1, ))

            # TODO: inject via introspection if we need to support this scenario
            T._allocate()
            T = T._get_native_array()

            T[0] = B[i, j]
            B[i, j] += A[i, j] * 2.
            A[i, j] = T[0]

        package.add(nest, args=(A, B))
        package_name = "test_temp_array_materialization_3"
        with verifiers.VerifyPackage(self, package_name, TEST_PACKAGE_DIR):
            package.build(package_name, format=TEST_FORMAT, mode=TEST_MODE, output_dir=TEST_PACKAGE_DIR)

    def test_first_major_array_access(self) -> None:
        A = Array(shape=(256, 32), role=Array.Role.INPUT, layout=Array.Layout.FIRST_MAJOR)

        nest = Nest(shape=(256, 32))
        i, j = nest.get_indices()

        @nest.iteration_logic
        def _():
            A[i, j] = 5.0

        A_test = np.random.random((256, 32)).astype(np.float32)
        A_expected = np.ndarray((256, 32)).astype(np.float32)
        A_expected.fill(5.0)
        correctness_check_values = {
            "pre": (A_test, ),
            "post": (A_expected, )
        }
        self._verify_nest(
            nest, (A, ), "test_first_major_array_access", correctness_check_values=correctness_check_values
        )

    def test_last_major_array_access(self) -> None:
        A = Array(shape=(256, 32), role=Array.Role.INPUT, layout=Array.Layout.LAST_MAJOR)

        nest = Nest(shape=(256, 32))
        i, j = nest.get_indices()

        @nest.iteration_logic
        def _():
            A[i, j] = 5.0

        A_test = np.random.random((256, 32)).astype(np.float32, order="F")
        A_expected = np.ndarray((256, 32)).astype(np.float32, order="F")
        A_expected.fill(5.0)
        correctness_check_values = {
            "pre": (A_test, ),
            "post": (A_expected, )
        }
        self._verify_nest(
            nest, (A, ), "test_last_major_array_access", correctness_check_values=correctness_check_values
        )

    def test_array_value_type_cast(self) -> None:
        A = Array(shape=(256, 32), role=Array.Role.INPUT, layout=Array.Layout.FIRST_MAJOR)
        B = Array(
            shape=(256, 32), role=Array.Role.INPUT, layout=Array.Layout.FIRST_MAJOR, element_type=ScalarType.int32
        )

        nest = Nest(shape=(256, 32))
        i, j = nest.get_indices()

        @nest.iteration_logic
        def _():
            A[i, j] = 5    # implicit cast from int8 to float
            B[i, j] = 10    # implicit cast from int8 to int32

        A_test = np.random.random((256, 32)).astype(np.float32)
        A_expected = np.ndarray((256, 32)).astype(np.float32)
        A_expected.fill(5.0)

        B_test = np.random.random((256, 32)).astype(np.int32)
        B_expected = np.ndarray((256, 32)).astype(np.int32)
        B_expected.fill(10)

        correctness_check_values = {
            "pre": (A_test, B_test),
            "post": (A_expected, B_expected)
        }
        self._verify_nest(nest, (A, B), "test_array_value_type_cast", correctness_check_values=correctness_check_values)

    def test_subarray(self) -> None:
        package = Package()

        arr = Array(role=Array.Role.INPUT_OUTPUT, element_type=ScalarType.float32, shape=(256, 256))
        arr0 = arr.sub_array(offsets=(0, 0), shape=(128, 128))
        self.assertEqual(arr0.shape, [128, 128])
        self.assertEqual(arr0.element_type, arr.element_type)
        print(arr0.layout)

        # add a function that utilizes a subarray layout
        def make_subarray_fn(arr0):
            nest = Nest(shape=arr0.shape)
            i, j = nest.get_indices()

            @nest.iteration_logic
            def _():
                arr0[i, j] += 1.

            return package.add(nest, args=(arr0, ))

        subarray_fn = make_subarray_fn(arr0)

        # add a function that instantiates a subarray of the input array and calls the function above
        def main(arr):
            arr1 = arr.sub_array(offsets=(0, 0), shape=(128, 128))
            print(arr1.layout)
            self.assertEqual(arr0.layout, arr1.layout)
            subarray_fn(arr1)

        package.add(main, args=(arr, ))

        package_name = "test_subarray"
        with verifiers.VerifyPackage(self, package_name, TEST_PACKAGE_DIR):
            package.build(package_name, format=TEST_FORMAT, mode=TEST_MODE, output_dir=TEST_PACKAGE_DIR)

    def test_subarray_l2(self) -> None:
        package = Package()

        arr = Array(role=Array.Role.INPUT_OUTPUT, element_type=ScalarType.float32, shape=(256, 256))
        arr0 = arr.sub_array(offsets=(0, 0), shape=(128, 128))
        self.assertEqual(arr0.shape, [128, 128])
        self.assertEqual(arr0.element_type, arr.element_type)
        arr00 = arr0.sub_array(offsets=(64, 64), shape=(64, 64))
        self.assertEqual(arr00.shape, [64, 64])
        self.assertEqual(arr00.element_type, arr0.element_type)

        # add a function that utilizes a subarray layout
        def make_fn(A):
            nest = Nest(shape=A.shape)
            i, j = nest.get_indices()

            @nest.iteration_logic
            def _():
                A[i, j] += 1.

            return package.add(nest, args=(A, ))

        subarray_fn = make_fn(arr0)
        subarray_fn1 = make_fn(arr00)

        # add a function that instantiates a subarray of the input array and calls the function above
        def main(arr):
            arr1 = arr.sub_array(offsets=(0, 0), shape=(128, 128))
            arr11 = arr1.sub_array(offsets=(64, 64), shape=(64, 64))
            print(f"{arr1.layout}\n{arr11.layout}")
            self.assertEqual(arr0.layout, arr1.layout)
            self.assertEqual(arr00.layout, arr11.layout)
            subarray_fn(arr1)
            subarray_fn1(arr11)

        package.add(main, args=(arr, ))

        package_name = "test_subarray_l2"
        with verifiers.VerifyPackage(self, package_name, TEST_PACKAGE_DIR):
            package.build(package_name, format=TEST_FORMAT, mode=TEST_MODE, output_dir=TEST_PACKAGE_DIR)


class DSLTest_02SimpleAffineLoopNests(unittest.TestCase):
    def _create_nest(self, shape: Tuple[int], type=ScalarType.float32) -> Tuple:
        # helper function to create a nest so that we can focus on the logic function
        M, N, S = shape

        A = Array(role=Array.Role.INPUT, element_type=type, shape=(M, S))
        B = Array(role=Array.Role.INPUT, element_type=type, shape=(S, N))
        C = Array(role=Array.Role.INPUT_OUTPUT, element_type=type, shape=(M, N))

        return Nest(shape=(M, N, S)), A, B, C

    def _build_nest(self, nest, args: Tuple[Array], package_name, correctness_check_values=None) -> None:
        # helper function to build a nest so that we can focus on the logic function
        # create a HAT package and add the nest to it
        package = Package()
        function = package.add(nest, args, base_name=package_name)

        # build the HAT package
        with verifiers.VerifyPackage(self, package_name, TEST_PACKAGE_DIR) as v:
            package.build(package_name, format=TEST_FORMAT, mode=TEST_MODE, output_dir=TEST_PACKAGE_DIR)
            if correctness_check_values:
                v.check_correctness(
                    function.name, before=correctness_check_values["pre"], after=correctness_check_values["post"]
                )

    def test_signed_types(self) -> None:
        for t in [ScalarType.int16, ScalarType.int32, ScalarType.int64] + FLOAT_TYPES:

            A = Array(role=Array.Role.INPUT, element_type=t, shape=(16, 16))
            B = Array(role=Array.Role.INPUT, element_type=t, shape=(16, 16))
            C = Array(role=Array.Role.INPUT_OUTPUT, element_type=t, shape=(16, 16))

            nest = Nest(shape=(16, 16))
            i, j = nest.get_indices()

            @nest.iteration_logic
            def _():
                C[i, j] += A[i, j] + B[i, j]
                C[i, j] += A[i, j] - B[i, j]
                C[i, j] += A[i, j] * B[i, j]
                C[i, j] += A[i, j] / B[i, j]

            dtype = np.dtype(t.name)

            A_test = np.random.random(A.shape).astype(dtype)
            B_test = np.ones((C.shape)).astype(dtype)    # avoid divide by zero
            C_test = np.random.random(C.shape).astype(dtype)

            C_ref = C_test + A_test + B_test
            C_ref = C_ref + A_test - B_test
            C_ref = C_ref + A_test * B_test
            C_ref = C_ref + A_test / B_test

            if t == ScalarType.float16:    # TODO: verification issue with correctness check?
                correctness_check_values = None
            else:
                correctness_check_values = {
                    "pre": [A_test, B_test, C_test],
                    "post": [A_test, B_test, C_ref]
                }

            self._build_nest(nest, [A, B, C], f"test_types_{t.name}", correctness_check_values)

    def test_unsigned_types(self) -> None:
        for t in [ScalarType.uint8, ScalarType.uint16, ScalarType.uint32, ScalarType.uint64]:

            A = Array(role=Array.Role.INPUT, element_type=t, shape=(16, 16))
            B = Array(role=Array.Role.INPUT, element_type=t, shape=(16, 16))
            C = Array(role=Array.Role.INPUT_OUTPUT, element_type=t, shape=(16, 16))

            nest = Nest(shape=(16, 16))
            i, j = nest.get_indices()

            @nest.iteration_logic
            def _():
                C[i, j] += A[i, j] + B[i, j]
                C[i, j] += A[i, j] - B[i, j]
                C[i, j] += A[i, j] * B[i, j]
                C[i, j] += A[i, j] / B[i, j]

            dtype = np.dtype(t.name)
            A_test = np.random.random(A.shape).astype(dtype)
            B_test = np.ones((C.shape)).astype(dtype)    # avoid divide by zero
            C_test = np.random.random(C.shape).astype(dtype)

            C_ref = C_test + A_test + B_test
            C_ref = C_ref + A_test - B_test
            C_ref = C_ref + A_test * B_test
            C_ref = C_ref + A_test / B_test

            correctness_check_values = {
                "pre": [A_test, B_test, C_test],
                "post": [A_test, B_test, C_ref]
            }

            self._build_nest(nest, [A, B, C], f"test_types_{t.name}", correctness_check_values)

    def test_arithmetic_operations(self) -> None:
        for t in INT_TYPES + FLOAT_TYPES:
            nest, A, B, C = self._create_nest((16, 10, 11), type=t)
            i, j, k = nest.get_indices()

            @nest.iteration_logic
            def _():
                C[i, j] = A[i, k] + B[k, j]    # test assignment
                C[i, j] += A[i, k] - B[k, j]
                C[i, j] += A[i, k] * B[k, j]
                C[i, j] += A[i, k] / B[k, j]
                C[i, j] += -A[i, k]
                C[i, j] += A[i, k] // B[k, j]
                C[i, j] += A[i, k] % B[k, j]
                C[i, j] += A[i, k]**B[k, j]

            self._build_nest(nest, [A, B, C], f"test_arithmetic_operations_{t.name}")

    def test_relational_operations(self) -> None:
        from accera._lang_python._lang import _If

        for t in [ScalarType.bool] + INT_TYPES + FLOAT_TYPES:
            nest, A, B, C = self._create_nest((16, 10, 11))
            i, j, k = nest.get_indices()

            @nest.iteration_logic
            def _():
                def f1():
                    C[i, j] += A[i, k] + B[k, j]

                def f2():
                    C[i, j] -= A[i, k] + B[k, j]

                def f3():
                    C[i, j] *= A[i, k] + B[k, j]

                def f4():
                    C[i, j] /= A[i, k] + B[k, j]

                # BUGBUG: this syntax probably needs to change
                _If(A[i, k] == B[k, j], f1)
                _If(A[i, k] != B[k, j], f2)
                _If(A[i, k] < B[k, j], f3)
                _If(A[i, k] <= B[k, j], f4)
                _If(A[i, k] > B[k, j], f1)
                _If(A[i, k] >= B[k, j], f2)

            self._build_nest(nest, [A, B, C], f"test_relational_operations_{t.name}")

    def test_logical_operations(self) -> None:
        from accera import logical_and, logical_or, logical_not

        for t in [ScalarType.bool] + INT_TYPES:
            nest, A, B, C = self._create_nest((16, 10, 11), type=t)
            i, j, k = nest.get_indices()

            @nest.iteration_logic
            def _():
                C[i, j] += logical_not(A[i, k])
                C[i, j] += logical_and(A[i, k], B[k, j])
                C[i, j] += logical_or(A[i, k], B[k, j])

            self._build_nest(nest, [A, B, C], f"test_logical_operations_{t.name}")

    def test_bitwise_operations(self) -> None:
        for t in INT_TYPES:
            nest, A, B, C = self._create_nest((16, 10, 11), type=t)
            i, j, k = nest.get_indices()

            @nest.iteration_logic
            def _():
                C[i, j] += B[j, k] >> 1
                C[i, j] += A[i, j] << 2
                C[i, j] += A[i, j] & B[j, k]
                C[i, j] += A[i, j] | B[j, k]
                C[i, j] += A[i, j] ^ B[j, k]
                C[i, j] += ~A[i, j]

            self._build_nest(nest, [A, B, C], f"test_bitwise_operations_{t.name}")

    def test_intrinsics(self) -> None:
        from accera import max, min

        for t in INT_TYPES + FLOAT_TYPES:

            nest, A, B, C = self._create_nest((16, 10, 11), type=t)
            i, j, k = nest.get_indices()

            @nest.iteration_logic
            def _():
                C[i, j] += max(A[i, j], B[j, k])
                C[i, j] += min(A[i, j], B[j, k])

            self._build_nest(nest, [A, B, C], f"test_intrinsics_{t.name}")

    def test_intrinsics_float(self) -> None:
        from accera import abs, sqrt, exp, log, log10, log2, sin, cos, ceil, floor, tan, cosh, sinh, tanh
        # from accera._lang_python import fast_exp, fast_exp_mlas

        for t in FLOAT_TYPES:

            nest, A, B, C = self._create_nest((16, 10, 11), type=t)
            i, j, k = nest.get_indices()

            @nest.iteration_logic
            def _():
                C[i, j] += abs(A[i, j])
                C[i, j] += exp(A[i, j])
                # C[i, j] += fast_exp(A[i, j])
                # C[i, j] += fast_exp_mlas(A[i, j])
                C[i, j] += log(B[j, k])
                C[i, j] += log2(B[j, k])
                C[i, j] += log10(A[i, j])
                C[i, j] += sin(A[i, j])
                C[i, j] += cos(B[j, k])
                C[i, j] += tan(A[i, j])
                C[i, j] += sqrt(B[j, k])
                C[i, j] += ceil(B[j, k])
                C[i, j] += floor(A[i, j])
                C[i, j] += sinh(A[i, j])
                C[i, j] += cosh(B[j, k])
                C[i, j] += tanh(A[i, j])

            self._build_nest(nest, [A, B, C], f"test_intrinsics_float_{t.name}")

    def test_convenience_syntax_1(self) -> None:
        nest, A, B, C = self._create_nest((16, 10, 11))
        i, j, k = nest.get_indices()

        @nest.iteration_logic
        def _():
            C[i, j] += A[i, k] + B[k, j]

        package = Package()
        package_name = "test_convenience_syntax_2"
        package.add(nest, args=(A, B, C), base_name="matmul")

        with verifiers.VerifyPackage(self, package_name, TEST_PACKAGE_DIR):
            package.build(package_name, format=TEST_FORMAT, mode=TEST_MODE, output_dir=TEST_PACKAGE_DIR)

    def test_convenience_syntax_2(self) -> None:

        nest, A, B, C = self._create_nest((16, 10, 11))
        i, j, k = nest.get_indices()

        @nest.iteration_logic
        def _():
            C[i, j] += A[i, k] * B[k, j]

        plan = nest.create_plan()

        package = Package()
        package_name = "test_convenience_syntax_2"
        package.add(plan, args=(A, B, C), base_name="matmul")

        with verifiers.VerifyPackage(self, package_name, TEST_PACKAGE_DIR):
            package.build(package_name, format=TEST_FORMAT, mode=TEST_MODE, output_dir=TEST_PACKAGE_DIR)


class DSLTest_03Schedules(unittest.TestCase):
    def _create_nest(self, shape: Tuple[int], type=ScalarType.float32) -> Tuple:
        M, N, S = shape

        A = Array(role=Array.Role.INPUT, element_type=type, shape=(M, S))
        B = Array(role=Array.Role.INPUT, element_type=type, shape=(S, N))
        C = Array(role=Array.Role.INPUT_OUTPUT, element_type=type, shape=(M, N))

        return Nest(shape=(M, N, S)), A, B, C

    def _verify_schedule(self, schedule, args: Tuple[Array], package_name, correctness_check_values=None) -> None:

        # create a HAT package and add the function to it
        package = Package()
        function = package.add(schedule, args, base_name="schedule_test")
        output_dir = pathlib.Path(TEST_PACKAGE_DIR) / package_name

        # build the HAT package
        with verifiers.VerifyPackage(self, package_name, output_dir) as v:
            package.build(package_name, format=TEST_FORMAT, mode=TEST_MODE, output_dir=output_dir)
            if correctness_check_values:
                v.check_correctness(
                    function.name, before=correctness_check_values["pre"], after=correctness_check_values["post"]
                )

    def test_schedule_reorder(self) -> None:
        nest, A, B, C = self._create_nest((16, 10, 11))
        i, j, k = nest.get_indices()

        @nest.iteration_logic
        def _():
            C[i, j] += A[i, k] * B[k, j]

        schedule = nest.create_schedule()
        schedule.reorder(k, i, j)
        self.assertEqual(schedule._indices, [k, i, j])

        schedule.reorder(order=(j, i, k))
        self.assertEqual(schedule._indices, [j, i, k])

        self._verify_schedule(schedule, [A, B, C], "test_schedule_reorder")

    def test_schedule_split(self) -> None:
        nest, A, B, C = self._create_nest((16, 10, 11))
        i, j, k = nest.get_indices()

        @nest.iteration_logic
        def _():
            C[i, j] += A[i, k] * B[k, j]

        schedule = nest.create_schedule()
        ii = schedule.split(i, 4)
        iii = schedule.split(i, 2)
        iiii = schedule.split(ii, 2)
        for index in [ii, iii, iiii]:
            self.assertIsNotNone(index)
        self.assertEqual(schedule._indices, [i, iii, ii, iiii, j, k])
        self._verify_schedule(schedule, [A, B, C], "test_schedule_split1")

        # split size does not divide the dimension size
        schedule2 = nest.create_schedule()
        kk = schedule2.split(k, 4)    # original size of dimension k was 11
        self.assertIsNotNone(kk)
        self.assertEqual(schedule2._indices, [i, j, k, kk])
        self._verify_schedule(schedule2, [A, B, C], "test_schedule_split2")

        # split size == dimension size
        schedule3 = nest.create_schedule()
        kk = schedule3.split(k, 11)    # original size of dimension k was 11
        self.assertIsNotNone(kk)
        self.assertEqual(schedule3._indices, [i, j, k, kk])
        self._verify_schedule(schedule3, [A, B, C], "test_schedule_split3")

        # split size > dimension size
        schedule4 = nest.create_schedule()
        kk = schedule4.split(k, 13)    # original size of dimension k was 11
        self.assertIsNotNone(kk)
        self.assertEqual(schedule4._indices, [i, j, k, kk])
        self._verify_schedule(schedule4, [A, B, C], "test_schedule_split4")

    def test_schedule_set_invalid_order(self) -> None:
        nest, A, B, C = self._create_nest((16, 10, 11))
        i, j, k = nest.get_indices()

        @nest.iteration_logic
        def _():
            C[i, j] += A[i, k] * B[k, j]

        schedule = nest.create_schedule()
        ii = schedule.split(i, 2)
        iii = schedule.split(ii, 2)
        jj = schedule.split(j, 5)
        self.assertEqual(schedule._indices, [i, ii, iii, j, jj, k])

        with self.assertRaises(ValueError):
            schedule.reorder(k, i, jj, j)
        self.assertEqual(schedule._indices, [i, ii, iii, j, jj, k])

        with self.assertRaises(ValueError):
            schedule.reorder(k, ii, iii, j, jj, i)
        self.assertEqual(schedule._indices, [i, ii, iii, j, jj, k])

        schedule.reorder(i, j, ii, jj, iii, k)
        self.assertEqual(schedule._indices, [i, j, ii, jj, iii, k])

    def test_schedule_tile(self) -> None:
        nest, A, B, C = self._create_nest((16, 10, 11))
        i, j, k = nest.get_indices()

        @nest.iteration_logic
        def _():
            C[i, j] += A[i, k] * B[k, j]

        schedule = nest.create_schedule()
        ii, jj, kk = schedule.tile({
            i: 8,
            j: 2,
            k: 3
        })
        self.assertIsNotNone(ii)
        self.assertIsNotNone(jj)
        self.assertIsNotNone(kk)
        self.assertEqual(schedule._indices, [i, ii, j, jj, k, kk])
        self._verify_schedule(schedule, [A, B, C], "test_schedule_tile")

        # tile a subset of the iteration space
        schedule1 = nest.create_schedule()
        iii, kkk = schedule1.tile({
            i: 8,
            k: 3
        })
        self.assertIsNotNone(iii)
        self.assertIsNotNone(kkk)
        self.assertEqual(schedule1._indices, [i, iii, j, k, kkk])
        self._verify_schedule(schedule1, [A, B, C], "test_schedule_tile_subset")

    def test_schedule_skew(self) -> None:
        for N in [10, 224]:    # input sizes
            for K in [1, 3, 5]:    # filter sizes
                M = N - K + 1    # output size

                A = Array(role=Array.Role.INPUT, shape=(N, ))
                B = Array(role=Array.Role.INPUT, shape=(K, ))
                C = Array(role=Array.Role.INPUT_OUTPUT, shape=(M, ))

                nest = Nest(shape=(M, K))
                i, j = nest.get_indices()

                @nest.iteration_logic
                def _():
                    C[i] += A[i + j] * B[j]

                schedule = nest.create_schedule()

                A_test = np.random.random(A.shape).astype(np.float32)
                B_test = np.random.random(B.shape).astype(np.float32)
                C_test = np.random.random(C.shape).astype(np.float32)
                correctness_check_values = {
                    "pre": [A_test, B_test, C_test],
                    "post": [A_test, B_test, C_test + np.convolve(np.flip(B_test), A_test, "valid")]
                }

                # Skew dimension i with respect to dimension j.
                schedule.skew(i, j)
                self._verify_schedule(schedule, [A, B, C], f"test_schedule_skew_i_j_{N}_{K}", correctness_check_values)

                # Skew dimension j with respect to dimension i.
                schedule1 = nest.create_schedule()
                schedule1.skew(j, i)
                self._verify_schedule(schedule1, [A, B, C], f"test_schedule_skew_j_i_{N}_{K}", correctness_check_values)

    def test_schedule_skew_unrolling(self) -> None:
        N = 10    # input size
        K = 3    # filter size
        M = N - K + 1    # output size = 8

        A = Array(role=Array.Role.INPUT, shape=(N, ))
        B = Array(role=Array.Role.INPUT, shape=(K, ))
        C = Array(role=Array.Role.INPUT_OUTPUT, shape=(M, ))

        nest = Nest(shape=(M, K))
        i, j = nest.get_indices()

        @nest.iteration_logic
        def _():
            C[i] += A[i + j] * B[j]

        A_test = np.random.random(A.shape).astype(np.float32)
        B_test = np.random.random(B.shape).astype(np.float32)
        C_test = np.random.random(C.shape).astype(np.float32)
        correctness_check_values = {
            "pre": [A_test, B_test, C_test],
            "post": [A_test, B_test, C_test + np.convolve(np.flip(B_test), A_test, "valid")]
        }

        # Skew dimension i with respect to dimension j, with unrolling.
        schedule = nest.create_schedule()
        schedule.skew(i, j, unroll_loops_smaller_than=3)
        self._verify_schedule(schedule, [A, B, C], "test_schedule_skew_i_j_with_unrolling", correctness_check_values)

        # Skew dimension j with respect to dimension i, with unrolling.
        schedule1 = nest.create_schedule()
        schedule1.skew(j, i, unroll_loops_smaller_than=3)
        self._verify_schedule(schedule1, [A, B, C], f"test_schedule_skew_j_i_with_unrolling", correctness_check_values)

    def test_schedule_pad(self) -> None:
        nest, A, B, C = self._create_nest((16, 10, 11))
        i, j, k = nest.get_indices()

        @nest.iteration_logic
        def _():
            C[i, j] += A[i, k] * B[k, j]

        schedule = nest.create_schedule()

        # Adds empty elements to the beginning of dimension i, j, k
        schedule.pad(i, 2)
        ii = schedule.split(i, 3)    # (2 + 16) // 3
        # should result in these loops for i, ii
        #  i: [2, 3:3), ii: [0, 1:1)  <-- partial (front padding)
        #  i: [3: 18:3), ii: [0, 3:1) <-- full

        schedule.pad(j, 3)
        jj = schedule.split(j, 3)    # (3 + 10) // 3
        # should result in these loops for j, jj
        #  j: [3, 12:3), jj: [0, 3:3)   <-- full (front padding == split size)
        #  j: [12, 13:3), jj: [0, 1:1)  <-- partial (automatic back padding)

        schedule.pad(k, 11)
        kk = schedule.split(k, 4)    # (11 + 11) // 4
        # should result in these loops for k, kk
        #  k: [11, 12:1), kk: [0, 1: 1) <-- partial
        #  k: [12, 20:4), kk: [0: 4: 1) <-- full
        #  k: [20, 22:4), kk: [0: 2: 1) <-- partial (automatic back padding)

        schedule.reorder(i, ii, k, j, jj, kk)

        A_test = np.random.random(A.shape).astype(np.float32)
        B_test = np.random.random(B.shape).astype(np.float32)
        C_test = np.random.random(C.shape).astype(np.float32)
        correctness_check_values = {
            "pre": [A_test, B_test, C_test],
            "post": [A_test, B_test, C_test + A_test @ B_test]
        }
        self._verify_schedule(schedule, [A, B, C], "test_schedule_pad", correctness_check_values)

    def test_convenience_syntax(self) -> None:

        nest, A, B, C = self._create_nest((16, 10, 11))
        i, j, k = nest.get_indices()

        @nest.iteration_logic
        def _():
            C[i, j] += A[i, k] * B[k, j]

        schedule = nest.create_schedule()

        package = Package()
        package_name = "test_convenience_syntax"
        package.add(schedule, args=(A, B, C), base_name="plan_test")

        with verifiers.VerifyPackage(self, package_name, TEST_PACKAGE_DIR):
            package.build(package_name, format=TEST_FORMAT, mode=TEST_MODE, output_dir=TEST_PACKAGE_DIR)


class DSLTest_04Fusing(unittest.TestCase):
    def _verify_schedule(self, schedule, args: Tuple[Array], package_name, correctness_check_values) -> None:
        # create a HAT package and add the function to it
        package = Package()
        function = package.add(schedule, args, base_name="fusing_test")
        output_dir = pathlib.Path(TEST_PACKAGE_DIR) / package_name

        # build the HAT package
        with verifiers.VerifyPackage(self, package_name, output_dir) as v:
            package.build(package_name, format=TEST_FORMAT, mode=TEST_MODE, output_dir=output_dir)
            if correctness_check_values:
                v.check_correctness(
                    function.name, before=correctness_check_values["pre"], after=correctness_check_values["post"]
                )

    def test_full_iteration_space_fusing(self) -> None:
        from accera import fuse, Nest

        A = Array(role=Array.Role.INPUT, shape=(16, 16))
        B = Array(role=Array.Role.INPUT, shape=(16, 16))
        C = Array(role=Array.Role.INPUT_OUTPUT, shape=(16, 16))

        # Create nest0 and schedule
        nest0 = Nest(shape=(16, 16))
        i0, j0 = nest0.get_indices()

        @nest0.iteration_logic
        def _():
            C[i0, j0] += A[i0, j0]

        schedule0 = nest0.create_schedule()

        # Create nest1 and schedule1
        nest1 = Nest(shape=(16, 16))
        i1, j1 = nest1.get_indices()

        @nest1.iteration_logic
        def _():
            C[i1, j1] *= B[i1, j1]

        schedule1 = nest1.create_schedule()

        # Create a fused schedule
        schedule = fuse(schedule0, schedule1)
        f, i, j = schedule.get_indices()

        schedule.reorder(i, j, f)

        A_test = np.random.random(A.shape).astype(np.float32)
        B_test = np.random.random(B.shape).astype(np.float32)
        C_test = np.random.random(C.shape).astype(np.float32)
        correctness_check_values = {
            "pre": [A_test, B_test, C_test],
            "post": [A_test, B_test, (C_test + A_test) * B_test]
        }
        self._verify_schedule(schedule, (A, B, C), "test_full_iteration_space_fusing1", correctness_check_values)

        # computing the output block-by-block:
        #  first computing C[0:4, 0:4] += A[0:4, 0:4]
        #  then computing C[0:4, 0:4] *= B[0:4, 0:4]
        ii, jj = schedule.tile({
            i: 4,
            j: 4
        })
        schedule.reorder(i, j, f, ii, jj)

        self._verify_schedule(schedule, (A, B, C), "test_full_iteration_space_fusing2", correctness_check_values)

    def test_partial_iteration_space_fusing_1(self) -> None:
        from accera import fuse, Nest, max
        from accera._lang_python._lang import Scalar

        A = Array(role=Array.Role.INPUT, shape=(16, 11))
        B = Array(role=Array.Role.INPUT, shape=(11, 10))
        C = Array(role=Array.Role.INPUT, shape=(16, 10))

        # Fully-connected neural layer with activation: C = op(C + A @ B)
        # Create nest0 and schedule0
        nest0 = Nest(shape=(16, 10, 11))
        i0, j0, k0 = nest0.get_indices()

        @nest0.iteration_logic
        def _():
            C[i0, j0] += A[i0, k0] * B[k0, j0]

        schedule0 = nest0.create_schedule()

        # Create nest1 and schedule1
        nest1 = Nest(shape=(16, 10))
        i1, j1 = nest1.get_indices()

        @nest1.iteration_logic
        def _():
            # BUGBUG: should implicitly convert Scalar
            C[i1, j1] = max(C[i1, j1], Scalar(0.))

        schedule1 = nest1.create_schedule()

        schedule = fuse((schedule0, schedule1), partial=2)
        f, i, j, k = schedule.get_indices()
        schedule.reorder(i, j, f, k)

        # unfused indices (k) must not precede the fusing index (f)
        with self.assertRaises(ValueError):
            schedule.reorder(i, j, k, f)
        self.assertEqual(schedule._indices, [i, j, f, k])

        A_test = np.random.random(A.shape).astype(np.float32)
        B_test = np.random.random(B.shape).astype(np.float32)
        C_test = np.random.random(C.shape).astype(np.float32)
        correctness_check_values = {
            "pre": [A_test, B_test, C_test],
            "post": [A_test, B_test, np.maximum(C_test + A_test @ B_test, 0.)]
        }
        self._verify_schedule(schedule, (A, B, C), "test_partial_iteration_space_fusing_1", correctness_check_values)

    def test_partial_iteration_space_fusing_2(self) -> None:
        from accera import fuse, Nest

        A = Array(role=Array.Role.INPUT_OUTPUT, shape=(16, ))
        B = Array(role=Array.Role.INPUT_OUTPUT, shape=(4, ))

        n0 = Nest([16])
        i0 = n0.get_indices()

        @n0.iteration_logic
        def _():
            A[i0] *= A[i0]

        s0 = n0.create_schedule()

        n1 = Nest([16, 4])
        i1, j1 = n1.get_indices()

        @n1.iteration_logic
        def _():
            B[j1] += A[i1]

        s1 = n1.create_schedule()

        fs = fuse((s0, s1), partial=1)
        f, i, j = fs.get_indices()
        jj = fs.split(j, 2)
        fs.reorder(i, f, j, jj)

        A_test_pre = np.random.random(A.shape).astype(np.float32)
        B_test_pre = np.random.random(B.shape).astype(np.float32)
        A_test_post = A_test_pre * A_test_pre
        B_test_post = B_test_pre + np.sum(A_test_post)
        correctness_check_values = {
            "pre": [A_test_pre, B_test_pre],
            "post": [A_test_post, B_test_post]
        }

        self._verify_schedule(fs, (A, B), "test_partial_iteration_space_fusing_2", correctness_check_values)

    def test_unequal_iteration_space_fusing_1(self) -> None:
        from accera import fuse, Nest

        A = Array(role=Array.Role.INPUT, shape=(16, 16))
        B = Array(role=Array.Role.INPUT, shape=(16, 10))
        C = Array(role=Array.Role.INPUT_OUTPUT, shape=(16, 16))

        # Create nest0 and schedule
        nest0 = Nest(shape=(16, 16))
        i0, j0 = nest0.get_indices()

        @nest0.iteration_logic
        def _():
            C[i0, j0] += A[i0, j0]

        schedule0 = nest0.create_schedule()

        # Create nest1 and schedule1 with a smaller iteration space size
        nest1 = Nest(shape=(16, 10))
        i1, j1 = nest1.get_indices()

        @nest1.iteration_logic
        def _():
            C[i1, j1] *= B[i1, j1]

        schedule1 = nest1.create_schedule()

        # Create a fused schedule: the smaller iteration space (nest1) should
        # be automatically end-padded with no-ops

        schedule = fuse(schedule0, schedule1)
        f, i, j = schedule.get_indices()
        schedule.reorder(i, j, f)

        # Emitted fused loop should look like:
        # for i in range(0, 16):
        #   for j in range(0, 10):
        #      for f in range(2):
        #         if f == 0:
        #           C[i, j] += A[i, j]
        #         if f == 1:
        #           C[i, j] *= B[i, j]
        #   for j in range(10, 16):
        #      for f in range(2):
        #         if f == 0:
        #           C[i, j] += A[i, j]

        A_test = np.random.random(A.shape).astype(np.float32)
        B_test = np.random.random(B.shape).astype(np.float32)
        C_test = np.random.random(C.shape).astype(np.float32)

        C_ref = C_test + A_test    # nest0
        C_ref[:, :B.shape[1]] = C_ref[:, :B.shape[1]] * B_test    # nest1

        correctness_check_values = {
            "pre": [A_test, B_test, C_test],
            "post": [A_test, B_test, C_ref]
        }
        self._verify_schedule(schedule, (A, B, C), "test_unequal_iteration_space_fusing_1", correctness_check_values)

    def test_unequal_iteration_space_fusing_2(self) -> None:
        from accera import fuse, Nest

        A = Array(role=Array.Role.INPUT, shape=(16, 10))
        B = Array(role=Array.Role.INPUT, shape=(16, 16))
        C = Array(role=Array.Role.INPUT_OUTPUT, shape=(16, 16))

        # Create nest0 and schedule
        nest0 = Nest(shape=(16, 10))
        i0, j0 = nest0.get_indices()

        @nest0.iteration_logic
        def _():
            C[i0, j0] += A[i0, j0]

        schedule0 = nest0.create_schedule()

        # Create nest1 and schedule1 with a larger iteration space size
        nest1 = Nest(shape=(16, 16))
        i1, j1 = nest1.get_indices()

        @nest1.iteration_logic
        def _():
            C[i1, j1] *= B[i1, j1]

        schedule1 = nest1.create_schedule()

        # Create a fused schedule: the smaller iteration space (nest0) should
        # be automatically end-padded with no-ops

        schedule = fuse(schedule0, schedule1)
        f, i, j = schedule.get_indices()
        schedule.reorder(i, j, f)

        # Emitted fused loop should look like:
        # for i in range(0, 16):
        #   for j in range(0, 10):
        #      for f in range(2):
        #         if f == 0:
        #           C[i, j] += A[i, j]
        #         if f == 1:
        #           C[i, j] *= B[i, j]
        #   for j in range(10, 16):
        #      for f in range(2):
        #         if f == 1:
        #           C[i, j] *= B[i, j]

        A_test = np.random.random(A.shape).astype(np.float32)
        B_test = np.random.random(B.shape).astype(np.float32)
        C_test = np.random.random(C.shape).astype(np.float32)
        C_ref = np.copy(C_test)

        C_ref[:, :A.shape[1]] = C_test[:, :A.shape[1]] + A_test    # nest0
        C_ref *= B_test    # nest1

        correctness_check_values = {
            "pre": [A_test, B_test, C_test],
            "post": [A_test, B_test, C_ref]
        }
        self._verify_schedule(schedule, (A, B, C), "test_unequal_iteration_space_fusing_2", correctness_check_values)

    def test_unequal_iteration_space_fusing_3(self) -> None:
        from accera import fuse, Nest

        A = Array(role=Array.Role.INPUT, shape=(16, 16))
        B = Array(role=Array.Role.INPUT, shape=(16, 10))
        C = Array(role=Array.Role.INPUT_OUTPUT, shape=(16, 16))

        # Create nest0 and schedule
        nest0 = Nest(shape=(16, 16))
        i0, j0 = nest0.get_indices()

        @nest0.iteration_logic
        def _():
            C[i0, j0] += A[i0, j0]

        schedule0 = nest0.create_schedule()

        # Create nest1 and schedule1 with a smaller iteration space size
        nest1 = Nest(shape=(16, 10))
        i1, j1 = nest1.get_indices()

        @nest1.iteration_logic
        def _():
            C[i1, j1] *= B[i1, j1]

        schedule1 = nest1.create_schedule()

        # Create a fused schedule: the smaller iteration space (nest1) should
        # be automatically end-padded with no-ops
        schedule = fuse(schedule0, schedule1)
        f, i, j = schedule.get_indices()

        # computing the output block-by-block:
        #  first computing C[0:4, 0:4] += A[0:4, 0:4]
        #  then computing C[0:4, 0:4] *= B[0:4, 0:4]
        ii, jj = schedule.tile({
            i: 4,
            j: 4
        })
        schedule.reorder(i, j, f, ii, jj)

        # Emitted fused loop should look like:
        # for i in range(0, 16, 4):
        #   # run both kernels in the smaller iteration spaces
        #   # (tiled block)
        #   for j in range(0, 8, 4):
        #       for f in range(2):
        #           if f == 0:
        #               for ii in range(0, 4):
        #                   for jj in range(0, 4):
        #                       C[i+ii, j+jj] += A[i+ii, j+jj]
        #           if f == 1:
        #               for ii in range(0, 4):
        #                   for jj in range(0, 4):
        #                       C[i+ii, j+jj] *= B[i+ii, j+jj]
        #
        #   # run both kernels in the smaller iteration space
        #   # (boundary block for split)
        #   for j in range(8, 10): # range < split size
        #       for f in range(2):
        #           if f == 0:
        #               for ii in range(0, 4):
        #                   C[i+ii, j] += A[i+ii, j]
        #           if f == 1:
        #               for ii in range(0, 4):
        #                   C[i+ii, j] *= B[i+ii, j]
        #
        #   # run kernel with the larger iteration space
        #   # (boundary block for split)
        #   for j in range(10, 16): # range < split size
        #       for f in range(2):
        #           if f == 0:
        #               for ii in range(0, 4):
        #                   C[i+ii, j] += A[i+ii, j]

        A_test = np.random.random(A.shape).astype(np.float32)
        B_test = np.random.random(B.shape).astype(np.float32)
        C_test = np.random.random(C.shape).astype(np.float32)

        C_ref = C_test + A_test    # nest0
        C_ref[:, :B.shape[1]] = C_ref[:, :B.shape[1]] * B_test    # nest1

        correctness_check_values = {
            "pre": [A_test, B_test, C_test],
            "post": [A_test, B_test, C_ref]
        }
        self._verify_schedule(schedule, (A, B, C), "test_unequal_iteration_space_fusing_3", correctness_check_values)

    def test_concat_fusing_1(self) -> None:
        from accera import fuse, Nest

        A = Array(role=Array.Role.INPUT_OUTPUT, shape=(3, ))
        B = Array(role=Array.Role.INPUT_OUTPUT, shape=(7, ))

        n1 = Nest(A.shape)
        n2 = Nest(B.shape)

        n1_i = n1.get_indices()

        @n1.iteration_logic
        def _():
            A[n1_i] /= A[n1_i]

        n2_i = n2.get_indices()

        @n2.iteration_logic
        def _():
            B[n2_i] *= B[n2_i]

        fused = fuse([n.create_schedule() for n in [n1, n2]], partial=0)

        # Emitted fused loop should look like:
        # for f in range(3):
        #     if f == 0:
        #         for i in range(3):
        #             A[i] /= A[i]
        #     if f == 1:
        #         for i in range(7):
        #             B[i] *= B[i]

        A_test = np.random.random(A.shape).astype(np.float32)
        B_test = np.random.random(B.shape).astype(np.float32)

        A_ref = A_test / A_test
        B_ref = B_test * B_test

        correctness_check_values = {
            "pre": [A_test, B_test],
            "post": [A_ref, B_ref]
        }
        self._verify_schedule(fused, (A, B), "test_concat_fusing_1", correctness_check_values)

    @expectedFailure(FailedReason.BUG, "Concat fusing is broken")
    def test_concat_fusing_2(self) -> None:
        from accera import fuse, Nest

        A = Array(role=Array.Role.INPUT_OUTPUT, shape=(11, ))
        B = Array(role=Array.Role.INPUT_OUTPUT, shape=(7, ))
        C = Array(role=Array.Role.INPUT_OUTPUT, shape=(5, ))

        n1 = Nest(A.shape)
        n2 = Nest(B.shape)
        n3 = Nest(C.shape)

        n1_i = n1.get_indices()

        @n1.iteration_logic
        def _():
            A[n1_i] += A[n1_i]

        n2_i = n2.get_indices()

        @n2.iteration_logic
        def _():
            B[n2_i] *= B[n2_i]

        n3_i = n3.get_indices()

        @n3.iteration_logic
        def _():
            C[n3_i] /= C[n3_i]

        fused = fuse([n.create_schedule() for n in [n1, n2, n3]], partial=0)

        # Emitted fused loop should look like:
        # for f in range(3):
        #     if f == 0:
        #         for i in range(11):
        #           A[i}] += A[i}]
        #     if f == 1:
        #         for i in range(7):
        #           B[i}] *= B[i}]
        #     if f == 2:
        #         for i in range(5):
        #           C[i}] /= C[i}]

        A_test = np.random.random(A.shape).astype(np.float32)
        B_test = np.random.random(B.shape).astype(np.float32)
        C_test = np.random.random(C.shape).astype(np.float32)

        A_ref = A_test + A_test
        B_ref = B_test * B_test
        C_ref = C_test / C_test

        correctness_check_values = {
            "pre": [A_test, B_test, C_test],
            "post": [A_ref, B_ref, C_ref]
        }
        self._verify_schedule(fused, (A, B, C), "test_concat_fusing_2", correctness_check_values)

    def test_concat_fusing_3(self) -> None:
        from accera import fuse, Nest

        A = Array(role=Array.Role.INPUT_OUTPUT, shape=(3, 16))
        B = Array(role=Array.Role.INPUT_OUTPUT, shape=(7, 16))

        n1 = Nest(A.shape)
        n2 = Nest(B.shape)

        n1_i, n1_j = n1.get_indices()

        @n1.iteration_logic
        def _():
            A[n1_i, n1_j] /= A[n1_i, n1_j]

        n2_i, n2_j = n2.get_indices()

        @n2.iteration_logic
        def _():
            B[n2_i, n2_j] *= B[n2_i, n2_j]

        fused = fuse([n.create_schedule() for n in [n1, n2]], partial=0)

        # Emitted fused loop should look like:
        # for f in range(3):
        #     if f == 0:
        #         for i in range(3):
        #             for j in range(16):
        #                 A[i,j] /= A[i,j]
        #     if f == 1:
        #         for i in range(7):
        #             for j in range(16):
        #                 B[i,j] *= B[i,j]

        A_test = np.random.random(A.shape).astype(np.float32)
        B_test = np.random.random(B.shape).astype(np.float32)

        A_ref = A_test / A_test
        B_ref = B_test * B_test

        correctness_check_values = {
            "pre": [A_test, B_test],
            "post": [A_ref, B_ref]
        }
        self._verify_schedule(fused, (A, B), "test_concat_fusing_3", correctness_check_values)

    @expectedFailure(FailedReason.BUG, "Concat fusing is broken")
    def test_concat_fusing_4(self) -> None:
        from accera import fuse, Nest

        A = Array(role=Array.Role.INPUT_OUTPUT, shape=(11, 16))
        B = Array(role=Array.Role.INPUT_OUTPUT, shape=(7, 16))
        C = Array(role=Array.Role.INPUT_OUTPUT, shape=(5, 16))

        n1 = Nest(A.shape)
        n2 = Nest(B.shape)
        n3 = Nest(C.shape)

        n1_i, n1_j = n1.get_indices()

        @n1.iteration_logic
        def _():
            A[n1_i, n1_j] += A[n1_i, n1_j]

        n2_i, n2_j = n2.get_indices()

        @n2.iteration_logic
        def _():
            B[n2_i, n2_j] *= B[n2_i, n2_j]

        n3_i, n3_j = n3.get_indices()

        @n3.iteration_logic
        def _():
            C[n3_i, n3_j] /= C[n3_i, n3_j]

        fused = fuse([n.create_schedule() for n in [n1, n2, n3]], partial=0)

        # Emitted fused loop should look like:
        # for f in range(3):
        #     if f == 0:
        #         for i in range(11):
        #             for j in range(16):
        #                 A[i,j] += A[i,j]
        #     if f == 1:
        #         for i in range(7):
        #             for j in range(16):
        #                 B[i,j] *= B[i,j]
        #     if f == 2:
        #         for i in range(5):
        #             for j in range(16):
        #                 C[i,j] /= C[i,j]

        A_test = np.random.random(A.shape).astype(np.float32)
        B_test = np.random.random(B.shape).astype(np.float32)
        C_test = np.random.random(C.shape).astype(np.float32)

        A_ref = A_test + A_test
        B_ref = B_test * B_test
        C_ref = C_test / C_test

        correctness_check_values = {
            "pre": [A_test, B_test, C_test],
            "post": [A_ref, B_ref, C_ref]
        }
        self._verify_schedule(fused, (A, B, C), "test_concat_fusing_4", correctness_check_values)

    @unittest.skip("BUG: Compilation takes too long")
    def test_multi_concat_fusing_1(self) -> None:
        from accera import fuse, Nest

        A = Array(role=Array.Role.INPUT_OUTPUT, shape=(1024 + 13, ))
        B = Array(role=Array.Role.INPUT_OUTPUT, shape=(1024 + 11, ))
        C = Array(role=Array.Role.INPUT_OUTPUT, shape=(1024 + 7, ))
        D = Array(role=Array.Role.INPUT_OUTPUT, shape=(1024 + 3, ))

        # Create nest0 and schedule
        nest0 = Nest(A.shape)
        i0 = nest0.get_indices()

        @nest0.iteration_logic
        def _():
            A[i0] += A[i0]

        # Create nest1 and schedule1
        nest1 = Nest(B.shape)
        i1 = nest1.get_indices()

        @nest1.iteration_logic
        def _():
            B[i1] *= B[i1]

        # Create a fused schedule
        s0, s1 = [n.create_schedule() for n in [nest0, nest1]]
        s0.split(i0, 11)
        s1.split(i1, 5)
        fused1 = fuse([s0, s1], partial=0)

        nest2 = Nest(C.shape)
        i2 = nest2.get_indices()

        @nest2.iteration_logic
        def _():
            C[i2] *= C[i2]

        s2 = nest2.create_schedule()
        s2.split(i2, 13)
        fused2 = fuse([fused1, s2], partial=0)

        nest3 = Nest(D.shape)
        i3 = nest3.get_indices()

        @nest3.iteration_logic
        def _():
            D[i3] *= D[i3]

        s3 = nest3.create_schedule()
        s3.split(i3, 7)
        fused3 = fuse([fused2, s3], partial=0)

        A_test = np.random.random(A.shape).astype(np.float32)
        B_test = np.random.random(B.shape).astype(np.float32)
        C_test = np.random.random(C.shape).astype(np.float32)
        D_test = np.random.random(D.shape).astype(np.float32)
        correctness_check_values = {
            "pre": [A_test, B_test, C_test, D_test],
            "post": [A_test + A_test, B_test * B_test, C_test * C_test, D_test * D_test]
        }
        self._verify_schedule(fused3, (A, B, C, D), "test_multi_concat_fusing_1", correctness_check_values)


class DSLTest_05Targets(unittest.TestCase):
    def test_known_targets(self) -> None:
        intel_name = "Intel 6400"
        intel = Target(known_name=intel_name, num_threads=44)
        self.assertEqual(intel.name, intel_name)
        self.assertEqual(intel.num_threads, 44)    # override
        self.assertEqual(intel.vector_bytes, 32)    # default
        self.assertEqual(intel.vector_registers, 16)    # default
        self.assertEqual(intel.category, Target.Category.CPU)    # default

        pi3_name = "Raspberry Pi 3B"
        pi3 = Target(Target.Model.RASPBERRY_PI_3B, category=Target.Category.CPU, frequency_GHz=1.2)
        self.assertEqual(pi3.name, pi3_name)
        self.assertEqual(pi3.num_threads, 8)
        self.assertEqual(pi3.category, Target.Category.CPU)

    def test_custom_targets(self) -> None:
        my_target = Target(
            name="Custom processor",
            category=Target.Category.CPU,
            architecture="x86_64",
            family="Broadwell",
            extensions=["MMX", "SSE", "SSE2", "SSE3", "SSSE3", "SSE4", "SSE4.1", "SSE4.2", "AVX", "AVX2", "FMA3"],
            num_cores=22,
            num_threads=44,
            frequency_GHz=3.2,
            turbo_frequency_GHz=3.8,
            cache_sizes=[32, 256, 56320],
            cache_lines=[64, 64, 64]
        )
        self.assertEqual(my_target.name, "Custom processor")
        self.assertEqual(my_target.category, Target.Category.CPU)
        self.assertEqual(my_target.architecture, "x86_64")
        self.assertTrue("SSE3" in my_target.extensions)

    def test_gpu_targets(self) -> None:
        v100_name = "NVidia V100"
        v100 = Target(Target.Model.NVIDIA_V100, category=Target.Category.GPU)
        self.assertEqual(v100.name, v100_name)
        self.assertEqual(v100.category, Target.Category.GPU)
        self.assertEqual(v100.warp_size, 32)

        mi100 = Target(Target.Model.AMD_MI100)
        self.assertEqual(mi100.warp_size, 64)
        self.assertEqual(mi100.frequency_GHz, 1.502)

        a100 = Target(Target.Model.NVIDIA_A100)
        self.assertEqual(a100.warp_size, 32)


class DSLTest_06PlansCaching(unittest.TestCase):
    def _create_plan(self, shape: Tuple[int], type=ScalarType.float32) -> Tuple:
        M, N, S = shape

        A = Array(role=Array.Role.INPUT, element_type=type, shape=(M, S))
        B = Array(
            role=Array.Role.INPUT, element_type=type, shape=(S, N), layout=Array.Layout.LAST_MAJOR
        )    # use a different caching layout
        C = Array(role=Array.Role.INPUT_OUTPUT, element_type=type, shape=(M, N))

        nest = Nest(shape=(M, N, S))
        i, j, k = nest.get_indices()

        @nest.iteration_logic
        def _():
            C[i, j] += A[i, k] * B[k, j]

        plan = nest.create_plan()

        return plan, [A, B, C], [i, j, k]

    def _verify_plan(self, plan, args: Tuple[Array], package_name, correctness_check_values=None) -> None:
        # create a HAT package and add the function to it
        package = Package()
        function = package.add(plan, args, base_name="caching_test")
        output_dir = pathlib.Path(TEST_PACKAGE_DIR) / package_name

        # build the HAT package
        with verifiers.VerifyPackage(self, package_name, output_dir) as v:
            package.build(package_name, format=TEST_FORMAT, mode=TEST_MODE, output_dir=output_dir)
            if correctness_check_values:
                v.check_correctness(
                    function.name, before=correctness_check_values["pre"], after=correctness_check_values["post"]
                )

    def test_caching_by_level(self) -> None:
        plan, args, indices = self._create_plan((16, 10, 11))
        A, B, C = args
        _, j, _ = indices

        AA = plan.cache(A, level=2)
        self.assertEqual(AA.index, j)

        # input, different layout
        BB = plan.cache(B, level=2, layout=Array.Layout.FIRST_MAJOR)
        self.assertEqual(BB.index, j)

        self._verify_plan(plan, [A, B, C], "test_caching_by_level")

    def test_caching_by_index(self) -> None:
        plan, args, indices = self._create_plan((16, 10, 11))
        A, B, C = args
        _, j, _ = indices

        with self.assertRaises(ValueError):
            AA = plan.cache(A, index=j, level=1)

        AA = plan.cache(A, index=j)    # input
        self.assertEqual(AA.index, j)

        # input, different layout
        BB = plan.cache(B, index=j, layout=Array.Layout.FIRST_MAJOR)
        self.assertEqual(BB.index, j)

        CC = plan.cache(C, index=j)    # input/output
        self.assertEqual(CC.index, j)

        self._verify_plan(plan, [A, B, C], "test_caching_by_index")

    def test_caching_by_element_budget(self) -> None:
        plan, args, _ = self._create_plan((256, 10, 11))
        A, B, C = args

        AA = plan.cache(A, max_elements=1024)
        self.assertEqual(AA.index, None)
        self.assertEqual(AA.max_elements, 1024)

        self._verify_plan(plan, [A, B, C], "test_caching_by_element_budget")

    def test_thrifty_caching(self) -> None:
        plan, args, indices = self._create_plan((16, 10, 11))
        A, B, C = args
        _, j, k = indices

        # A is row-major, thrifty mode should skip caching
        AA = plan.cache(A, thrifty=True, index=j)
        self.assertIsNotNone(AA)

        # B is column-major, thrifty mode should cache
        BB = plan.cache(B, thrifty=True, index=k)
        self.assertIsNotNone(BB)

        self._verify_plan(plan, [A, B, C], "test_thrifty_caching")

    @expectedFailure(FailedReason.NOT_IN_PY, "Various target memory identifiers")
    def test_cache_mapping(self) -> None:
        A = Array(role=Array.Role.INPUT, shape=(1024, ))

        nest = Nest(shape=(64, ))
        i = nest.get_indices()

        @nest.iteration_logic
        def _():
            A[i] += 2

        v100 = Target(Target.Model.NVIDIA_V100, category=Target.Category.GPU, num_threads=16)
        plan = nest.create_plan(v100)

        plan.cache(i, type=v100.MemorySpace.SHARED)
        self._verify_plan(plan, [A], "test_cache_mapping")

    def test_cache_trigger_level(self) -> None:
        A = Array(role=Array.Role.INPUT, shape=(1024, 1024))
        B = Array(role=Array.Role.INPUT_OUTPUT, shape=(1024, 1024))

        nest = Nest(shape=(1024, 1024))
        i, j = nest.get_indices()

        @nest.iteration_logic
        def _():
            B[i, j] += A[i, j]

        schedule = nest.create_schedule()
        ii = schedule.split(i, 128)
        jj = schedule.split(j, 256)
        schedule.reorder(i, j, ii, jj)

        plan = schedule.create_plan()

        plan.cache(A, index=ii, trigger_index=j)

        self._verify_plan(plan, [A, B], "test_cache_trigger_level")

    def test_cache_trigger_level_matmul(self) -> None:
        M = 1024
        N = 1024
        S = 1024

        A = Array(role=Array.Role.INPUT, shape=(M, S))
        B = Array(role=Array.Role.INPUT, shape=(S, N))
        C = Array(role=Array.Role.INPUT_OUTPUT, shape=(M, N))

        nest = Nest(shape=(M, N, S))
        i, j, k = nest.get_indices()

        @nest.iteration_logic
        def _():
            C[i, j] += A[i, k] * B[k, j]

        schedule = nest.create_schedule()

        jj = schedule.split(j, 128)
        kk = schedule.split(k, 256)
        kkk = schedule.split(kk, 4)
        jjj = schedule.split(jj, 16)
        jjjj = schedule.split(jjj, 8)
        ii = schedule.split(i, 6)

        schedule.reorder(j, k, i, jj, kk, kkk, ii, jjj, jjjj)
        plan = schedule.create_plan()
        plan.cache(B, index=kkk, trigger_index=k, layout=Array.Layout.FIRST_MAJOR)

        A_test = np.random.random(A.shape).astype(np.float32)
        B_test = np.random.random(B.shape).astype(np.float32)
        C_test = np.random.random(C.shape).astype(np.float32)
        correctness_check_values = {
            "pre": [A_test, B_test, C_test],
            "post": [A_test, B_test, C_test + A_test @ B_test]
        }

        self._verify_plan(
            plan, [A, B, C], "test_cache_trigger_level_matmul", correctness_check_values=correctness_check_values
        )

    def test_hierachical_caching(self) -> None:
        M = 1024
        N = 1024
        S = 1024

        A = Array(role=Array.Role.INPUT, shape=(M, S))
        B = Array(role=Array.Role.INPUT, shape=(S, N))
        C = Array(role=Array.Role.INPUT_OUTPUT, shape=(M, N))

        nest = Nest(shape=(M, N, S))
        i, j, k = nest.get_indices()

        @nest.iteration_logic
        def _():
            C[i, j] += A[i, k] * B[k, j]

        schedule = nest.create_schedule()

        jj = schedule.split(j, 128)
        kk = schedule.split(k, 256)
        kkk = schedule.split(kk, 4)
        jjj = schedule.split(jj, 16)
        jjjj = schedule.split(jjj, 8)
        ii = schedule.split(i, 6)

        schedule.reorder(j, k, i, jj, kk, kkk, ii, jjj, jjjj)
        plan = schedule.create_plan()

        AA = plan.cache(A, level=5, trigger_level=7, layout=Array.Layout.FIRST_MAJOR)
        AAA = plan.cache(AA, level=3, trigger_level=5, layout=Array.Layout.LAST_MAJOR)
        BB = plan.cache(B, level=6, trigger_level=7, layout=Array.Layout.FIRST_MAJOR)
        BBB = plan.cache(BB, level=2, trigger_level=5, layout=Array.Layout.LAST_MAJOR)
        CC = plan.cache(C, level=8, layout=Array.Layout.FIRST_MAJOR)
        CCC = plan.cache(CC, level=6, layout=Array.Layout.LAST_MAJOR)

        A_test = np.random.random(A.shape).astype(np.float32)
        B_test = np.random.random(B.shape).astype(np.float32)
        C_test = np.random.random(C.shape).astype(np.float32)
        correctness_check_values = {
            "pre": [A_test, B_test, C_test],
            "post": [A_test, B_test, C_test + A_test @ B_test]
        }

        self._verify_plan(
            plan, [A, B, C], "test_hierarchical_caching", correctness_check_values=correctness_check_values
        )


class DSLTest_07PlansVectorizationParallelization(unittest.TestCase):
    def _verify_plan(self, plan, args: Tuple[int], package_name, correctness_check_values=None) -> None:
        package = Package()
        function = package.add(plan, args, base_name="vectorization_parallelization_test")

        output_dir = pathlib.Path(TEST_PACKAGE_DIR) / package_name
        with verifiers.VerifyPackage(self, package_name, output_dir) as v:
            package.build(package_name, format=TEST_FORMAT, mode=TEST_MODE, output_dir=output_dir)
            if correctness_check_values:
                v.check_correctness(
                    function.name, before=correctness_check_values["pre"], after=correctness_check_values["post"]
                )

    def test_unroll(self) -> None:
        from accera import Target, Nest

        A = Array(role=Array.Role.INPUT, shape=(3, 5))

        my_target = Target(category=Target.Category.CPU)

        nest = Nest(shape=(3, 5))
        i, j = nest.get_indices()

        @nest.iteration_logic
        def _():
            A[i, j] *= 2.0

        plan1 = nest.create_plan(my_target)
        plan1.unroll(index=j)
        self._verify_plan(plan1, [A], "test_unroll1")

        plan2 = nest.create_plan(my_target)
        plan2.unroll(index=i)
        self._verify_plan(plan2, [A], "test_unroll2")

    def test_vectorize(self) -> None:
        from accera import Target, Nest

        A = Array(role=Array.Role.INPUT, shape=(64, ))
        B = Array(role=Array.Role.INPUT, shape=(64, ))
        C = Array(role=Array.Role.INPUT_OUTPUT, shape=(64, ))

        my_target = Target(category=Target.Category.CPU, vector_bytes=16, vector_registers=2)

        nest = Nest(shape=(64, ))
        i = nest.get_indices()

        @nest.iteration_logic
        def _():
            C[i] = A[i] * B[i]

        plan = nest.create_plan(my_target)
        plan.vectorize(index=i)
        self._verify_plan(plan, [A, B, C], "test_vectorize")

    def test_kernelize(self) -> None:
        from accera import Target, Nest

        A = Array(role=Array.Role.INPUT, shape=(16, 11))
        B = Array(role=Array.Role.INPUT, shape=(11, 10))
        C = Array(role=Array.Role.INPUT_OUTPUT, shape=(16, 10))

        nest = Nest(shape=(16, 10, 11))
        i, j, k = nest.get_indices()

        @nest.iteration_logic
        def _():
            C[i, j] += A[i, k] * B[k, j]

        my_target = Target(category=Target.Category.CPU, vector_bytes=16, vector_registers=2)
        plan = nest.create_plan(my_target)

        # Shorthand for:
        # plan.unroll(i)
        # plan.unroll(j)
        # plan.vectorize(k)
        plan.kernelize(unroll_indices=(i, j), vectorize_indices=k)
        self._verify_plan(plan, [A, B, C], "test_kernelize")

    def test_kernelize_2(self) -> None:
        from accera import Target, Nest

        A = Array(role=Array.Role.INPUT, shape=(16, 16))
        B = Array(role=Array.Role.INPUT, shape=(16, 16))
        C = Array(role=Array.Role.INPUT_OUTPUT, shape=(16, 16))

        nest = Nest(shape=(16, 16, 16))
        i, j, k = nest.get_indices()

        @nest.iteration_logic
        def _():
            C[i, j] += A[i, k] * B[k, j]

        my_target = Target(category=Target.Category.CPU, vector_bytes=16, vector_registers=2)
        plan = nest.create_plan(my_target)

        # Shorthand for:
        # plan.unroll(i)
        # plan.vectorize(j)
        # plan.vectorize(k)
        plan.kernelize(unroll_indices=(i, ), vectorize_indices=(j, k))
        self._verify_plan(plan, [A, B, C], "test_kernelize_2")

    @expectedFailure(FailedReason.NOT_IN_PY, "pinning parallelization to CPU cores")
    def test_cpu_bind(self) -> None:
        A = Array(role=Array.Role.INPUT, shape=(16, 11))
        B = Array(role=Array.Role.INPUT, shape=(11, 10))
        C = Array(role=Array.Role.INPUT_OUTPUT, shape=(16, 10))

        nest = Nest(shape=(16, 10, 11))
        i, j, k = nest.get_indices()

        @nest.iteration_logic
        def _():
            C[i, j] += A[i, k] * B[k, j]

        target = Target("HOST", num_threads=16)
        plan = nest.create_plan(target)

        plan.parallelize(indices=(i, j, k), pin=(target.cores[0], target.cores[1]))    # TODO: confirm syntax
        self._verify_plan(plan, [A, B, C], "test_cpu_bind")

    def test_gpu_bind(self) -> None:
        M = 128
        N = 256
        K = 256
        A = Array(role=Array.Role.INPUT, shape=(M, K))
        B = Array(role=Array.Role.INPUT, shape=(K, N))
        C = Array(role=Array.Role.INPUT_OUTPUT, shape=(M, N))

        nest = Nest(shape=(M, N, K))
        i, j, k = nest.get_indices()

        @nest.iteration_logic
        def _():
            C[i, j] += A[i, k] * B[k, j]

        v100 = Target(Target.Model.NVIDIA_V100, category=Target.Category.GPU)
        plan = nest.create_plan(v100)

        plan.bind(mapping={
            i: v100.GridUnit.BLOCK_X,
            j: v100.GridUnit.THREAD_X,
            k: v100.GridUnit.THREAD_Y
        })

        test_name = "test_gpu_bind"
        package = Package()
        function = package.add(plan, args=(A, B, C), base_name=test_name)

        output_dir = pathlib.Path(TEST_PACKAGE_DIR) / test_name

        with verifiers.VerifyPackage(self, test_name, output_dir, file_list=[f"{test_name}.cu",
                                                                             f"{test_name}.hat"]) as v:
            package.build(
                name=test_name,
                format=Package.Format.MLIR | Package.Format.CUDA | Package.Format.HAT_PACKAGE,
                mode=Package.Mode.RELEASE,    # Package.Mode.DEBUG,
                output_dir=output_dir
            )

    def test_scheduling_strategies(self) -> None:
        A = Array(role=Array.Role.INPUT, shape=(256, 1024))
        B = Array(role=Array.Role.INPUT, shape=(1024, 512))
        C = Array(role=Array.Role.INPUT_OUTPUT, shape=(256, 512))

        nest = Nest(shape=(256, 512, 1024))
        i, j, k = nest.get_indices()

        @nest.iteration_logic
        def _():
            C[i, j] += A[i, k] * B[k, j]

        target = Target("HOST", num_threads=16)

        # disable correctness checking on windows because the
        # install location of libomp.dll is non-standard as of now
        if sys.platform.startswith('win'):
            correctness_check_values = None
        else:
            A_test = np.random.random(A.shape).astype(np.float32)
            B_test = np.random.random(B.shape).astype(np.float32)
            C_test = np.random.random(C.shape).astype(np.float32)
            correctness_check_values = {
                "pre": [A_test, B_test, C_test],
                "post": [A_test, B_test, C_test + A_test @ B_test]
            }

        schedule = nest.create_schedule()
        ii = schedule.split(i, A.shape[0] // min(4, target.num_threads))
        # set the index (k) that cannot be parallelized as innermost
        schedule.reorder(i, ii, j, k)

        for policy in ["static", "dynamic"]:
            plan = schedule.create_plan(target)

            # wrong order
            with self.assertRaises(ValueError):
                plan.parallelize(indices=(k, ii), policy=policy)

            # non-contiguous
            with self.assertRaises(ValueError):
                plan.parallelize(indices=(i, j), policy=policy)

            # non-collapsed
            plan.parallelize(indices=i, policy=policy)
            self._verify_plan(plan, [A, B, C], f"test_parallelize_i_{policy}", correctness_check_values)

            # parallelizing middle index
            plan_ii = schedule.create_plan(target)
            plan_ii.parallelize(indices=ii, policy=policy)
            self._verify_plan(plan_ii, [A, B, C], f"test_parallelize_ii_{policy}", correctness_check_values)

            # partial collapsed
            plan_partial = schedule.create_plan(target)
            plan_partial.parallelize(indices=(i, ii, j), policy=policy)
            self._verify_plan(plan_partial, [A, B, C], f"test_parallelize_i_ii_j_{policy}", correctness_check_values)

            # partial collapsed inner indices
            plan_partial_inner = schedule.create_plan(target)
            plan_partial_inner.parallelize(indices=(ii, j), policy=policy)
            self._verify_plan(
                plan_partial_inner, [A, B, C], f"test_parallelize_ii_j_{policy}", correctness_check_values
            )

            # fully collapsed will result in correctness issues because parallelizing k can stomp on the C matrix
            # where multiple threads try to update C[i, j] for different values of k


class DSLTest_08DeferredLayout(unittest.TestCase):
    def _verify_package(self, plan, args, package_name, correctness_check_values) -> None:
        package = Package()
        function = package.add(plan, args, base_name="deferred_layout")

        output_dir = pathlib.Path(TEST_PACKAGE_DIR) / package_name
        with verifiers.VerifyPackage(self, package_name, output_dir) as v:
            package.build(package_name, format=TEST_FORMAT, mode=TEST_MODE, output_dir=output_dir)
            if correctness_check_values:
                v.check_correctness(
                    function.name, before=correctness_check_values["pre"], after=correctness_check_values["post"]
                )

    def test_deferred_layout_predefined(self) -> None:
        matrix = np.random.rand(128, 128).astype(np.float32)
        B_test = np.random.random(matrix.shape).astype(np.float32)

        for layout in [Array.Layout.FIRST_MAJOR, Array.Layout.LAST_MAJOR]:
            A = Array(role=Array.Role.CONST, data=matrix, layout=Array.Layout.DEFERRED)
            B = Array(role=Array.Role.INPUT_OUTPUT, element_type=ScalarType.float32, shape=matrix.shape)

            nest = Nest(shape=matrix.shape)
            i, j = nest.get_indices()

            @nest.iteration_logic
            def _():
                B[i, j] += A[i, j]

            # create a cache for the constant array
            plan1 = nest.create_plan()
            AA = plan1.cache(A, i, layout=layout)    # , thrifty=True) # TODO

            # create another cache, using a different plan, for testing purposes
            plan2 = nest.create_plan()
            BB = plan2.cache(B, i)

            with self.assertRaises(ValueError):
                B.deferred_layout(cache=BB)    # non-const array

            with self.assertRaises(ValueError):
                A.deferred_layout(cache=BB)    # wrong cache

            # update the constant array's layout based on the cache
            A.deferred_layout(cache=AA)
            self.assertEqual(A.layout, AA.layout)

            with self.assertRaises(ValueError):
                A.deferred_layout(cache=AA)    # duplicate

            package_name = f"test_deferred_layout_predefined_{layout}".replace(".", "_")    # sanitize path name

            self._verify_package(plan1, (B, ), package_name, {
                "pre": [B_test],
                "post": [B_test + matrix]
            })

    def test_deferred_layout_coefficients(self) -> None:
        matrix = np.random.rand(128, 128).astype(np.float32)
        B_test = np.random.random(matrix.shape).astype(np.float32)

        for layout in [(128, 1), (1, 128)]:
            A = Array(role=Array.Role.CONST, data=matrix, layout=Array.Layout.DEFERRED)
            B = Array(role=Array.Role.INPUT_OUTPUT, element_type=ScalarType.float32, shape=matrix.shape)

            nest = Nest(shape=matrix.shape)
            i, j = nest.get_indices()

            @nest.iteration_logic
            def _():
                B[i, j] += A[i, j]

            plan = nest.create_plan()
            AA = plan.cache(A, i, layout=layout)    # , thrifty=True) # TODO

            A.deferred_layout(cache=AA)
            self.assertEqual(A.layout, AA.layout)

            package_name = f"test_deferred_layout_coefficients_{'_'.join(map(str, layout))}"
            self._verify_package(plan, (B, ), package_name, {
                "pre": [B_test],
                "post": [B_test + matrix]
            })


class DSLTest_09Parameters(unittest.TestCase):
    def test_parameterization_1(self) -> None:
        from accera import create_parameters, Nest

        P0, P1, P2, P3 = create_parameters(4)

        A = Array(role=Array.Role.INPUT, element_type=ScalarType.float32, shape=(P0, P2))
        B = Array(role=Array.Role.INPUT, element_type=ScalarType.float32, shape=(P2, P1))
        C = Array(role=Array.Role.INPUT_OUTPUT, element_type=ScalarType.float32, shape=(P0, P1))

        nest = Nest(shape=(P0, P1, P2))
        i, j, k = nest.get_indices()

        @nest.iteration_logic
        def _():
            C[i, j] += P3 * A[i, k] * B[k, j]

        package = Package()
        package_name = "test_parameterization_1"

        # Use the templated nest to add two different functions to the package
        package.add(
            nest, args=(A, B, C), parameters={
                P0: 16,
                P1: 16,
                P2: 16,
                P3: 1.0
            }, base_name="matmul_16_16_16_1"
        )
        package.add(
            nest, args=(A, B, C), parameters={
                P0: 32,
                P1: 32,
                P2: 32,
                P3: 2.0
            }, base_name="matmul_32_32_32_2"
        )

        P4, P5 = create_parameters(2)

        # Create a parameterized schedule
        schedule = nest.create_schedule()
        ii = schedule.split(i, size=P4)

        P6 = create_parameters(1)
        schedule.reorder(order=P6)

        # Create a parameterized plan
        plan = schedule.create_plan()
        plan.cache(A, level=P5)

        # Add another function to the package
        package.add(
            plan,
            args=(A, B, C),
            parameters={
                P0: 16,
                P1: 16,
                P2: 16,
                P3: 1.0,
                P4: 4,
                P5: 2,
                P6: (j, k, i, ii)
            },
            base_name="alternative_matmul_16_16_16"
        )

        with verifiers.VerifyPackage(self, package_name, TEST_PACKAGE_DIR):
            package.build(name=package_name, format=TEST_FORMAT, mode=TEST_MODE, output_dir=TEST_PACKAGE_DIR)

    def test_parameterization_2(self) -> None:
        from accera import create_parameters, Nest

        P0, P1, P2, P3 = create_parameters(4)

        A = Array(role=Array.Role.INPUT, element_type=ScalarType.float32, shape=(P0, P2))
        B = Array(role=Array.Role.INPUT, element_type=ScalarType.float32, shape=(P2, P1))
        C = Array(role=Array.Role.INPUT_OUTPUT, element_type=ScalarType.float32, shape=(P0, P1))

        nest = Nest(shape=(P0, P1, P2))
        i, j, k = nest.get_indices()

        @nest.iteration_logic
        def _():
            C[i, j] += P3 * A[i, k] * B[k, j]

        package = Package()
        package_name = "test_parameterization_2"

        P4, P5 = create_parameters(2)

        # Create a parameterized schedule
        schedule = nest.create_schedule()
        ii = schedule.split(i, size=P4)
        jj = schedule.split(j, size=P4)
        kk = schedule.split(k, size=P4)

        P6, P7, P8 = create_parameters(3)
        schedule.reorder(order=P6)

        # Create a parameterized plan
        plan = schedule.create_plan()
        plan.cache(A, level=P5)
        plan.kernelize(unroll_indices=P7, vectorize_indices=P8)

        # Add another function to the package
        package.add(
            plan,
            args=(A, B, C),
            parameters={
                P0: 256,
                P1: 256,
                P2: 256,
                P3: 1.0,
                P4: 4,
                P5: 2,
                P6: (j, k, i, ii, jj, kk),
                P7: (ii, jj),
                P8: kk
            },
            base_name="matmul_256_256_256"
        )

        with verifiers.VerifyPackage(self, package_name, TEST_PACKAGE_DIR):
            package.build(name=package_name, format=TEST_FORMAT, mode=TEST_MODE, output_dir=TEST_PACKAGE_DIR)

    def test_parameterization_3(self) -> None:
        from accera import create_parameters, Nest

        for N in [10, 224]:    # input sizes
            for K in [1, 3, 5]:    # filter sizes
                M = N - K + 1    # output size

                P = create_parameters(1)

                A = Array(role=Array.Role.INPUT, shape=(N, ))
                B = Array(role=Array.Role.INPUT, shape=(K, ))
                C = Array(role=Array.Role.INPUT_OUTPUT, shape=(M, ))

                nest = Nest(shape=(M, K))
                i, j = nest.get_indices()

                @nest.iteration_logic
                def _():
                    C[i] += A[i + j] * B[j]

                schedule = nest.create_schedule()

                A_test = np.random.random(A.shape).astype(np.float32)
                B_test = np.random.random(B.shape).astype(np.float32)
                C_test = np.random.random(C.shape).astype(np.float32)
                correctness_check_values = {
                    "pre": [A_test, B_test, C_test],
                    "post": [A_test, B_test, C_test + np.convolve(np.flip(B_test), A_test, "valid")]
                }

                # Skew dimension i with respect to dimension j with unroll loop not smaller than P.
                schedule.skew(i, j, P)

                # create a HAT package and add the function to it
                package = Package()
                package_name = f"test_parameterization_3_skew_i_j_{N}_{K}"
                function = package.add(
                    schedule, args=(A, B, C), parameters={P: 0}, base_name=f"schedule_test_skew_i_j_{N}_{K}"
                )
                output_dir = pathlib.Path(TEST_PACKAGE_DIR) / package_name

                # build the HAT package
                with verifiers.VerifyPackage(self, package_name, output_dir) as v:
                    package.build(package_name, format=TEST_FORMAT, mode=TEST_MODE, output_dir=output_dir)
                    if correctness_check_values:
                        v.check_correctness(
                            function.name,
                            before=correctness_check_values["pre"],
                            after=correctness_check_values["post"]
                        )

    def test_parameterization_4(self) -> None:
        from accera import create_parameters, Nest

        M = 16
        N = 10
        S = 11
        type = ScalarType.float32
        A = Array(role=Array.Role.INPUT, element_type=type, shape=(M, S))
        B = Array(role=Array.Role.INPUT, element_type=type, shape=(S, N))
        C = Array(role=Array.Role.INPUT_OUTPUT, element_type=type, shape=(M, N))

        nest = Nest(shape=(M, N, S))

        i, j, k = nest.get_indices()

        @nest.iteration_logic
        def _():
            C[i, j] += A[i, k] * B[k, j]

        schedule = nest.create_schedule()

        P1, P2, P3, P4, P5, P6 = create_parameters(6)

        # Adds empty elements to the beginning of dimension i, j, k
        schedule.pad(i, P1)
        ii = schedule.split(i, P2)    # (2 + 16) // 3
        # should result in these loops for i, ii
        #  i: [2, 3:3), ii: [0, 1:1)  <-- partial (front padding)
        #  i: [3: 18:3), ii: [0, 3:1) <-- full

        schedule.pad(j, P3)
        jj = schedule.split(j, P4)    # (3 + 10) // 3
        # should result in these loops for j, jj
        #  j: [3, 12:3), jj: [0, 3:3)   <-- full (front padding == split size)
        #  j: [12, 13:3), jj: [0, 1:1)  <-- partial (automatic back padding)

        schedule.pad(k, P5)
        kk = schedule.split(k, P6)    # (11 + 11) // 4
        # should result in these loops for k, kk
        #  k: [11, 12:1), kk: [0, 1: 1) <-- partial
        #  k: [12, 20:4), kk: [0: 4: 1) <-- full
        #  k: [20, 22:4), kk: [0: 2: 1) <-- partial (automatic back padding)

        schedule.reorder(i, ii, k, j, jj, kk)

        A_test = np.random.random(A.shape).astype(np.float32)
        B_test = np.random.random(B.shape).astype(np.float32)
        C_test = np.random.random(C.shape).astype(np.float32)
        correctness_check_values = {
            "pre": [A_test, B_test, C_test],
            "post": [A_test, B_test, C_test + A_test @ B_test]
        }

        # create a HAT package and add the function to it
        package = Package()
        package_name = "test_parameterization_4_pad"
        function = package.add(
            schedule,
            args=(A, B, C),
            parameters={
                P1: 2,
                P2: 3,
                P3: 3,
                P4: 3,
                P5: 11,
                P6: 4
            },
            base_name="schedule_test_pad_parameter"
        )
        output_dir = pathlib.Path(TEST_PACKAGE_DIR) / package_name

        # build the HAT package
        with verifiers.VerifyPackage(self, package_name, output_dir) as v:
            package.build(package_name, format=TEST_FORMAT, mode=TEST_MODE, output_dir=output_dir)
            if correctness_check_values:
                v.check_correctness(
                    function.name, before=correctness_check_values["pre"], after=correctness_check_values["post"]
                )

    def test_parameterization_5(self) -> None:
        from accera import create_parameters

        A = Array(role=Array.Role.INPUT, shape=(256, 1024))
        B = Array(role=Array.Role.INPUT, shape=(1024, 512))
        C = Array(role=Array.Role.INPUT_OUTPUT, shape=(256, 512))

        nest = Nest(shape=(256, 512, 1024))
        i, j, k = nest.get_indices()

        @nest.iteration_logic
        def _():
            C[i, j] += A[i, k] * B[k, j]

        target = Target("HOST", num_threads=16)
        assert target.architecture == Target.Architecture.HOST

        # disable correctness checking on windows because the
        # install location of libomp.dll is non-standard as of now
        if sys.platform.startswith('win'):
            correctness_check_values = None
        else:
            A_test = np.random.random(A.shape).astype(np.float32)
            B_test = np.random.random(B.shape).astype(np.float32)
            C_test = np.random.random(C.shape).astype(np.float32)
            correctness_check_values = {
                "pre": [A_test, B_test, C_test],
                "post": [A_test, B_test, C_test + A_test @ B_test]
            }

        schedule = nest.create_schedule()
        ii = schedule.split(i, A.shape[0] // target.num_threads)
        # set the index (k) that cannot be parallelized as innermost
        schedule.reorder(i, ii, j, k)

        P1, P2, P3, P4, P5, P6, P7, P8 = create_parameters(8)

        for policy in ["static", "dynamic"]:
            plan = schedule.create_plan(target)

            # non-collapsed
            plan.parallelize(indices=P1, policy=P2)

            package_name = f"parameterized_test_parallelize_i_{policy}"
            package = Package()
            function = package.add(
                plan,
                args=[A, B, C],
                parameters={
                    P1: i,
                    P2: policy
                },
                base_name=f"parameterized_vectorization_parallelization_test_i_{policy}"
            )

            output_dir = pathlib.Path(TEST_PACKAGE_DIR) / package_name
            with verifiers.VerifyPackage(self, package_name, output_dir) as v:
                package.build(package_name, format=TEST_FORMAT, mode=TEST_MODE, output_dir=output_dir)
                if correctness_check_values:
                    v.check_correctness(
                        function.name, before=correctness_check_values["pre"], after=correctness_check_values["post"]
                    )

            # parallelizing middle index
            plan_ii = schedule.create_plan(target)
            plan_ii.parallelize(indices=P3, policy=P4)

            package_name = f"parameterized_test_parallelize_ii_{policy}"
            package_ii = Package()
            function_ii = package_ii.add(
                plan_ii,
                args=[A, B, C],
                parameters={
                    P3: ii,
                    P4: policy
                },
                base_name=f"parameterized_vectorization_parallelization_test_ii_{policy}"
            )

            output_dir = pathlib.Path(TEST_PACKAGE_DIR) / package_name
            with verifiers.VerifyPackage(self, package_name, output_dir) as v:
                package_ii.build(package_name, format=TEST_FORMAT, mode=TEST_MODE, output_dir=output_dir)
            if correctness_check_values:
                v.check_correctness(
                    function_ii.name, before=correctness_check_values["pre"], after=correctness_check_values["post"]
                )

            # partial collapsed
            plan_partial = schedule.create_plan(target)
            plan_partial.parallelize(indices=P5, policy=P6)

            package_name = f"parameterized_test_parallelize_i_ii_j_{policy}"
            package_partial = Package()
            function_partial = package_partial.add(
                plan_ii,
                args=[A, B, C],
                parameters={
                    P5: (i, ii, j),
                    P6: policy
                },
                base_name=f"parameterized_vectorization_parallelization_test_i_ii_j_{policy}"
            )

            output_dir = pathlib.Path(TEST_PACKAGE_DIR) / package_name
            with verifiers.VerifyPackage(self, package_name, output_dir) as v:
                package_partial.build(package_name, format=TEST_FORMAT, mode=TEST_MODE, output_dir=output_dir)
                if correctness_check_values:
                    v.check_correctness(
                        function_partial.name,
                        before=correctness_check_values["pre"],
                        after=correctness_check_values["post"]
                    )

            # partial collapsed inner indices
            plan_partial_inner = schedule.create_plan(target)
            plan_partial_inner.parallelize(indices=P7, policy=P8)

            package_name = f"parameterized_test_parallelize_ii_j_{policy}"
            package_partial_inner = Package()
            function_partial_inner = package_partial_inner.add(
                plan,
                args=[A, B, C],
                parameters={
                    P7: (ii, j),
                    P8: policy
                },
                base_name=f"parameterized_vectorization_parallelization_test_ii_j_{policy}"
            )

            output_dir = pathlib.Path(TEST_PACKAGE_DIR) / package_name
            with verifiers.VerifyPackage(self, package_name, output_dir) as v:
                package_partial_inner.build(package_name, format=TEST_FORMAT, mode=TEST_MODE, output_dir=output_dir)
                if correctness_check_values:
                    v.check_correctness(
                        function_partial_inner.name,
                        before=correctness_check_values["pre"],
                        after=correctness_check_values["post"]
                    )

    def test_parameterization_grid(self) -> None:
        from accera import create_parameters, create_parameter_grid, Nest, Schedule

        P0, P1, P2, P3, P4 = create_parameters(5)

        A = Array(role=Array.Role.INPUT, element_type=ScalarType.float32, shape=(P0, P2))
        B = Array(role=Array.Role.INPUT, element_type=ScalarType.float32, shape=(P2, P1))
        C = Array(role=Array.Role.INPUT_OUTPUT, element_type=ScalarType.float32, shape=(P0, P1))

        nest = Nest(shape=(P0, P1, P2))
        i, j, k = nest.get_indices()

        @nest.iteration_logic
        def _():
            C[i, j] += P3 * A[i, k] * B[k, j]

        sched: Schedule = nest.create_schedule()
        sched.split(j, P4)

        package = Package()
        package_name = "test_parameter_grid_generation"

        parameter_grid = {
            P0: [8, 16],
            P1: [16, 32],
            P2: [16],
            P3: [1.0, 2.0],
            P4: [3, 5, 7]
        }

        parameters = create_parameter_grid(parameter_grid)
        package.add(sched, args=(A, B, C), base_name="matmul", parameters=parameters)

        with verifiers.VerifyPackage(self, package_name, TEST_PACKAGE_DIR):
            package.build(name=package_name, format=TEST_FORMAT, mode=TEST_MODE, output_dir=TEST_PACKAGE_DIR)

    def test_fusion_parameterization_1(self) -> None:
        from accera import create_parameters, Nest, fuse

        A = Array(role=Array.Role.INPUT, element_type=float, shape=(32, ))
        B = Array(role=Array.Role.INPUT_OUTPUT, element_type=float, shape=(32, ))
        C = Array(role=Array.Role.INPUT_OUTPUT, element_type=float, shape=(1, ))

        n0 = Nest([32, 32])
        i0, j0 = n0.get_indices()

        @n0.iteration_logic
        def _():
            B[i0] += A[i0] * A[j0]

        s0 = n0.create_schedule()

        n0_up = Nest(n0.get_shape())
        i0_up, j0_up = n0_up.get_indices()

        @n0_up.iteration_logic
        def _():
            B[i0_up] += A[i0_up] * A[j0_up]

        s0_up = n0_up.create_schedule()

        n1 = Nest([32])
        i1 = n1.get_indices()

        @n1.iteration_logic
        def _():
            C[0] += B[i1]

        s1 = n1.create_schedule()

        P0 = create_parameters(1)
        jj0 = s0.split(j0, P0)

        jj0_up = s0_up.split(j0_up, 16)

        fs = fuse((s0, s1), partial=1)
        f, i, j, jj = fs.get_indices()
        fs.reorder(i, f, j, jj)

        fs_up = fuse((s0_up, s1), partial=1)
        f_up, i_up, j_up, jj_up = fs_up.get_indices()
        fs_up.reorder(i_up, f_up, j_up, jj_up)

        package = Package()
        package_name = "test_fusion_parameterization_1"

        package.add(fs_up, args=(A, B, C), base_name="fuse_unparameterized_1")

        package.add(
            fs, args=(A, B, C), parameters={
                P0: 16,
            }, base_name="fuse_1"
        )
        package.add(
            fs, args=(A, B, C), parameters={
                P0: 3,
            }, base_name="fuse_2"
        )
        package.add(
            fs, args=(A, B, C), parameters=[{
                P0: 5
            }, {
                P0: 7
            }], base_name="fuse_3"
        )

        with verifiers.VerifyPackage(self, package_name, TEST_PACKAGE_DIR):
            package.build(name=package_name, format=TEST_FORMAT, mode=TEST_MODE, output_dir=TEST_PACKAGE_DIR)

    def test_fusion_parameterization_2(self) -> None:
        """
        Goes through a different codepath from the above tests because the
        schedules are emitted directly prior to the fused schedule, which
        matters because the fused schedule has references to the schedule
        """
        from accera import create_parameters, Nest, fuse

        A = Array(role=Array.Role.INPUT, element_type=float, shape=(32, ))
        B = Array(role=Array.Role.INPUT_OUTPUT, element_type=float, shape=(32, ))
        C = Array(role=Array.Role.INPUT_OUTPUT, element_type=float, shape=(1, ))

        n0 = Nest([32, 32])
        i0, j0 = n0.get_indices()

        @n0.iteration_logic
        def _():
            B[i0] += A[i0] * A[j0]

        s0 = n0.create_schedule()

        n1 = Nest([32])
        i1 = n1.get_indices()

        @n1.iteration_logic
        def _():
            C[0] += B[i1]

        s1 = n1.create_schedule()

        P0 = create_parameters(1)
        jj0 = s0.split(j0, P0)

        fs = fuse((s0, s1), partial=1)

        package = Package()
        package_name = "test_fusion_parameterization_2"

        package.add(
            s0, args=(A, B), parameters={P0: 16}, base_name="s0_1"
        )
        package.add(
            s0, args=(A, B), parameters={P0: 32}, base_name="s0_2"
        )
        package.add(
            s1, args=(C, B), parameters={P0: 16}, base_name="s1_1"
        )
        package.add(
            fs, args=(A, B, C), parameters={
                P0: 16,
            }, base_name="fuse_1"
        )
        package.add(
            fs, args=(A, B, C), parameters={
                P0: 32,
            }, base_name="fuse_2"
        )

        with verifiers.VerifyPackage(self, package_name, TEST_PACKAGE_DIR):
            package.build(name=package_name, format=TEST_FORMAT, mode=TEST_MODE, output_dir=TEST_PACKAGE_DIR)

    def test_fusion_parameterization_3(self) -> None:
        from accera import create_parameters, Nest, fuse

        A = Array(role=Array.Role.INPUT, element_type=float, shape=(32, ))
        B = Array(role=Array.Role.INPUT_OUTPUT, element_type=float, shape=(32, ))
        C = Array(role=Array.Role.INPUT_OUTPUT, element_type=float, shape=(1, ))

        n0 = Nest([32, 32])
        i0, j0 = n0.get_indices()

        @n0.iteration_logic
        def _():
            B[i0] += A[i0] * A[j0]

        s0 = n0.create_schedule()

        n1 = Nest([32])
        i1 = n1.get_indices()

        @n1.iteration_logic
        def _():
            C[0] += B[i1]

        s1 = n1.create_schedule()

        P0, P1 = create_parameters(2)
        jj0 = s0.split(j0, P0)

        fs = fuse((s0, s1), partial=1)
        f, i, j, jj = fs.get_indices()
        ii = fs.split(i, P1)
        fs.reorder(f, i, j, ii, jj)

        package = Package()
        package_name = "test_fusion_parameterization_3"

        package.add(
            fs, args=(A, B, C), parameters={
                P0: 16,
                P1: 8
            }, base_name="fuse_1"
        )
        package.add(
            fs, args=(A, B, C), parameters={
                P0: 32,
                P1: 4,
            }, base_name="fuse_2"
        )

        with verifiers.VerifyPackage(self, package_name, TEST_PACKAGE_DIR):
            package.build(name=package_name, format=TEST_FORMAT, mode=TEST_MODE, output_dir=TEST_PACKAGE_DIR)

    def test_fusion_parameterization_4(self) -> None:
        from accera import create_parameters, Nest, fuse, create_parameter_grid

        A = Array(role=Array.Role.INPUT, element_type=float, shape=(128, ))
        B = Array(role=Array.Role.INPUT_OUTPUT, element_type=float, shape=(128, ))
        C = Array(role=Array.Role.INPUT_OUTPUT, element_type=float, shape=(1, ))

        n0 = Nest([128, 128])
        i0, j0 = n0.get_indices()

        @n0.iteration_logic
        def _():
            B[i0] += A[i0] * A[j0]

        s0 = n0.create_schedule()

        n1 = Nest([128])
        i1 = n1.get_indices()

        @n1.iteration_logic
        def _():
            C[0] += B[i1]

        s1 = n1.create_schedule()

        P0, P1, P2 = create_parameters(3)
        jj0 = s0.split(j0, P0)

        fs = fuse((s0, s1), partial=1)
        f, i, j, jj = fs.get_indices()
        ii = fs.split(i, P1)
        fs.reorder(i, f, j, ii, jj)
        jjj = fs.split(jj, P2)

        package = Package()
        package_name = "test_fusion_parameterization_4"

        # Expected loop structure
        # P0 = 16
        # P1 = 8
        # P2 = 4
        # for i in range(128, step=P1):
        #     for f in range(2):
        #         if f == 0:
        #             for j in range(128, step=P0):
        #                 for ii in range(P1):
        #                     for jj in range(P0, step=P2):
        #                         for jjj in range(P2):
        #                             ...
        #         if f == 1:
        #             for ii in range(P1):
        #                 ...
        package.add(
            fs, args=(A, B, C), parameters={
                P0: 16,
                P1: 8,
                P2: 4
            }, base_name="fuse_1"
        )

        # Expected loop structure
        # P0 = 32
        # P1 = 4
        # P2 = 8
        # for i in range(128, step=P1):
        #     for f in range(2):
        #         if f == 0:
        #             for j in range(128, step=P0):
        #                 for ii in range(P1):
        #                     for jj in range(P0, step=P2):
        #                         for jjj in range(P2):
        #                             ...
        #         if f == 1:
        #             for ii in range(P1):
        #                 ...
        package.add(
            fs, args=(A, B, C), parameters={
                P0: 32,
                P1: 4,
                P2: 8
            }, base_name="fuse_2"
        )
        package.add(
            fs,
            args=(A, B, C),
            parameters=create_parameter_grid({
                P0: [64, 8],
                P1: [12, 16, 20],
                P2: [2, 10]
            }),
            base_name="fuse_grid"
        )

        with verifiers.VerifyPackage(self, package_name, TEST_PACKAGE_DIR):
            package.build(name=package_name, format=TEST_FORMAT, mode=TEST_MODE, output_dir=TEST_PACKAGE_DIR)

    def test_parameterization_auxiliary_data(self) -> None:
        from accera import create_parameters, create_parameter_grid, Nest, Schedule
        from hatlib import HATPackage

        P0, P1, P2, P3, P4 = create_parameters(5)

        A = Array(role=Array.Role.INPUT, element_type=ScalarType.float32, shape=(P0, P2))
        B = Array(role=Array.Role.INPUT, element_type=ScalarType.float32, shape=(P2, P1))
        C = Array(role=Array.Role.INPUT_OUTPUT, element_type=ScalarType.float32, shape=(P0, P1))

        nest = Nest(shape=(P0, P1, P2))
        i, j, k = nest.get_indices()

        @nest.iteration_logic
        def _():
            C[i, j] += P3 * A[i, k] * B[k, j]

        sched: Schedule = nest.create_schedule()
        sched.split(j, P4)

        package = Package()
        package_name = "test_parameterization_auxiliary_data"

        parameter_grid = {
            P0: [8, 16],
            P1: [16, 32],
            P2: [16],
            P3: [1.0, 2.0],
            P4: [3, 5, 7]
        }

        parameters = create_parameter_grid(parameter_grid)
        package.add(sched, args=(A, B, C), base_name="matmul", parameters=parameters)

        with verifiers.VerifyPackage(self, package_name, TEST_PACKAGE_DIR):
            package.build(name=package_name, format=TEST_FORMAT, mode=TEST_MODE, output_dir=TEST_PACKAGE_DIR)

        hat_package = HATPackage(pathlib.Path(TEST_PACKAGE_DIR) / f"{package_name}.hat")
        functions = [fn for fn in hat_package.get_functions()]
        for function in functions:
            data_point = function.auxiliary['accera']['parameters']
            if data_point:
                self.assertIn(int(data_point["P0"]), [8, 16])
                self.assertIn(int(data_point["P1"]), [16, 32])
                self.assertIn(int(data_point["P2"]), [16])
                self.assertIn(float(data_point["P3"]), [1.0, 2.0])
                self.assertIn(int(data_point["P4"]), [3, 5, 7])


class DSLTest_10Packages(unittest.TestCase):
    def _create_plan(self, target=Target.HOST) -> Function:
        A = Array(role=Array.Role.INPUT_OUTPUT, shape=(64, ))

        nest = Nest(shape=(64, ))
        i = nest.get_indices()

        @nest.iteration_logic
        def _():
            A[i] += 2.

        plan = nest.create_plan(target)
        return plan, A

    def test_HAT_packages(self) -> None:
        from accera import Target

        pi3 = Target(Target.Model.RASPBERRY_PI_3B, category=Target.Category.CPU)
        plan, A = self._create_plan(pi3)

        package = Package()
        package_name = "MyPackage"
        package.add(plan, args=(A, ), base_name="func1")
        package.add(plan, args=(A, ), base_name="func2")

        with verifiers.VerifyPackage(self, package_name, TEST_PACKAGE_DIR):
            package.build(
                package_name,
                format=Package.Format.HAT_STATIC,
                mode=TEST_MODE,
                output_dir=TEST_PACKAGE_DIR,
                platform=Package.Platform.RASPBIAN
            )

    def test_MLIR_packages(self) -> None:
        plan, A = self._create_plan()

        package = Package()
        package_name = "MyPackage"
        package.add(plan, args=(A, ), base_name="func1")
        package.add(plan, args=(A, ), base_name="func2")

        with verifiers.VerifyPackage(self, package_name, TEST_PACKAGE_DIR):
            package.build(package_name, format=Package.Format.MLIR_STATIC, output_dir=TEST_PACKAGE_DIR)

    def test_default_output_dir(self) -> None:
        plan, A = self._create_plan()

        package = Package()
        package_name = "MyPackage"
        package.add(plan, args=(A, ), base_name="func1")
        package.add(plan, args=(A, ), base_name="func2")

        with verifiers.VerifyPackage(self, package_name):
            package.build(package_name, format=TEST_FORMAT, mode=TEST_MODE)

    def test_debug_mode_1(self) -> None:
        M = N = K = 16
        A = Array(role=Array.Role.INPUT, element_type=ScalarType.float32, shape=(M, K))
        B = Array(role=Array.Role.INPUT, element_type=ScalarType.float32, shape=(K, N))
        C = Array(role=Array.Role.INPUT_OUTPUT, element_type=ScalarType.float32, shape=(M, N))

        nest = Nest(shape=(M, N, K))
        i, j, k = nest.get_indices()

        @nest.iteration_logic
        def _():
            C[i, j] += A[i, k] * B[k, j]

        schedule = nest.create_schedule()

        ii = schedule.split(i, 4)
        schedule.reorder(i, k, j, ii)
        plan = schedule.create_plan()
        plan.unroll(ii)

        package = Package()
        package_name = "MyDebugPackage"
        function = package.add(plan, args=(A, B, C), base_name="func1")
        output_dir = pathlib.Path(TEST_PACKAGE_DIR) / package_name

        with verifiers.VerifyPackage(self, package_name, output_dir) as v:
            package.build(
                package_name, format=TEST_FORMAT, output_dir=output_dir, mode=Package.Mode.DEBUG, tolerance=1e-5
            )

            A_test = np.random.random(A.shape).astype(np.float32)
            B_test = np.random.random(B.shape).astype(np.float32)
            C_test = np.random.random(C.shape).astype(np.float32)

            v.check_correctness(
                function.name, before=[A_test, B_test, C_test], after=[A_test, B_test, C_test + A_test @ B_test]
            )

    def test_debug_mode_2(self) -> None:
        M = N = K = 16
        A = Array(role=Array.Role.INPUT, element_type=ScalarType.float32, shape=(M, K))
        B = Array(role=Array.Role.INPUT, element_type=ScalarType.float32, shape=(K, N))
        C = Array(role=Array.Role.INPUT_OUTPUT, element_type=ScalarType.float32, shape=(M, N))

        nest = Nest(shape=(M, N, K))
        i, j, k = nest.get_indices()

        @nest.iteration_logic
        def _():
            C[i, j] += A[i, k] * B[k, j]

        schedule = nest.create_schedule()

        ii = schedule.split(i, 4)
        schedule.reorder(i, k, j, ii)
        plan = schedule.create_plan()
        plan.unroll(ii)
        # deliberately introduce a correctness issue
        plan.parallelize(indices=k)

        package = Package()
        package_name = "MyDebugPackageIncorrect"
        function = package.add(plan, args=(A, B, C), base_name="func1")
        output_dir = pathlib.Path(TEST_PACKAGE_DIR) / package_name

        with verifiers.VerifyPackage(self, package_name, output_dir) as v:
            package.build(
                package_name, format=TEST_FORMAT, output_dir=output_dir, mode=Package.Mode.DEBUG, tolerance=1e-5
            )

            A_test = np.random.random(A.shape).astype(np.float32)
            B_test = np.random.random(B.shape).astype(np.float32)
            C_test = np.random.random(C.shape).astype(np.float32)

            try:
                v.check_correctness(
                    function.name, before=[A_test, B_test, C_test], after=[A_test, B_test, C_test + A_test @ B_test]
                )
            except Exception as e:
                print(e)

    def test_debug_mode_fusion_1(self) -> None:
        from accera import fuse

        M = N = 16
        A = Array(role=Array.Role.INPUT, element_type=ScalarType.float32, shape=(M, N))
        B = Array(role=Array.Role.INPUT, element_type=ScalarType.float32, shape=(M, N))
        C = Array(role=Array.Role.INPUT_OUTPUT, element_type=ScalarType.float32, shape=(M, N))

        nest0 = Nest(shape=(M, N))
        i0, j0 = nest0.get_indices()

        @nest0.iteration_logic
        def _():
            C[i0, j0] += A[i0, j0]

        schedule0 = nest0.create_schedule()

        nest1 = Nest(shape=(M, N))
        i1, j1 = nest1.get_indices()

        @nest1.iteration_logic
        def _():
            C[i1, j1] *= B[i1, j1]

        schedule1 = nest1.create_schedule()

        schedule = fuse(schedule0, schedule1, partial=1)
        f, i, j0, j1 = schedule.get_indices()
        ii = schedule.split(i, 2)
        schedule.reorder(i, ii, f, j0, j1)

        package = Package()
        package_name = "MyFusionDebugPackage"
        function = package.add(schedule, args=(A, B, C), base_name="fusion_func1")
        output_dir = pathlib.Path(TEST_PACKAGE_DIR) / package_name

        with verifiers.VerifyPackage(self, package_name, output_dir) as v:
            package.build(
                package_name, format=TEST_FORMAT, output_dir=output_dir, mode=Package.Mode.DEBUG, tolerance=1e-5
            )

            A_test = np.random.random(A.shape).astype(np.float32)
            B_test = np.random.random(B.shape).astype(np.float32)
            C_test = np.random.random(C.shape).astype(np.float32)

            v.check_correctness(
                function.name, before=[A_test, B_test, C_test], after=[A_test, B_test, (C_test + A_test) * B_test]
            )

    def test_debug_mode_fusion_2(self) -> None:
        from accera import fuse

        M = N = 16
        A = Array(role=Array.Role.INPUT, element_type=ScalarType.float32, shape=(M, N))
        B = Array(role=Array.Role.INPUT, element_type=ScalarType.float32, shape=(M, N))
        C = Array(role=Array.Role.INPUT_OUTPUT, element_type=ScalarType.float32, shape=(M, N))

        nest0 = Nest(shape=(M, N))
        i0, j0 = nest0.get_indices()

        @nest0.iteration_logic
        def _():
            C[i0, j0] += A[i0, j0]

        schedule0 = nest0.create_schedule()

        nest1 = Nest(shape=(M, N))
        i1, j1 = nest1.get_indices()

        @nest1.iteration_logic
        def _():
            C[i1, j1] *= B[i1, j1]

        schedule1 = nest1.create_schedule()

        # Reorder schedule1 before fusing
        schedule1.reorder(j1, i1)
        # Fuse schedule0 with the reordered schedule1
        schedule = fuse(schedule0, schedule1)
        f, a, b = schedule.get_indices()

        # Deliberately break logical equivalence
        # before: C[1,0] = C[1,0] * B[1,0] + A[1,0]
        # after: C[1,0] = (C[1,0] + A[1,0]) * B[1,0]
        schedule.reorder(a, b, f)

        package = Package()
        package_name = "MyFusionDebugPackageIncorrect"
        function = package.add(schedule, args=(A, B, C), base_name="fusion_func1")
        output_dir = pathlib.Path(TEST_PACKAGE_DIR) / package_name

        with verifiers.VerifyPackage(self, package_name, output_dir) as v:
            package.build(
                package_name, format=TEST_FORMAT, output_dir=output_dir, mode=Package.Mode.DEBUG, tolerance=1e-5
            )

            A_test = np.random.random(A.shape).astype(np.float32)
            B_test = np.random.random(B.shape).astype(np.float32)
            C_test = np.random.random(C.shape).astype(np.float32)

            try:
                v.check_correctness(
                    function.name, before=[A_test, B_test, C_test], after=[A_test, B_test, (C_test + A_test) * B_test]
                )
            except Exception as e:
                print(e)

    def test_debug_mode_fusion_cascading_1(self) -> None:
        from accera import fuse

        M = N = 16
        A = Array(role=Array.Role.INPUT, element_type=ScalarType.float32, shape=(M, N))
        B = Array(role=Array.Role.INPUT, element_type=ScalarType.float32, shape=(M, N))
        C = Array(role=Array.Role.INPUT_OUTPUT, element_type=ScalarType.float32, shape=(M, N))

        nest0 = Nest(shape=(M, N))
        i0, j0 = nest0.get_indices()

        @nest0.iteration_logic
        def _():
            C[i0, j0] += A[i0, j0]

        schedule0 = nest0.create_schedule()

        nest1 = Nest(shape=(M, N))
        i1, j1 = nest1.get_indices()

        @nest1.iteration_logic
        def _():
            C[i1, j1] *= B[i1, j1]

        schedule1 = nest1.create_schedule()

        schedule_f1 = fuse(schedule0, schedule1)
        f, i, j = schedule_f1.get_indices()
        schedule_f1.reorder(i, j, f)

        nest2 = Nest(shape=(M, N))
        i2, j2 = nest2.get_indices()

        @nest2.iteration_logic
        def _():
            C[i2, j2] -= 1.0

        schedule2 = nest2.create_schedule()

        # set the fused schedule first in the fusing order
        schedule_f2 = fuse(schedule_f1, schedule2, partial=2)

        package = Package()
        package_name = "MyFusionDebugPackageCascade1"
        function = package.add(schedule_f2, args=(A, B, C), base_name="fusion_func1")
        output_dir = pathlib.Path(TEST_PACKAGE_DIR) / package_name

        with verifiers.VerifyPackage(self, package_name, output_dir) as v:
            package.build(
                package_name, format=TEST_FORMAT, output_dir=output_dir, mode=Package.Mode.DEBUG, tolerance=1e-5
            )

            A_test = np.random.random(A.shape).astype(np.float32)
            B_test = np.random.random(B.shape).astype(np.float32)
            C_test = np.random.random(C.shape).astype(np.float32)

            v.check_correctness(
                function.name,
                before=[A_test, B_test, C_test],
                after=[A_test, B_test, (C_test + A_test) * B_test - 1.0]
            )

    def test_debug_mode_fusion_cascading_2(self) -> None:
        from accera import fuse

        M = N = 16
        A = Array(role=Array.Role.INPUT, element_type=ScalarType.float32, shape=(M, N))
        B = Array(role=Array.Role.INPUT, element_type=ScalarType.float32, shape=(M, N))
        C = Array(role=Array.Role.INPUT_OUTPUT, element_type=ScalarType.float32, shape=(M, N))

        nest0 = Nest(shape=(M, N))
        i0, j0 = nest0.get_indices()

        @nest0.iteration_logic
        def _():
            C[i0, j0] += A[i0, j0]

        schedule0 = nest0.create_schedule()

        nest1 = Nest(shape=(M, N))
        i1, j1 = nest1.get_indices()

        @nest1.iteration_logic
        def _():
            C[i1, j1] *= B[i1, j1]

        schedule1 = nest1.create_schedule()

        schedule_f1 = fuse(schedule0, schedule1)
        f, i, j = schedule_f1.get_indices()
        schedule_f1.reorder(i, j, f)

        nest2 = Nest(shape=(M, N))
        i2, j2 = nest2.get_indices()

        @nest2.iteration_logic
        def _():
            C[i2, j2] -= 1.0

        schedule2 = nest2.create_schedule()

        # set an unfused schedule first in the fusing order
        schedule_f2 = fuse(schedule2, schedule_f1, partial=2)

        package = Package()
        package_name = "MyFusionDebugPackageCascade2"
        function = package.add(schedule_f2, args=(A, B, C), base_name="fusion_func1")
        output_dir = pathlib.Path(TEST_PACKAGE_DIR) / package_name

        with verifiers.VerifyPackage(self, package_name, output_dir) as v:
            package.build(
                package_name, format=TEST_FORMAT, output_dir=output_dir, mode=Package.Mode.DEBUG, tolerance=1e-5
            )

            A_test = np.random.random(A.shape).astype(np.float32)
            B_test = np.random.random(B.shape).astype(np.float32)
            C_test = np.random.random(C.shape).astype(np.float32)

            v.check_correctness(
                function.name,
                before=[A_test, B_test, C_test],
                after=[A_test, B_test, (C_test - 1.0 + A_test) * B_test]
            )

    def test_add_description(self) -> None:
        from hatlib import HATFile

        plan, A, = self._create_plan()

        package = Package()
        package_name = "MyPackage"
        package.add(plan, args=(A, ), base_name="func1")
        package.add(plan, args=(A, ), base_name="func2")

        description1 = {
            "Dependencies": ["numpy", "onnx", "scipy"],
            "Documentation": "https://docs.readthedocs.io.",
            "SHA": "0bb913ce84afa28127ea3fd2a9995e219dad322a"
        }

        package.add_description(
            other=description1, version="1.0", author="Microsoft Research", license="https://mit-license.org"
        )

        description2 = {
            "Documentation": "",    # clearing a value
            "SHA": None,    # removing a value
            "Release Notes": "https://stackoverflow.com"    # adding an entry
        }

        package.add_description(other=description2)
        package.add_description(version="2.0")

        with verifiers.VerifyPackage(self, package_name, TEST_PACKAGE_DIR):
            package.build(package_name, format=TEST_FORMAT, mode=TEST_MODE, output_dir=TEST_PACKAGE_DIR)

        hat_file = HATFile.Deserialize(pathlib.Path(TEST_PACKAGE_DIR) / f"{package_name}.hat")
        hat_description = hat_file.description.auxiliary
        self.assertEqual(hat_description["Dependencies"], description1["Dependencies"])
        self.assertEqual(hat_description["Documentation"], description2["Documentation"])
        self.assertNotIn("SHA", hat_description)
        self.assertEqual(hat_description["Release Notes"], description2["Release Notes"])
        self.assertEqual(hat_file.description.version, "2.0")
        self.assertEqual(hat_file.description.author, "Microsoft Research")
        self.assertEqual(hat_file.description.license_url, "https://mit-license.org")


if __name__ == '__main__':
    unittest.main(verbosity=10)
