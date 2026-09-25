import asyncio
from genio_server.core.agent_loop import AgentLoop

async def chat():
    agent = AgentLoop(session_id="azmi")
    print("\n" + "="*50)
    print("🇹🇳 جينيو حاضر معاك! اكتب سؤالك واضغط Enter (أو اكتب 'exit' للخروج):")
    print("="*50 + "\n")
    
    while True:
        try:
            user_input = input("أنت: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit", "sortir"]:
                print("إلى اللقاء يا عزمي!")
                break
            
            print("\nجينيو يفكّر...", end="\r")
            async for event in agent.run(user_input):
                if isinstance(event, dict) and event.get("type") == "answer":
                    print(f"\nجينيو: {event.get('text')}\n")
        except (KeyboardInterrupt, EOFError):
            print("\nتم إغلاق الجلسة.")
            break

if __name__ == "__main__":
    asyncio.run(chat())
