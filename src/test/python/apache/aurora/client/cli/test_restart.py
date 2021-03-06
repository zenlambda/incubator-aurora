#
# Copyright 2014 Apache Software Foundation
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
#
import contextlib
import functools

from apache.aurora.client.api.health_check import StatusHealthCheck, Retriable
from apache.aurora.client.cli import EXIT_API_ERROR
from apache.aurora.client.cli.client import AuroraCommandLine
from apache.aurora.client.cli.util import AuroraClientCommandTest

from twitter.common.contextutil import temporary_file

from gen.apache.aurora.api.ttypes import (
    AssignedTask,
    JobKey,
    PopulateJobResult,
    ScheduledTask,
    ScheduleStatusResult,
    TaskConfig,
)

from mock import Mock, patch


class TestRestartCommand(AuroraClientCommandTest):

  @classmethod
  def setup_mock_scheduler_for_simple_restart(cls, api):
    """Set up all of the API mocks for scheduler calls during a simple restart"""
    sched_proxy = api.scheduler_proxy
    cls.setup_get_tasks_status_calls(sched_proxy)
    cls.setup_populate_job_config(sched_proxy)
    sched_proxy.restartShards.return_value = cls.create_simple_success_response()

  @classmethod
  def setup_populate_job_config(cls, api):
    populate = cls.create_simple_success_response()
    populate.result.populateJobResult = Mock(spec=PopulateJobResult)
    api.populateJobConfig.return_value = populate
    configs = [Mock(spec=TaskConfig) for i in range(20)]
    populate.result.populateJobResult.populated = set(configs)
    return populate


  @classmethod
  def setup_health_checks(cls, mock_api):
    mock_health_check = Mock(spec=StatusHealthCheck)
    mock_health_check.health.return_value = Retriable.alive()
    return mock_health_check

  def test_restart_simple(self):
    # Test the client-side restart logic in its simplest case: everything succeeds
    (mock_api, mock_scheduler_proxy) = self.create_mock_api()
    mock_health_check = self.setup_health_checks(mock_api)
    self.setup_mock_scheduler_for_simple_restart(mock_api)
    with contextlib.nested(
        patch('apache.aurora.client.api.SchedulerProxy', return_value=mock_scheduler_proxy),
        patch('apache.aurora.client.factory.CLUSTERS', new=self.TEST_CLUSTERS),
        patch('apache.aurora.client.api.instance_watcher.StatusHealthCheck',
            return_value=mock_health_check),
        patch('time.time', side_effect=functools.partial(self.fake_time, self)),
        patch('time.sleep', return_value=None)
    ):
      with temporary_file() as fp:
        fp.write(self.get_valid_config())
        fp.flush()
        cmd = AuroraCommandLine()
        cmd.execute(['job', 'restart', '--batch-size=5', 'west/bozo/test/hello', fp.name])

        # Like the update test, the exact number of calls here doesn't matter.
        # what matters is that it must have been called once before batching, plus
        # at least once per batch, and there are 4 batches.
        assert mock_scheduler_proxy.getTasksStatus.call_count >= 4
        # called once per batch
        assert mock_scheduler_proxy.restartShards.call_count == 4
        # parameters for all calls are generated by the same code, so we just check one
        mock_scheduler_proxy.restartShards.assert_called_with(JobKey(environment=self.TEST_ENV,
            role=self.TEST_ROLE, name=self.TEST_JOB), [15, 16, 17, 18, 19], None)

  def test_restart_failed_status(self):
    # Test the client-side updater logic in its simplest case: everything succeeds, and no rolling
    # updates.
    (mock_api, mock_scheduler_proxy) = self.create_mock_api()
    mock_health_check = self.setup_health_checks(mock_api)
    self.setup_mock_scheduler_for_simple_restart(mock_api)
    mock_scheduler_proxy.getTasksStatus.return_value = self.create_error_response()
    with contextlib.nested(
        patch('apache.aurora.client.api.SchedulerProxy', return_value=mock_scheduler_proxy),
        patch('apache.aurora.client.factory.CLUSTERS', new=self.TEST_CLUSTERS),
        patch('apache.aurora.client.api.instance_watcher.StatusHealthCheck',
            return_value=mock_health_check),
        patch('time.time', side_effect=functools.partial(self.fake_time, self)),
        patch('time.sleep', return_value=None)):
      with temporary_file() as fp:
        fp.write(self.get_valid_config())
        fp.flush()
        cmd = AuroraCommandLine()
        result = cmd.execute(['job', 'restart', '--batch-size=5', 'west/bozo/test/hello', fp.name])
        assert mock_scheduler_proxy.getTasksStatus.call_count == 1
        assert mock_scheduler_proxy.restartShards.call_count == 0
        assert result == EXIT_API_ERROR

  def test_restart_failed_restart(self):
    # Test the client-side updater logic in its simplest case: everything succeeds, and no rolling
    # updates.
    (mock_api, mock_scheduler_proxy) = self.create_mock_api()
    mock_health_check = self.setup_health_checks(mock_api)
    self.setup_mock_scheduler_for_simple_restart(mock_api)
    mock_scheduler_proxy.restartShards.return_value = self.create_error_response()
    with contextlib.nested(
        patch('apache.aurora.client.api.SchedulerProxy', return_value=mock_scheduler_proxy),
        patch('apache.aurora.client.factory.CLUSTERS', new=self.TEST_CLUSTERS),
        patch('apache.aurora.client.api.instance_watcher.StatusHealthCheck',
            return_value=mock_health_check),
        patch('time.time', side_effect=functools.partial(self.fake_time, self)),
        patch('time.sleep', return_value=None)):
      with temporary_file() as fp:
        fp.write(self.get_valid_config())
        fp.flush()
        cmd = AuroraCommandLine()
        result = cmd.execute(['job', 'restart', '--batch-size=5', 'west/bozo/test/hello', fp.name])
        assert mock_scheduler_proxy.getTasksStatus.call_count == 1
        assert mock_scheduler_proxy.restartShards.call_count == 1
        mock_scheduler_proxy.restartShards.assert_called_with(JobKey(environment=self.TEST_ENV,
            role=self.TEST_ROLE, name=self.TEST_JOB), [0, 1, 2, 3, 4], None)
        assert result == EXIT_API_ERROR
