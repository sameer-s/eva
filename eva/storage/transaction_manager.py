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

class TransactionManager:
    """ Singleton class responsible for tracking the current transaction

    Attributes:
        _instance: stores the singleton instance of the class.
    """

    def __new__(cls):
        """Overrides the default __new__ method.

        Returns the existing instance or creates a new one if an instance
        does not exist.

        Returns:
            An instance of the class.
        """
        if not hasattr(cls, "_instance"):
            cls._instance = super(TransactionManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        self.transaction_in_progress = False