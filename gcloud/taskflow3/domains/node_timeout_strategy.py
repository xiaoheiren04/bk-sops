# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
Edition) available.
Copyright (C) 2017 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from abc import ABCMeta, abstractmethod
from django.conf import settings
from pipeline.eri.models import State


class NodeTimeoutStrategy(metaclass=ABCMeta):
    TIMEOUT_NODE_OPERATOR = "sops_system"

    @abstractmethod
    def deal_with_timeout_node(self, task, node_id):
        pass


class ForcedFailStrategy(NodeTimeoutStrategy):
    def deal_with_timeout_node(self, task, node_id):
        return task.nodes_action("forced_fail", node_id, self.TIMEOUT_NODE_OPERATOR)


class ForcedFailAndSkipStrategy(NodeTimeoutStrategy):
    def deal_with_timeout_node(self, task, node_id):
        fail_result = task.nodes_action("forced_fail", node_id, self.TIMEOUT_NODE_OPERATOR)
        if fail_result["result"]:
            skip_result = task.nodes_action("skip", node_id, self.TIMEOUT_NODE_OPERATOR)
            return skip_result
        return fail_result

class ForcedFailAndRetryStrategy(NodeTimeoutStrategy):
    def deal_with_timeout_node(self, task, node_id):
        state = State.objects.only("retry").get(node_id=node_id)
        fail_result = task.nodes_action(
            "forced_fail",
            node_id,
            self.TIMEOUT_NODE_OPERATOR,
            full_ex_data = self.ex_data_hint,
            send_post_set_state_singal = False,
        )
        if not fail_result["result"]:
            return fail_result
        max_retry_times = settings.TASKFLOW_NODE_TIMEOUT_RETRY_MAX_TIMES
        if state.retry >= max_retry_times:
            fail_result["message"] = (
                "The node has been terminated by the system due to exceeding the 'Timeout Setting'," \
                "and will not be retried because the timeout retry limit has been reached."
            )
            return fail_result
        return task.nodes_action("retry", node_id, self.TIMEOUT_NODE_OPERATOR, inputs = {})

node_timeout_handler = {
    "forced_fail": ForcedFailStrategy(),
    "forced_fail_and_skip": ForcedFailAndSkipStrategy(),
    "forced_fail_and_retry": ForcedFailAndRetryStrategy(),

}
