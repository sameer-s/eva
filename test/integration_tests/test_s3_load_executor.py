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
from pathlib import Path
from test.util import (
    create_dummy_batches,
    create_sample_video,
    file_remove,
    shutdown_ray,
)

import boto3
import pandas as pd
import pytest
from moto import mock_s3

from eva.catalog.catalog_manager import CatalogManager
from eva.configuration.configuration_manager import ConfigurationManager
from eva.configuration.constants import EVA_ROOT_DIR
from eva.models.storage.batch import Batch
from eva.parser.types import FileFormatType
from eva.server.command_handler import execute_query_fetch_all


class S3LoadExecutorTest(unittest.TestCase):
    mock_s3 = mock_s3()

    def setUp(self):
        self.video_file_path = create_sample_video()
        self.multiple_video_file_path = f"{EVA_ROOT_DIR}/data/sample_videos/1"
        self.s3_download_dir = ConfigurationManager().get_value(
            "storage", "s3_download_dir"
        )

        """Mocked AWS Credentials for moto."""
        os.environ["AWS_ACCESS_KEY_ID"] = "testing"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
        os.environ["AWS_SECURITY_TOKEN"] = "testing"
        os.environ["AWS_SESSION_TOKEN"] = "testing"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

        self.mock_s3.start()

        self.s3_client = boto3.client("s3")

    def upload_single_file(self, bucket_name="test-bucket"):
        self.s3_client.create_bucket(Bucket=bucket_name)
        self.s3_client.upload_file(self.video_file_path, bucket_name, "dummy.avi")

    def upload_multiple_files(self, bucket_name="test-bucket"):
        self.s3_client.create_bucket(Bucket=bucket_name)
        video_path = self.multiple_video_file_path

        for file in os.listdir(video_path):
            self.s3_client.upload_file(f"{video_path}/{file}", bucket_name, file)

    def tearDown(self):
        shutdown_ray()

        file_remove("MyVideo/dummy.avi", parent_dir=self.s3_download_dir)

        for file in os.listdir(self.multiple_video_file_path):
            file_remove(f"MyVideos/{file}", parent_dir=self.s3_download_dir)

        self.mock_s3.stop()

    def test_s3_single_file_load_executor(self):
        bucket_name = "single-file-bucket"
        self.upload_single_file(bucket_name)

        query = f"LOAD VIDEO 's3://{bucket_name}/dummy.avi' INTO MyVideo;"
        execute_query_fetch_all(query)

        select_query = """SELECT * FROM MyVideo;"""

        actual_batch = execute_query_fetch_all(select_query)
        actual_batch.sort()
        expected_batch = list(
            create_dummy_batches(
                video_dir=os.path.join(self.s3_download_dir, "MyVideo")
            )
        )[0]
        self.assertEqual(actual_batch, expected_batch)
        execute_query_fetch_all("DROP TABLE IF EXISTS MyVideo;")

    def test_s3_multiple_file_load_executor(self):
        bucket_name = "multiple-file-bucket"
        self.upload_multiple_files(bucket_name)

        query = f"""LOAD VIDEO "s3://{bucket_name}/*.mp4" INTO MyVideos;"""
        result = execute_query_fetch_all(query)
        expected = Batch(
            pd.DataFrame([f"Number of loaded {FileFormatType.VIDEO.name}: 2"])
        )
        self.assertEqual(result, expected)

        execute_query_fetch_all("DROP TABLE IF EXISTS MyVideos;")

    def test_s3_multiple_file_multiple_load_executor(self):
        bucket_name = "multiple-file-multiple-load-bucket"
        self.upload_single_file(bucket_name)
        self.upload_multiple_files(bucket_name)

        insert_query_one = f"""LOAD VIDEO "s3://{bucket_name}/1.mp4" INTO MyVideos;"""
        execute_query_fetch_all(insert_query_one)
        insert_query_two = f"""LOAD VIDEO "s3://{bucket_name}/2.mp4" INTO MyVideos;"""
        execute_query_fetch_all(insert_query_two)
        insert_query_three = f"LOAD VIDEO '{self.video_file_path}' INTO MyVideos;"
        execute_query_fetch_all(insert_query_three)

        select_query = """SELECT * FROM MyVideos;"""
        result = execute_query_fetch_all(select_query)
        result_videos = [
            Path(video).as_posix() for video in result.frames["myvideos.name"].unique()
        ]

        s3_dir_path = Path(self.s3_download_dir)
        expected_videos = [
            (s3_dir_path / "MyVideos/1.mp4").as_posix(),
            (s3_dir_path / "MyVideos/2.mp4").as_posix(),
            Path(self.video_file_path).as_posix(),
        ]

        self.assertEqual(result_videos, expected_videos)

        execute_query_fetch_all("DROP TABLE IF EXISTS MyVideos;")
