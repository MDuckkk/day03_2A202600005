import os
from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger
from datetime import datetime

class BasicChatbot:
    """
    A basic Chatbot that does not use tools.
    """
    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def get_system_prompt(self) -> str:
        current_year = datetime.now().year
        return (
            "You are a helpful shopping assistant for an electronics store.\n"
            "You do NOT have access to any external databases or tools. Answer truthfully based on your internal knowledge.\n"
            f"The current year is {current_year}.\n"
        )
        
    def run(self, user_input: str) -> str:
        logger.log_event("CHATBOT_START", {"input": user_input, "model": self.llm.model_name})
        system_prompt = self.get_system_prompt()
        prompt = f"User: {user_input}\nAssistant:"
        
        # We pass system prompt directly through LLM Provider generate
        result = self.llm.generate(prompt, system_prompt=system_prompt)
        answer = result["content"].strip()
        
        logger.log_event("CHATBOT_END", {"response": answer})
        return answer
