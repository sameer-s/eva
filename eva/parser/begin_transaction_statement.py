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
from eva.parser.statement import AbstractStatement
from eva.parser.types import StatementType

class BeginTransactionStatement(AbstractStatement):
    """
    Begin Transaction statement constructed after parsing the input query
    """

    def __init__(self):
        super().__init__(StatementType.BEGIN_TRANSACTION)

    def __str__(self):
        return "BEGIN TRANSACTION"

    def __eq__(self, other):
        return isinstance(other, BeginTransactionStatement)

    def __hash__(self):
        return 1 # this class has no state