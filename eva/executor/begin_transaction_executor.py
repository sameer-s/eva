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
from eva.executor.abstract_executor import AbstractExecutor
from eva.plan_nodes.begin_transaction_plan import BeginTransactionPlan
from eva.catalog.sql_config import SQLConfig
from eva.storage.transaction_manager import TransactionManager

class BeginTransactionExecutor(AbstractExecutor):
    def __init__(self, node: BeginTransactionPlan):
        super().__init__(node)
        self.session = SQLConfig().session

    def exec(self, *args, **kwargs):
        self.session.begin()
        TransactionManager().transaction_in_progress = True