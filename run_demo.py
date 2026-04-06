import os
import sys
from dotenv import load_dotenv

load_dotenv()

from src.agent.agent import ReActAgent
from src.agent.chatbot import BasicChatbot

from src.tools.search_product import TOOL_SPEC as search_spec
from src.tools.get_product_detail import TOOL_SPEC as detail_spec
from src.tools.check_inventory import TOOL_SPEC as inventory_spec
from src.tools.compare_product import TOOL_SPEC as compare_spec
from src.tools.web_search_product import TOOL_SPEC as web_search_spec
from src.tools.read_web_page import TOOL_SPEC as read_web_page_spec

def get_llm():
    provider_type = os.getenv("DEFAULT_PROVIDER", "local").lower()
    
    if provider_type in ("google", "gemini"):
        from src.core.gemini_provider import GeminiProvider
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key or api_key == "your_gemini_api_key_here":
            print("❌ Error: Please set your GEMINI_API_KEY in the .env file.")
            sys.exit(1)
        return GeminiProvider(api_key=api_key)
        
    elif provider_type == "openai":
        from src.core.openai_provider import OpenAIProvider
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key == "your_openai_api_key_here":
            print("❌ Error: Please set your OPENAI_API_KEY in the .env file.")
            sys.exit(1)
        return OpenAIProvider(api_key=api_key)
        
    else:
        from src.core.local_provider import LocalProvider
        model_path = os.getenv("LOCAL_MODEL_PATH", "./models/gemma-4-E4B-it-Q4_1.gguf")
        return LocalProvider(model_path=model_path)

def main():
    print("⏳ Initializing LLM...")
    llm = get_llm()
    print(f"✅ Model loaded: {llm.model_name}\n")

    tools = [search_spec, detail_spec, inventory_spec, compare_spec, web_search_spec, read_web_page_spec]
    
    agent = ReActAgent(llm, tools)
    chatbot = BasicChatbot(llm)

    print("=" * 50)
    print("  🚀 DEMO: Chatbot Baseline vs ReAct Agent")
    print("=" * 50)
    print("Type 'quit' to exit.")

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye! 👋")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("Bye! 👋")
            break

        print("\n--- [ Baseline Chatbot (No Tools) ] ---")
        chatbot_response = chatbot.run(user_input)
        print(f"🤖 Bot: {chatbot_response}")

        print("\n--- [ ReAct Agent (With Tools) ] ---")
        agent_response = agent.run(user_input)
        print(f"🤖 Agent: {agent_response}")

if __name__ == "__main__":
    main()
