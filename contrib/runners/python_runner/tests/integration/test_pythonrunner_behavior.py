# Copyright 2020 The StackStorm Authors.
# Copyright 2019 Extreme Networks, Inc.
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

"""
This tests whether an action which is python-script behaves as we expect.
"""

import os
import pwd
import mock
import tempfile

from oslo_config import cfg

from python_runner import python_runner
from st2common import log as logging
from st2common.util.virtualenvs import setup_pack_virtualenv
from st2tests import config
from st2tests.base import CleanFilesTestCase
from st2tests.base import CleanDbTestCase
from st2tests.fixturesloader import get_fixtures_base_path

__all__ = ["PythonRunnerBehaviorTestCase"]

LOG = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WRAPPER_SCRIPT_PATH = os.path.join(
    BASE_DIR, "../../../python_runner/python_runner/python_action_wrapper.py"
)
WRAPPER_SCRIPT_PATH = os.path.abspath(WRAPPER_SCRIPT_PATH)


class PythonRunnerBehaviorTestCase(CleanFilesTestCase, CleanDbTestCase):
    def setUp(self):
        super(PythonRunnerBehaviorTestCase, self).setUp()
        config.parse_args()

        dir_path = tempfile.mkdtemp()
        cfg.CONF.set_override(name="base_path", override=dir_path, group="system")

        self.base_path = dir_path
        self.virtualenvs_path = os.path.join(self.base_path, "virtualenvs/")
        LOG.debug(
            f"{self.virtualenvs_path} exists={os.path.exists(self.virtualenvs_path)} "
        )

        # Make sure dir is deleted on tearDown
        self.to_delete_directories.append(self.base_path)

    def test_priority_of_loading_library_after_setup_pack_virtualenv(self):
        """
        This test checks priority of loading library, whether the library which is specified in
        the 'requirements.txt' of pack is loaded when a same name module is also specified in the
        'requirements.txt' of st2, at a subprocess in ActionRunner.

        To test above, this uses 'get_library_path.py' action in 'test_library_dependencies' pack.
        This action returns file-path of imported module which is specified by 'module' parameter.
        """
        pack_name = "test_library_dependencies"

        # Before calling action, this sets up virtualenv for test pack. This pack has
        # requirements.txt wihch only writes 'six' module.
        setup_pack_virtualenv(pack_name=pack_name)
        self.assertTrue(os.path.exists(os.path.join(self.virtualenvs_path, pack_name)))
        ls_v = os.stat(self.virtualenvs_path)
        LOG.debug(
            f"{self.virtualenvs_path} exists={os.path.exists(self.virtualenvs_path)} "
            f"perms={oct(ls_v.st_mode)[-3:]} owner_uid={ls_v.st_uid} owner_gid={ls_v.st_gid} "
            f"owner={pwd.getpwuid(ls_v.st_uid)[0]} "
            f"uid={os.getuid()} user={pwd.getpwuid(os.getuid())[0]}"
        )
        ls = os.stat(os.path.join(self.virtualenvs_path, pack_name))
        LOG.debug(
            f"{os.path.join(self.virtualenvs_path, pack_name)} "
            f"exists={os.path.exists(os.path.join(self.virtualenvs_path, pack_name))} "
            f"perms={oct(ls.st_mode)[-3:]} owner_uid={ls.st_uid} owner_gid={ls.st_gid} "
            f"owner={pwd.getpwuid(ls.st_uid)[0]} "
            f"uid={os.getuid()} user={pwd.getpwuid(os.getuid())[0]}"
        )

        # This test suite expects that loaded six module is located under the virtualenv library,
        # because 'six' is written in the requirements.txt of 'test_library_dependencies' pack.
        (_, output, _) = self._run_action(
            pack_name, "get_library_path.py", {"module": "six"}
        )
        self.assertEqual(output["result"].find(self.virtualenvs_path), 0)

        # Conversely, this expects that 'mock' module file-path is not under sandbox library,
        # but the parent process's library path, because that is not under the pack's virtualenv.
        (_, output, _) = self._run_action(
            pack_name, "get_library_path.py", {"module": "mock"}
        )
        self.assertEqual(output["result"].find(self.virtualenvs_path), -1)

        # While a module which is in the pack's virtualenv library is specified at 'module'
        # parameter of the action, this test suite expects that file-path under the parent's
        # library is returned when 'sandbox' parameter of PythonRunner is False.
        (_, output, _) = self._run_action(
            pack_name, "get_library_path.py", {"module": "six"}, {"_sandbox": False}
        )
        self.assertEqual(output["result"].find(self.virtualenvs_path), -1)

    def _run_action(self, pack, action, params, runner_params={}):
        action_db = mock.Mock()
        action_db.pack = pack

        runner = python_runner.get_runner()
        runner.runner_parameters = {}
        runner.action = action_db
        runner._use_parent_args = False

        for key, value in runner_params.items():
            setattr(runner, key, value)

        runner.entry_point = os.path.join(
            get_fixtures_base_path(), "packs/%s/actions/%s" % (pack, action)
        )
        runner.pre_run()
        return runner.run(params)
