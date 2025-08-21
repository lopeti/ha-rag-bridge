"""EGYSZERŰ TESZT HOOK - minimális implementáció"""

from litellm.integrations.custom_logger import CustomLogger
import logging

logger = logging.getLogger("simple_test_hook")
logger.setLevel(logging.INFO)


class SimpleTestHook(CustomLogger):
    def __init__(self):
        super().__init__()
        logger.info("🔥🔥🔥 SIMPLE HOOK INITIALIZED")

    def log_success_event(self, kwargs, response_obj, start_time, end_time):
        logger.info("🔥🔥🔥 SYNC log_success_event CALLED!")

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        logger.info("🔥🔥🔥 ASYNC log_success_event CALLED!")

    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        logger.info(f"🔥🔥🔥 ASYNC PRE CALL HOOK CALLED! call_type={call_type}")
        return data


# Create instance
simple_hook_instance = SimpleTestHook()
logger.info("🔥🔥🔥 Simple hook instance created")
