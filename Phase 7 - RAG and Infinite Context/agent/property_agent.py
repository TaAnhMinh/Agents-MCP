from google import genai
from google.genai import types

# Initialize Gemini here
client = genai.Client()

class PropertyAgent:
    def __init__(self, name: str, role: str, tool_manager):
        self.name = name
        self.role = role
        self.tool_manager = tool_manager 
        self.memory = []
        
    async def chat(self, user_message: str) -> str:
        print(f"\nUSER: \"{user_message}\"")
        self.memory.append(types.Content(role="user", parts=[types.Part.from_text(text=user_message)]))
        
        iteration_count = 0
        max_iterations = 4
        gemini_tools_menu = await self.tool_manager.get_menu_for_gemini()
        
        while iteration_count < max_iterations:
            config = types.GenerateContentConfig(
                system_instruction=f"You are a {self.role} named {self.name}. Use your tools to assist the user.",
                tools=gemini_tools_menu,
                temperature=0.0
            )
            
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=self.memory,
                config=config
            )
            
            if response.candidates and response.candidates[0].content:
                self.memory.append(response.candidates[0].content)
            
            if response.function_calls:
                iteration_count += 1
                fc = response.function_calls[0]
                print(f"[{self.name}'s Brain] -> Decided to use '{fc.name}'")
                print(f"[{self.name}'s Brain] -> Decided to use '{fc.args}'")
                raw_text_result = await self.tool_manager.execute(fc.name, fc.args)
                
                self.memory.append(
                    types.Content(
                        role="user",
                        parts=[types.Part.from_function_response(name=fc.name, response={"result": raw_text_result})]
                    )
                )
                
            elif response.text:
                return response.text
                
        return "[SYSTEM ERROR] Loop limit reached."