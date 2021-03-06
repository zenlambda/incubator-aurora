#!/bin/bash
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
#
# A simple integration test for the mesos client, intended to be run  before checkin of major
#client changes, and as a part of an integrated build process.
#
# This test uses the vagrant demonstration environment. It loads up a virtual cluster, and then
# launches a job, verifies that it's running, updates it, verifies that the update succeeded,
# and then kills the job.

set -u -e -x

. src/test/sh/org/apache/aurora/e2e/test_common.sh

function run_dev() {
  vagrant ssh devcluster -c "$1"
}

function run_sched() {
  vagrant ssh devcluster -c "$1"
}

devtools_setup() {
  local _testdir=$1
  # grab the current branch name, and create a workspace using the same branch in vagrant.
  branch=$(git branch | grep '*' | cut -c 3-)
  run_dev "if [ ! -d ~/test_dev ]; then git clone /vagrant ~/test_dev; fi"
  # Clean out any lingering build products; we want fresh.
  run_dev "rm -rf ~/.pex"
  run_dev "cd ~/test_dev; git reset --hard; git clean -fdx"
  run_dev "cd ~/test_dev; git checkout $branch; git pull"
  run_dev "cd ~/test_dev; ./pants src/main/python/apache/aurora/client/bin:aurora_client"
  run_dev "cd ~/test_dev; ./pants src/test/sh/org/apache/aurora/e2e/flask:flask_example"
  if [ ! -d $_testdir ]
    then
      mkdir $_testdir
    fi
  run_dev "cd ~/test_dev; cp dist/flask_example.pex /vagrant/$_testdir"
  run_dev "cd ~/test_dev; cp dist/aurora_client.pex /vagrant/$_testdir"
}

test_flask_example() {
  local _cluster=$1 _role=$2 _env=$3 _job=$4 _testdir=$5 _sched_ip=$6
  local _base_config=$7 _updated_config=$8
  jobkey="$_cluster/$_role/$_env/$_job"
  echo '== Creating job'
  run_sched "/vagrant/$_testdir/aurora_client.pex create $jobkey $_base_config"

  # Check that scheduler /vars being exported
  base_url="http://$_sched_ip:8081"
  uptime=$(_curl -s "$base_url/vars" | grep jvm_uptime_secs | wc -l)
  test $uptime -eq 1

  echo '== Updating test job'
  run_sched "/vagrant/$_testdir/aurora_client.pex update $jobkey $_updated_config"

  #echo "== Probing job via 'aurora run'"
  # TODO(mchucarroll): Get "run" working: the vagrant configuration currently doesn't set up ssh
  # to allow automatic logins to the slaves. "aurora run" therefore tries to prompt the user for
  # a password, finds that it's not running in a TTY, and aborts.
  runlen=$(run_sched "/vagrant/$_testdir/aurora_client.pex run $jobkey 'pwd'" | wc -l)
  test $runlen -eq 2

  run_sched "/vagrant/$_testdir/aurora_client.pex get_quota --cluster=$_cluster $_role"

  run_sched "/vagrant/$_testdir/aurora_client.pex killall  $jobkey"
}

RETCODE=1
# Set up shorthands for test
export EXAMPLE_DIR=/vagrant/src/test/sh/org/apache/aurora/e2e/flask
TEST_DIR=deploy_test
TEST_CLUSTER=devcluster
TEST_ROLE=vagrant
TEST_ENV=test
TEST_JOB=flask_example
TEST_SCHEDULER_IP=192.168.33.7
TEST_ARGS=(
  $TEST_CLUSTER
  $TEST_ROLE
  $TEST_ENV
  $TEST_JOB
  $TEST_DIR
  $TEST_SCHEDULER_IP
  $EXAMPLE_DIR/flask_example.aurora
  $EXAMPLE_DIR/flask_example_updated.aurora
  )

trap collect_result EXIT
vagrant up
# wipe the pseudo-deploy dir, and then create it fresh, to guarantee that the
# test runs clean.
rm -rf $TEST_DIR
devtools_setup $TEST_DIR
test_flask_example "${TEST_ARGS[@]}"
RETCODE=0
