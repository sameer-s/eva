# coding=utf-8
# Copyright 2018-2022 EVA
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import os
import unittest
from test.util import (  # file_remove,
    create_dummy_4d_batches,
    create_dummy_batches,
    create_sample_video,
    create_table,
    file_remove,
    get_logical_query_plan,
    load_inbuilt_udfs,
)

import numpy as np
import pandas as pd
import pytest

from eva.binder.binder_utils import BinderError
from eva.catalog.catalog_manager import CatalogManager
from eva.configuration.constants import EVA_ROOT_DIR
from eva.models.storage.batch import Batch
from eva.readers.opencv_reader import OpenCVReader
from eva.server.command_handler import execute_query_fetch_all

NUM_FRAMES = 10


@pytest.mark.notparallel
class SelectExecutorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        CatalogManager().reset()
        video_file_path = create_sample_video(NUM_FRAMES)
        load_query = f"LOAD VIDEO '{video_file_path}' INTO MyVideo;"
        execute_query_fetch_all(load_query)
        ua_detrac = f"{EVA_ROOT_DIR}/data/ua_detrac/ua_detrac.mp4"
        load_query = f"LOAD VIDEO '{ua_detrac}' INTO DETRAC;"
        execute_query_fetch_all(load_query)
        load_inbuilt_udfs()
        cls.table1 = create_table("table1", 100, 3)
        cls.table2 = create_table("table2", 500, 3)
        cls.table3 = create_table("table3", 1000, 3)

    @classmethod
    def tearDownClass(cls):
        file_remove(f"dummy_{os.environ['PYTEST_XDIST_WORKER']}.avi")
        drop_query = """DROP TABLE table1;"""
        execute_query_fetch_all(drop_query)
        drop_query = """DROP TABLE table2;"""
        execute_query_fetch_all(drop_query)
        drop_query = """DROP TABLE table3;"""
        execute_query_fetch_all(drop_query)
        execute_query_fetch_all("DROP TABLE IF EXISTS MyVideo;")

    def test_sort_on_nonprojected_column(self):
        """This tests doing an order by on a column
        that is not projected. The orderby_executor currently
        catches the KeyError, passes, and returns the untouched
        data
        """
        select_query = "SELECT data FROM MyVideo ORDER BY id;"
        actual_batch = execute_query_fetch_all(select_query)

        select_query = "SELECT data FROM MyVideo"
        expected_batch = execute_query_fetch_all(select_query)

        self.assertEqual(len(actual_batch), len(expected_batch))

    def test_should_load_and_sort_in_table(self):
        select_query = "SELECT data, id FROM MyVideo ORDER BY id;"
        actual_batch = execute_query_fetch_all(select_query)
        expected_rows = [
            {
                "myvideo.id": i,
                "myvideo.data": np.array(
                    np.ones((2, 2, 3)) * float(i + 1) * 25, dtype=np.uint8
                ),
            }
            for i in range(NUM_FRAMES)
        ]
        expected_batch = Batch(frames=pd.DataFrame(expected_rows))
        self.assertEqual(actual_batch, expected_batch)

        select_query = "SELECT data, id FROM MyVideo ORDER BY id DESC;"
        actual_batch = execute_query_fetch_all(select_query)
        expected_batch.reverse()
        self.assertEqual(actual_batch, expected_batch)

    def test_should_load_and_select_in_table(self):
        select_query = "SELECT id FROM MyVideo;"
        actual_batch = execute_query_fetch_all(select_query)
        actual_batch.sort()
        expected_rows = [{"myvideo.id": i} for i in range(NUM_FRAMES)]
        expected_batch = Batch(frames=pd.DataFrame(expected_rows))
        self.assertEqual(actual_batch, expected_batch)

        select_query = "SELECT * FROM MyVideo;"
        actual_batch = execute_query_fetch_all(select_query)
        actual_batch.sort()
        expected_batch = list(create_dummy_batches())
        self.assertEqual([actual_batch], expected_batch)

    def test_should_select_star_in_table(self):
        select_query = "SELECT * FROM MyVideo;"
        actual_batch = execute_query_fetch_all(select_query)
        actual_batch.sort()
        expected_batch = list(create_dummy_batches())[0]
        self.assertEqual(actual_batch, expected_batch)

        select_query = "SELECT * FROM MyVideo WHERE id = 5;"
        actual_batch = execute_query_fetch_all(select_query)
        expected_batch = list(create_dummy_batches(filters=[5]))[0]
        self.assertEqual(actual_batch, expected_batch)

    def test_should_select_star_in_nested_query(self):
        select_query = """SELECT * FROM (SELECT * FROM MyVideo) AS T;"""
        actual_batch = execute_query_fetch_all(select_query)
        actual_batch.sort()
        expected_batch = list(create_dummy_batches())[0]
        expected_batch.modify_column_alias("T")
        self.assertEqual(actual_batch, expected_batch)

        select_query = """SELECT * FROM (SELECT id FROM MyVideo) AS T;"""
        actual_batch = execute_query_fetch_all(select_query)
        actual_batch.sort()
        expected_rows = [{"T.id": i} for i in range(NUM_FRAMES)]
        expected_batch = Batch(frames=pd.DataFrame(expected_rows))
        self.assertEqual(actual_batch, expected_batch)

    @unittest.skip("Not supported in current version")
    def test_select_star_in_lateral_join(self):
        select_query = """SELECT * FROM MyVideo JOIN LATERAL
                          YoloV5(data);"""
        actual_batch = execute_query_fetch_all(select_query)
        self.assertEqual(actual_batch.frames.columns, ["myvideo.id"])

    def test_should_load_and_select_real_video_in_table(self):
        query = """LOAD VIDEO 'data/mnist/mnist.mp4'
                   INTO MNIST;"""
        execute_query_fetch_all(query)

        select_query = "SELECT id, data FROM MNIST;"
        actual_batch = execute_query_fetch_all(select_query)
        actual_batch.sort("mnist.id")
        video_reader = OpenCVReader("data/mnist/mnist.mp4")
        expected_batch = Batch(frames=pd.DataFrame())
        for batch in video_reader.read():
            batch.frames["name"] = "mnist.mp4"
            expected_batch += batch
        expected_batch.modify_column_alias("mnist")
        expected_batch = expected_batch.project(["mnist.id", "mnist.data"])
        self.assertEqual(actual_batch, expected_batch)

    def test_select_and_where_video_in_table(self):
        select_query = "SELECT * FROM MyVideo WHERE id = 5;"
        actual_batch = execute_query_fetch_all(select_query)
        expected_batch = list(create_dummy_batches(filters=[5]))[0]
        self.assertEqual(actual_batch, expected_batch)

        select_query = "SELECT data FROM MyVideo WHERE id = 5;"
        actual_batch = execute_query_fetch_all(select_query)
        expected_rows = [
            {
                "myvideo.data": np.array(
                    np.ones((2, 2, 3)) * float(5 + 1) * 25, dtype=np.uint8
                )
            }
        ]
        expected_batch = Batch(frames=pd.DataFrame(expected_rows))
        self.assertEqual(actual_batch, expected_batch)

        select_query = "SELECT id, data FROM MyVideo WHERE id >= 2;"
        actual_batch = execute_query_fetch_all(select_query)
        actual_batch.sort()
        expected_batch = list(create_dummy_batches(filters=range(2, NUM_FRAMES)))[0]
        self.assertEqual(
            actual_batch,
            expected_batch.project(["myvideo.id", "myvideo.data"]),
        )

        select_query = "SELECT * FROM MyVideo WHERE id >= 2 AND id < 5;"
        actual_batch = execute_query_fetch_all(select_query)
        actual_batch.sort()
        expected_batch = list(create_dummy_batches(filters=range(2, 5)))[0]

        self.assertEqual(actual_batch, expected_batch)

    def test_nested_select_video_in_table(self):
        nested_select_query = """SELECT * FROM
            (SELECT * FROM MyVideo WHERE id >= 2 AND id < 5) AS T
            WHERE id >= 3;"""
        actual_batch = execute_query_fetch_all(nested_select_query)
        actual_batch.sort()
        expected_batch = list(create_dummy_batches(filters=range(3, 5)))[0]
        expected_batch.modify_column_alias("T")
        self.assertEqual(actual_batch, expected_batch)

        nested_select_query = """SELECT * FROM
            (SELECT * FROM MyVideo WHERE id >= 2 AND id < 5) AS T
            WHERE id >= 3;"""
        actual_batch = execute_query_fetch_all(nested_select_query)
        actual_batch.sort("T.id")
        expected_batch = list(create_dummy_batches(filters=range(3, 5)))[0]
        expected_batch.modify_column_alias("T")
        self.assertEqual(actual_batch, expected_batch)

    def test_select_and_union_video_in_table(self):
        select_query = """SELECT * FROM MyVideo WHERE id < 3
            UNION ALL SELECT * FROM MyVideo WHERE id > 7;"""
        actual_batch = execute_query_fetch_all(select_query)
        actual_batch.sort("myvideo.id")
        expected_batch = list(
            create_dummy_batches(
                filters=[i for i in range(NUM_FRAMES) if i < 3 or i > 7]
            )
        )[0]
        self.assertEqual(actual_batch, expected_batch)

        select_query = """SELECT * FROM MyVideo WHERE id < 2
            UNION ALL SELECT * FROM MyVideo WHERE id > 4 AND id < 6
            UNION ALL SELECT * FROM MyVideo WHERE id > 7;"""
        actual_batch = execute_query_fetch_all(select_query)
        actual_batch.sort("myvideo.id")
        expected_batch = list(
            create_dummy_batches(
                filters=[i for i in range(NUM_FRAMES) if i < 2 or i == 5 or i > 7]
            )
        )[0]
        self.assertEqual(actual_batch, expected_batch)

    def test_select_and_limit(self):
        select_query = "SELECT * FROM MyVideo ORDER BY id LIMIT 5;"
        actual_batch = execute_query_fetch_all(select_query)
        actual_batch.sort()
        expected_batch = list(create_dummy_batches(num_frames=10, batch_size=5))

        self.assertEqual(len(actual_batch), len(expected_batch[0]))
        self.assertEqual(actual_batch, expected_batch[0])

    def test_select_and_aggregate(self):
        simple_aggregate_query = "SELECT COUNT(*), AVG(id) FROM MyVideo;"
        actual_batch = execute_query_fetch_all(simple_aggregate_query)

        self.assertEqual(actual_batch.frames.iat[0, 0], 10)
        self.assertEqual(actual_batch.frames.iat[0, 1], 4.5)

    def test_select_and_sample(self):
        select_query = "SELECT id FROM MyVideo SAMPLE 7 ORDER BY id;"
        actual_batch = execute_query_fetch_all(select_query)
        actual_batch.sort()

        expected_batch = list(create_dummy_batches(filters=range(0, NUM_FRAMES, 7)))
        expected_batch[0] = expected_batch[0].project(["myvideo.id"])

        self.assertEqual(len(actual_batch), len(expected_batch[0]))
        self.assertEqual(actual_batch, expected_batch[0])

    def test_select_and_iframe_sample(self):
        select_query = "SELECT id FROM MyVideo SAMPLE IFRAMES 7 ORDER BY id;"
        actual_batch = execute_query_fetch_all(select_query)
        actual_batch.sort()

        expected_batch = list(create_dummy_batches(filters=range(0, NUM_FRAMES, 7)))
        expected_batch[0] = expected_batch[0].project(["myvideo.id"])

        self.assertEqual(len(actual_batch), len(expected_batch[0]))
        self.assertEqual(actual_batch, expected_batch[0])

    def test_select_and_iframe_sample_without_sampling_rate(self):
        select_query = "SELECT id FROM MyVideo SAMPLE IFRAMES ORDER BY id;"
        actual_batch = execute_query_fetch_all(select_query)
        actual_batch.sort()

        expected_batch = list(create_dummy_batches(filters=range(0, NUM_FRAMES, 1)))
        expected_batch[0] = expected_batch[0].project(["myvideo.id"])

        self.assertEqual(len(actual_batch), len(expected_batch[0]))
        self.assertEqual(actual_batch, expected_batch[0])

    def test_select_and_groupby_first(self):
        # groupby and orderby together not tested because groupby
        # only applies to video data which is already sorted
        segment_size = 3
        select_query = (
            "SELECT FIRST(id), SEGMENT(data) FROM MyVideo GROUP BY '{}f';".format(
                segment_size
            )
        )
        actual_batch = execute_query_fetch_all(select_query)
        actual_batch.sort()
        ids = np.arange(NUM_FRAMES)
        segments = [ids[i : i + segment_size] for i in range(0, len(ids), segment_size)]
        segments = [i for i in segments if len(i) == segment_size]
        expected_batch = list(create_dummy_4d_batches(filters=segments))[0]
        self.assertEqual(len(actual_batch), len(expected_batch))

        expected_batch.rename(
            columns={"myvideo.id": "FIRST.id", "myvideo.data": "SEGMENT.data"}
        )
        self.assertEqual(
            actual_batch,
            expected_batch.project(["FIRST.id", "SEGMENT.data"]),
        )

    def test_select_and_groupby_with_last(self):
        # groupby and orderby together not tested because groupby
        # only applies to video data which is already sorted
        segment_size = 3
        select_query = (
            "SELECT LAST(id), SEGMENT(data) FROM MyVideo GROUP BY '{}f';".format(
                segment_size
            )
        )
        actual_batch = execute_query_fetch_all(select_query)
        actual_batch.sort()
        ids = np.arange(NUM_FRAMES)
        segments = [ids[i : i + segment_size] for i in range(0, len(ids), segment_size)]
        segments = [i for i in segments if len(i) == segment_size]
        expected_batch = list(
            create_dummy_4d_batches(filters=segments, start_id=segment_size - 1)
        )[0]
        self.assertEqual(len(actual_batch), len(expected_batch))

        expected_batch.rename(
            columns={"myvideo.id": "LAST.id", "myvideo.data": "SEGMENT.data"}
        )
        self.assertEqual(
            actual_batch,
            expected_batch.project(["LAST.id", "SEGMENT.data"]),
        )

    def test_select_and_groupby_should_fail_with_incorrect_pattern(self):
        segment_size = "4a"
        select_query = (
            "SELECT FIRST(id), SEGMENT(data) FROM MyVideo GROUP BY '{}f';".format(
                segment_size
            )
        )
        self.assertRaises(BinderError, execute_query_fetch_all, select_query)

    def test_select_and_groupby_should_fail_with_seconds(self):
        segment_size = 4
        select_query = (
            "SELECT FIRST(id), SEGMENT(data) FROM MyVideo GROUP BY '{}s';".format(
                segment_size
            )
        )
        self.assertRaises(BinderError, execute_query_fetch_all, select_query)

    def test_select_and_groupby_should_fail_with_non_video_table(self):
        segment_size = 4
        select_query = "SELECT FIRST(a1) FROM table1 GROUP BY '{}f';".format(
            segment_size
        )
        self.assertRaises(BinderError, execute_query_fetch_all, select_query)

    def test_select_and_groupby_with_sample(self):
        # TODO ACTION: groupby and orderby together not tested because groupby
        # only applies to video data which is already sorted
        segment_size = 2
        sampling_rate = 2
        select_query = "SELECT FIRST(id), SEGMENT(data) FROM MyVideo SAMPLE {} GROUP BY '{}f';".format(
            sampling_rate, segment_size
        )
        actual_batch = execute_query_fetch_all(select_query)
        actual_batch.sort()
        ids = np.arange(0, NUM_FRAMES, sampling_rate)

        segments = [ids[i : i + segment_size] for i in range(0, len(ids), segment_size)]
        segments = [i for i in segments if len(i) == segment_size]
        expected_batch = list(create_dummy_4d_batches(filters=segments))[0]
        self.assertEqual(len(actual_batch), len(expected_batch))

        expected_batch.rename(
            columns={"myvideo.id": "FIRST.id", "myvideo.data": "SEGMENT.data"}
        )

        self.assertEqual(
            actual_batch,
            expected_batch.project(["FIRST.id", "SEGMENT.data"]),
        )

    def test_select_and_sample_with_predicate(self):
        select_query = "SELECT id FROM MyVideo SAMPLE 2 WHERE id > 5 ORDER BY id;"
        actual_batch = execute_query_fetch_all(select_query)
        expected_batch = list(create_dummy_batches(filters=range(6, NUM_FRAMES, 2)))
        self.assertEqual(actual_batch, expected_batch[0].project(["myvideo.id"]))

        select_query = "SELECT id FROM MyVideo SAMPLE 4 WHERE id > 2 ORDER BY id;"
        actual_batch = execute_query_fetch_all(select_query)
        expected_batch = list(create_dummy_batches(filters=range(4, NUM_FRAMES, 4)))
        self.assertEqual(actual_batch, expected_batch[0].project(["myvideo.id"]))

        select_query = (
            "SELECT id FROM MyVideo SAMPLE 2 WHERE id > 2 AND id < 8 ORDER BY id;"
        )
        actual_batch = execute_query_fetch_all(select_query)
        expected_batch = list(create_dummy_batches(filters=range(4, 8, 2)))
        self.assertEqual(actual_batch, expected_batch[0].project(["myvideo.id"]))

    @pytest.mark.torchtest
    def test_lateral_join(self):
        select_query = """SELECT id, a FROM DETRAC JOIN LATERAL
                        YoloV5(data) AS T(a,b,c) WHERE id < 5;"""
        actual_batch = execute_query_fetch_all(select_query)
        self.assertEqual(list(actual_batch.columns), ["detrac.id", "T.a"])
        self.assertEqual(len(actual_batch), 5)

    @pytest.mark.torchtest
    def test_lateral_join_with_multiple_projects(self):
        select_query = """SELECT id, T.labels FROM DETRAC JOIN LATERAL
                        YoloV5(data) AS T WHERE id < 5;"""
        actual_batch = execute_query_fetch_all(select_query)
        self.assertTrue(all(actual_batch.frames.columns == ["detrac.id", "T.labels"]))
        self.assertEqual(len(actual_batch), 5)

    def test_lateral_join_with_unnest(self):
        query = """SELECT id, label
                  FROM MyVideo JOIN LATERAL
                    UNNEST(DummyObjectDetector(data)) AS T(label)
                  WHERE id < 2 ORDER BY id;"""
        unnest_batch = execute_query_fetch_all(query)
        expected = Batch(
            pd.DataFrame(
                {
                    "myvideo.id": np.array([0, 1], dtype=np.intp),
                    "T.label": np.array(["person", "bicycle"]),
                }
            )
        )

        self.assertEqual(unnest_batch, expected)

        query = """SELECT id, label
                  FROM MyVideo JOIN LATERAL
                    UNNEST(DummyObjectDetector(data)) AS T
                  WHERE id < 2 ORDER BY id;"""
        unnest_batch = execute_query_fetch_all(query)
        expected = Batch(
            pd.DataFrame(
                {
                    "myvideo.id": np.array([0, 1], dtype=np.intp),
                    "T.label": np.array(["person", "bicycle"]),
                }
            )
        )

        self.assertEqual(unnest_batch, expected)

    def test_lateral_join_with_unnest_and_sample(self):
        query = """SELECT id, label
                  FROM MyVideo SAMPLE 2 JOIN LATERAL
                    UNNEST(DummyMultiObjectDetector(data).labels) AS T(label)
                  WHERE id < 10 ORDER BY id;"""
        unnest_batch = execute_query_fetch_all(query)
        expected = Batch(
            pd.DataFrame(
                {
                    "myvideo.id": np.array(
                        [0, 0, 2, 2, 4, 4, 6, 6, 8, 8], dtype=np.intp
                    ),
                    "T.label": np.array(
                        [
                            "person",
                            "person",
                            "car",
                            "car",
                            "bicycle",
                            "bicycle",
                            "person",
                            "person",
                            "car",
                            "car",
                        ]
                    ),
                }
            )
        )
        self.assertEqual(len(unnest_batch), 10)
        self.assertEqual(unnest_batch, expected)

    def test_lateral_join_with_unnest_on_subset_of_outputs(self):
        query = """SELECT id, label
                  FROM MyVideo JOIN LATERAL
                    UNNEST(DummyMultiObjectDetector(data).labels) AS T(label)
                  WHERE id < 2 ORDER BY id;"""
        unnest_batch = execute_query_fetch_all(query)
        expected = Batch(
            pd.DataFrame(
                {
                    "myvideo.id": np.array([0, 0, 1, 1], np.intp),
                    "T.label": np.array(["person", "person", "bicycle", "bicycle"]),
                }
            )
        )
        self.assertEqual(unnest_batch, expected)

    def test_should_raise_error_with_missing_alias_in_lateral_join(self):
        udf_name = "DummyMultiObjectDetector"
        query = """SELECT id, labels
                  FROM MyVideo JOIN LATERAL DummyMultiObjectDetector(data).labels;"""
        with self.assertRaises(SyntaxError) as cm:
            execute_query_fetch_all(query)
        self.assertEqual(
            str(cm.exception),
            f"TableValuedFunction {udf_name} should have alias.",
        )

        query = """SELECT id, labels
                  FROM MyVideo JOIN LATERAL
                    UNNEST(DummyMultiObjectDetector(data).labels);"""
        with self.assertRaises(SyntaxError) as cm:
            execute_query_fetch_all(query)
        self.assertEqual(
            str(cm.exception),
            f"TableValuedFunction {udf_name} should have alias.",
        )

        query = """SELECT id, labels
                  FROM MyVideo JOIN LATERAL DummyMultiObjectDetector(data);"""
        with self.assertRaises(SyntaxError) as cm:
            execute_query_fetch_all(query)
        self.assertEqual(
            str(cm.exception),
            f"TableValuedFunction {udf_name} should have alias.",
        )

    def test_should_raise_error_with_invalid_number_of_aliases(self):
        udf_name = "DummyMultiObjectDetector"
        query = """SELECT id, labels
                  FROM MyVideo JOIN LATERAL
                    DummyMultiObjectDetector(data).bboxes AS T;"""
        with self.assertRaises(BinderError) as cm:
            execute_query_fetch_all(query)
        self.assertEqual(
            str(cm.exception),
            f"Output bboxes does not exist for {udf_name}.",
        )

    def test_should_raise_error_with_invalid_output_lateral_join(self):
        query = """SELECT id, a
                  FROM MyVideo JOIN LATERAL
                    DummyMultiObjectDetector(data) AS T(a, b);
                """
        with self.assertRaises(AssertionError) as cm:
            execute_query_fetch_all(query)
        self.assertEqual(str(cm.exception), "Expected 1 output columns for T, got 2.")

    def test_hash_join_with_one_on(self):
        select_query = """SELECT * FROM table1 JOIN
                        table2 ON table1.a1 = table2.a1;"""
        actual_batch = execute_query_fetch_all(select_query)
        expected = pd.merge(
            self.table1,
            self.table2,
            left_on=["table1.a1"],
            right_on=["table2.a1"],
            how="inner",
        )
        if len(expected):
            expected_batch = Batch(expected)
            self.assertEqual(
                expected_batch.sort_orderby(["table1.a2"]),
                actual_batch.sort_orderby(["table1.a2"]),
            )

    def test_hash_join_with_multiple_on(self):
        select_query = """SELECT * FROM table1 JOIN
                        table1 AS table2 ON table1.a1 = table2.a1 AND
                        table1.a0 = table2.a0;"""
        actual_batch = execute_query_fetch_all(select_query)
        expected = pd.merge(
            self.table1,
            self.table1,
            left_on=["table1.a1", "table1.a0"],
            right_on=["table1.a1", "table1.a0"],
            how="inner",
        )
        if len(expected):
            expected_batch = Batch(expected)
            self.assertEqual(
                expected_batch.sort_orderby(["table1.a1"]),
                actual_batch.sort_orderby(["table1.a1"]),
            )

    def test_hash_join_with_multiple_tables(self):
        select_query = """SELECT * FROM table1 JOIN table2
                          ON table2.a0 = table1.a0 JOIN table3
                          ON table3.a1 = table1.a1 WHERE table1.a2 > 50;"""
        actual_batch = execute_query_fetch_all(select_query)
        tmp = pd.merge(
            self.table1,
            self.table2,
            left_on=["table1.a0"],
            right_on=["table2.a0"],
            how="inner",
        )
        expected = pd.merge(
            tmp,
            self.table3,
            left_on=["table1.a1"],
            right_on=["table3.a1"],
            how="inner",
        )
        expected = expected.where(expected["table1.a2"] > 50)
        if len(expected):
            expected_batch = Batch(expected)
            self.assertEqual(
                expected_batch.sort_orderby(["table1.a0"]),
                actual_batch.sort_orderby(["table1.a0"]),
            )

    def test_expression_tree_signature(self):
        plan = get_logical_query_plan(
            "SELECT DummyMultiObjectDetector(data).labels FROM MyVideo"
        )
        signature = plan.target_list[0].signature()
        self.assertEqual(signature, "DummyMultiObjectDetector(MyVideo.data)")
