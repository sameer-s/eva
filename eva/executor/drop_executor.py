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


from pathlib import Path

import pandas as pd

from eva.catalog.catalog_manager import CatalogManager
from eva.executor.abstract_executor import AbstractExecutor
from eva.executor.executor_utils import ExecutorError
from eva.models.storage.batch import Batch
from eva.parser.table_ref import TableInfo
from eva.plan_nodes.drop_plan import DropPlan
from eva.storage.storage_engine import StorageEngine
from eva.storage.transaction_manager import TransactionManager
from eva.utils.logging_manager import logger


class DropExecutor(AbstractExecutor):
    def __init__(self, node: DropPlan):
        super().__init__(node)

    def exec(self, *args, **kwargs):
        """Drop table executor"""
        catalog_manager = CatalogManager()

        assert len(self.node.table_infos) == 1, "Drop supports only single table"

        table_info: TableInfo = self.node.table_infos[0]

        TransactionManager().drop_table(table_info.table_name)

        if not catalog_manager.check_table_exists(
            table_info.table_name, table_info.database_name
        ):
            err_msg = "Table: {} does not exist".format(table_info)
            if self.node.if_exists:
                logger.warn(err_msg)
                return Batch(pd.DataFrame([err_msg]))
            else:
                logger.exception(err_msg)
                raise ExecutorError(err_msg)

        table_obj = catalog_manager.get_table_catalog_entry(
            table_info.table_name, table_info.database_name
        )
        TransactionManager().lock_multimedia_file(Path(table_obj.file_url).stem)
        
        storage_engine = StorageEngine.factory(table_obj)

        storage_engine.drop(table=table_obj)

        for col_obj in table_obj.columns:
            for cache in col_obj.dep_caches:
                catalog_manager.drop_udf_cache_catalog_entry(cache)

        assert catalog_manager.delete_table_catalog_entry(
            table_obj
        ), "Failed to drop {}".format(table_info)

        yield Batch(
            pd.DataFrame(
                {"Table Successfully dropped: {}".format(table_info.table_name)},
                index=[0],
            )
        )
