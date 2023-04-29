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
import shutil
import unittest
from test.util import create_dummy_batches, prefix_worker_id

import pytest

from eva.catalog.catalog_type import ColumnType, NdArrayType, TableType
from eva.catalog.models.column_catalog import ColumnCatalogEntry
from eva.catalog.models.table_catalog import TableCatalogEntry
from eva.storage.sqlite_storage_engine import SQLStorageEngine
from eva.storage.transaction_manager import TransactionManager


class SQLStorageEngineTest(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.table = None

    def create_sample_table(self):
        table_info = TableCatalogEntry(
            prefix_worker_id("dataset"),
            prefix_worker_id("dataset"),
            table_type=TableType.VIDEO_DATA,
        )
        column_0 = ColumnCatalogEntry("name", ColumnType.TEXT, is_nullable=False)
        column_1 = ColumnCatalogEntry("id", ColumnType.INTEGER, is_nullable=False)
        column_2 = ColumnCatalogEntry(
            "data", ColumnType.NDARRAY, False, NdArrayType.UINT8, [2, 2, 3]
        )
        table_info.schema = [column_0, column_1, column_2]
        return table_info

    def setUp(self):
        TransactionManager().begin_transaction()
        self.table = self.create_sample_table()

    def tearDown(self):
        try:
            shutil.rmtree(prefix_worker_id("dataset"), ignore_errors=True)
        except ValueError:
            pass
        TransactionManager().rollback_transaction()

    def test_should_create_empty_table(self):
        sqlengine = SQLStorageEngine()
        sqlengine.create(self.table)
        records = list(sqlengine.read(self.table, batch_mem_size=3000))
        self.assertEqual(records, [])
        # clean up
        sqlengine.drop(self.table)

    def test_should_write_rows_to_table(self):
        dummy_batches = list(create_dummy_batches())
        # drop the _row_id
        dummy_batches = [batch.project(batch.columns[1:]) for batch in dummy_batches]
        sqlengine = SQLStorageEngine()
        sqlengine.create(self.table)
        for batch in dummy_batches:
            batch.drop_column_alias()
            sqlengine.write(self.table, batch)

        read_batch = list(sqlengine.read(self.table, batch_mem_size=3000))
        self.assertTrue(read_batch, dummy_batches)
        # clean up
        sqlengine.drop(self.table)

    def test_rename(self):
        table_info = TableCatalogEntry(
            "new_name", "new_name", table_type=TableType.VIDEO_DATA
        )
        sqlengine = SQLStorageEngine()

        with pytest.raises(Exception):
            sqlengine.rename(self.table, table_info)

    def test_sqlite_storage_engine_exceptions(self):
        sqlengine = SQLStorageEngine()

        missing_table_info = TableCatalogEntry(
            "missing_table", None, table_type=TableType.VIDEO_DATA
        )

        with self.assertRaises(Exception):
            sqlengine.drop(missing_table_info)

        with self.assertRaises(Exception):
            sqlengine.write(missing_table_info, None)

        with self.assertRaises(Exception):
            read_batch = list(sqlengine.read(missing_table_info))
            self.assertEqual(read_batch, None)

        with self.assertRaises(Exception):
            sqlengine.delete(missing_table_info, None)

    def test_cannot_delete_missing_column(self):
        sqlengine = SQLStorageEngine()
        sqlengine.create(self.table)

        incorrect_where_clause = {"foo": None}

        with self.assertRaises(Exception):
            sqlengine.delete(self.table, incorrect_where_clause)
        # clean up
        sqlengine.drop(self.table)
