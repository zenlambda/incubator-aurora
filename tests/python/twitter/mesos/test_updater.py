from math import ceil
import copy
import unittest
import pytest
from mesos_twitter.ttypes import *
from twitter.common import options
from twitter.mesos.mesos.updater import *
import twitter.common.log
from fake_scheduler import *

def find_expected_status_calls(watch_secs, sleep_secs):
  return ceil(watch_secs / sleep_secs)

class UpdaterTest(unittest.TestCase):
  BATCH_SIZE = 3
  WATCH_SECS = RESTART_THRESHOLD = 50.0
  EXPECTED_INITIAL_GET_STATUS_CALL = 1
  EXPECTED_GET_STATUS_CALLS = (find_expected_status_calls(WATCH_SECS, 3.0) +
      EXPECTED_INITIAL_GET_STATUS_CALL)
  EXPECTED_GET_STATUS_CALLS_IN_UNKNOWN_STATE = 1
  MAX_SHARD_FAILURE = 0
  MAX_TOTAL_FAILURE = 0

  @classmethod
  def setUpClass(cls):
    options.parse([])
    twitter.common.log.init('Update_test')

  def setUp(self):
    self._clock = Clock()
    self._scheduler = FakeScheduler()
    self._updater = Updater('mesos', {'name' : 'sathya'}, self._scheduler, self._clock,
        'test_update')
    self._update_config = UpdateConfig()
    self._update_config.batchSize = UpdaterTest.BATCH_SIZE
    self._update_config.restartThreshold = UpdaterTest.RESTART_THRESHOLD
    self._update_config.watchSecs = UpdaterTest.WATCH_SECS
    self._update_config.maxPerShardFailures = UpdaterTest.MAX_SHARD_FAILURE
    self._update_config.maxTotalFailures = UpdaterTest.MAX_TOTAL_FAILURE
    self._job_config = JobConfiguration()
    task = TwitterTaskInfo()
    tasks = []
    for i in range(10):
      taskCopy = copy.deepcopy(task)
      taskCopy.shardId = i
      tasks.append(taskCopy)
    self._job_config.taskConfigs = tasks
    self._job_config.updateConfig = self._update_config

  def expect_restart(self, shard_ids):
    self._scheduler.expect_updateShards('mesos', 'sathya', shard_ids, 'test_update')

  def expect_rollback(self, shard_ids):
    self._scheduler.expect_rollbackShards('mesos', 'sathya', shard_ids, 'test_update')

  def expect_get_statuses(self, num_calls, statuses):
    for x in range(num_calls):
      self._scheduler.expect_getTasksStatus(statuses)

  def test_case_pass(self):
    """All tasks complete and update succeeds"""
    self.expect_restart([0, 1, 2])
    self.expect_get_statuses(UpdaterTest.EXPECTED_GET_STATUS_CALLS,
        {0: ScheduleStatus.RUNNING, 1: ScheduleStatus.RUNNING, 2: ScheduleStatus.RUNNING})
    self.expect_restart([3, 4, 5])
    self.expect_get_statuses(UpdaterTest.EXPECTED_GET_STATUS_CALLS,
        {3: ScheduleStatus.RUNNING, 4: ScheduleStatus.RUNNING, 5: ScheduleStatus.RUNNING})
    self.expect_restart([6, 7, 8])
    self.expect_get_statuses(UpdaterTest.EXPECTED_GET_STATUS_CALLS,
        {6: ScheduleStatus.RUNNING, 7: ScheduleStatus.RUNNING, 8: ScheduleStatus.RUNNING})
    self.expect_restart([9])
    self.expect_get_statuses(UpdaterTest.EXPECTED_GET_STATUS_CALLS,
        {9: ScheduleStatus.RUNNING})
    shards_expected = []
    shards_returned = self._updater.update(self._job_config)
    assert shards_expected == shards_returned, ('Expected shards (%s) : Returned shards (%s)' %
        (shards_expected, shards_returned))

  def test_tasks_stuck_in_starting(self):
    """Tasks 1, 2, 3 fail to move into RUNNING when restarted - Complete rollback performed."""
    self._update_config.maxTotalFailures = 5
    self._update_config.maxPerShardFailures = 2
    self.expect_restart([0, 1, 2])
    self.expect_get_statuses(UpdaterTest.EXPECTED_GET_STATUS_CALLS,
        {0: ScheduleStatus.STARTING, 1: ScheduleStatus.STARTING, 2: ScheduleStatus.STARTING})
    self.expect_restart([0, 1, 2])
    self.expect_get_statuses(UpdaterTest.EXPECTED_GET_STATUS_CALLS,
        {0: ScheduleStatus.STARTING, 1: ScheduleStatus.STARTING, 2: ScheduleStatus.STARTING})
    self.expect_rollback([0, 1, 2])
    shards_expected = [0, 1, 2]
    shards_returned = self._updater.update(self._job_config)
    assert shards_expected == shards_returned, ('Expected shards (%s) : Returned shards (%s)' %
        (shards_expected, shards_returned))

  def test_single_failed_shard(self):
    """All tasks fail to move into running state when re-started - Complete rollback performed."""
    self._update_config.maxTotalFailures = 5
    self._update_config.maxPerShardFailures = 2
    self.expect_restart([0, 1, 2])
    self.expect_get_statuses(UpdaterTest.EXPECTED_GET_STATUS_CALLS,
        {0: ScheduleStatus.STARTING, 1: ScheduleStatus.RUNNING, 2: ScheduleStatus.RUNNING})
    self.expect_restart([0, 3, 4])
    self.expect_get_statuses(UpdaterTest.EXPECTED_GET_STATUS_CALLS,
        {0: ScheduleStatus.STARTING, 3: ScheduleStatus.RUNNING, 4: ScheduleStatus.RUNNING})
    self.expect_restart([0, 5, 6])
    self.expect_get_statuses(UpdaterTest.EXPECTED_GET_STATUS_CALLS,
        {0: ScheduleStatus.STARTING, 5: ScheduleStatus.RUNNING, 6: ScheduleStatus.RUNNING})
    self.expect_rollback([0, 1, 2])
    self.expect_rollback([3, 4, 5])
    self.expect_rollback([6])
    shards_expected = [0]
    shards_returned = self._updater.update(self._job_config)
    assert shards_expected == shards_returned, ('Expected shards (%s) : Returned shards (%s)' %
        (shards_expected, shards_returned))

  def test_shard_state_transition(self):
    """All tasks move into running state at the end of restart threshold."""
    self.expect_restart([0, 1, 2])
    self.expect_get_statuses(UpdaterTest.EXPECTED_GET_STATUS_CALLS - 1,
        {0: ScheduleStatus.STARTING, 1: ScheduleStatus.STARTING, 2: ScheduleStatus.STARTING})
    self.expect_get_statuses(UpdaterTest.EXPECTED_GET_STATUS_CALLS,
        {0: ScheduleStatus.RUNNING, 1: ScheduleStatus.RUNNING, 2: ScheduleStatus.RUNNING})
    self.expect_restart([3, 4, 5])
    self.expect_get_statuses(UpdaterTest.EXPECTED_GET_STATUS_CALLS - 1,
        {3: ScheduleStatus.STARTING, 4: ScheduleStatus.STARTING, 5: ScheduleStatus.STARTING})
    self.expect_get_statuses(UpdaterTest.EXPECTED_GET_STATUS_CALLS,
        {3: ScheduleStatus.RUNNING, 4: ScheduleStatus.RUNNING, 5: ScheduleStatus.RUNNING})
    self.expect_restart([6, 7, 8])
    self.expect_get_statuses(UpdaterTest.EXPECTED_GET_STATUS_CALLS - 1,
        {6: ScheduleStatus.STARTING, 7: ScheduleStatus.STARTING, 8: ScheduleStatus.STARTING})
    self.expect_get_statuses(UpdaterTest.EXPECTED_GET_STATUS_CALLS,
        {6: ScheduleStatus.RUNNING, 7: ScheduleStatus.RUNNING, 8: ScheduleStatus.RUNNING})
    self.expect_restart([9])
    self.expect_get_statuses(UpdaterTest.EXPECTED_GET_STATUS_CALLS - 1,
        {9: ScheduleStatus.STARTING})
    self.expect_get_statuses(UpdaterTest.EXPECTED_GET_STATUS_CALLS,
        {9: ScheduleStatus.RUNNING})
    shards_expected = []
    shards_returned = self._updater.update(self._job_config)
    assert shards_expected == shards_returned, ('Expected shards (%s) : Returned shards (%s)' %
        (shards_expected, shards_returned))

  def test_case_unknown_state(self):
    """All tasks move into an unexpected state - Complete rollback performed."""
    self._update_config.maxTotalFailures = 5
    self._update_config.maxPerShardFailures = 2
    self.expect_restart([0, 1, 2])
    self.expect_get_statuses(UpdaterTest.EXPECTED_GET_STATUS_CALLS_IN_UNKNOWN_STATE,
        {0: ScheduleStatus.FINISHED, 1: ScheduleStatus.FINISHED, 2: ScheduleStatus.FINISHED})
    self.expect_restart([0, 1, 2])
    self.expect_get_statuses(UpdaterTest.EXPECTED_GET_STATUS_CALLS_IN_UNKNOWN_STATE,
        {0: ScheduleStatus.FINISHED, 1: ScheduleStatus.FINISHED, 2: ScheduleStatus.FINISHED})
    self.expect_rollback([0, 1, 2])
    shards_expected = [0, 1, 2]
    shards_returned = self._updater.update(self._job_config)
    assert shards_expected == shards_returned, ('Expected shards (%s) : Returned shards (%s)' %
        (shards_expected, shards_returned))

  def test_invalid_batch_size(self):
    """Test for out of range error for batch size"""
    self._update_config.batchSize = 0
    with pytest.raises(InvalidUpdaterConfigException):
      self._updater.update(self._job_config)

  def test_invalid_restart_threshold(self):
    """Test for out of range error for restart threshold"""
    self._update_config.restartThreshold = 0
    with pytest.raises(InvalidUpdaterConfigException):
      self._updater.update(self._job_config)

  def test_invalid_watch_secs(self):
    """Test for out of range error for watch secs"""
    self._update_config.watchSecs = 0
    with pytest.raises(InvalidUpdaterConfigException):
      self._updater.update(self._job_config)