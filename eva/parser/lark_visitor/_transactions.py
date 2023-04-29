# coding=utf-8
# Copyright 2023 EVA
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
from lark.tree import Tree
from eva.parser.begin_transaction_statement import BeginTransactionStatement
from eva.parser.end_transaction_statement import EndTransactionStatement

##################################################################
# Transactions - BEGIN, END                                      #
##################################################################
class Transactions:
    def begin_transaction(self, tree):
        begin_transaction_stmt = BeginTransactionStatement()
        return begin_transaction_stmt
    
    def end_transaction(self, tree):
        end_transaction_stmt = EndTransactionStatement()
        return end_transaction_stmt