"""
AFHSync Smart Chatbot - Main Entry Point
"""

import logging
from chatbot import AFHSyncBot

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main interactive test mode"""
    print("=" * 60)
    print("AFHSync Smart Chatbot - Interactive Test Mode")
    print("=" * 60)
    print("\nCommands:")
    print("  • Type your messages normally")
    print("  • 'exit' or 'quit' - Exit the program")
    print("  • 'restart' - Restart conversation")
    print("  • 'debug' - Show current state and data")
    print("=" * 60)
    print()

    try:
        bot = AFHSyncBot()
        
        print(bot.process_message("start"))
        print()
        
        while True:
            try:
                user_input = input("You: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ['exit', 'quit']:
                    print("\n👋 Goodbye! Thank you for using AFHSync.")
                    break
                
                if user_input.lower() == 'debug':
                    print(f"\n🔍 Debug Info:")
                    print(f"State: {bot.state.value}")
                    print(f"Data keys: {list(bot.data.keys())}")
                    print(f"Last activity: {bot.last_activity}")
                    print()
                    continue
                
                response = bot.process_message(user_input)
                print(f"\nBot: {response}\n")
            
            except KeyboardInterrupt:
                print("\n\n⚠️  Interrupted. Type 'exit' to quit or continue chatting.")
                continue

    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"\n❌ Fatal error: {e}")


if __name__ == "__main__":
    main()