from google import genai
from google.genai import types
from pydantic import BaseModel # <-- 1. Import Pydantic

client = genai.Client()

class PropertyAgent:
    # 2. Add 'response_schema' as an optional parameter
    def __init__(self, name: str, role: str, tool_manager, response_schema: type[BaseModel] | None = None):
        self.name = name
        self.role = role
        self.tool_manager = tool_manager 
        self.response_schema = response_schema # <-- Save it
        self.memory = []
        
    async def chat(self, user_message: str) -> str:
        print(f"\nUSER: \"{user_message}\"")
        self.memory.append(types.Content(role="user", parts=[types.Part.from_text(text=user_message)]))
        
        iteration_count = 0
        max_iterations = 4
        gemini_tools_menu = await self.tool_manager.get_menu_for_gemini()
        
        while iteration_count < max_iterations:
            print(f"Iteration number: {iteration_count}")
            # 3. Build the config
            config = types.GenerateContentConfig(
                system_instruction=f"You are a {self.role} named {self.name}. Use your tools to assist the user. ONLY output the requested JSON schema if one is provided.",
                tools=gemini_tools_menu,
                temperature=0.0
            )
            
            # 4. If a schema was provided, force the model into JSON mode!
            if self.response_schema:
                config.response_mime_type = "application/json"
                config.response_schema = self.response_schema
            
            response = client.models.generate_content(
                model='gemini-3.1-flash-lite-preview',
                contents=self.memory,
                config=config
            )
            
            # ... (Keep the rest of your tool execution logic exactly the same) ...
            if response.candidates and response.candidates[0].content:
                self.memory.append(response.candidates[0].content)
            
            if response.function_calls:
                iteration_count += 1
                fc = response.function_calls[0]
                print(f"[{self.name}'s Brain] -> Decided to use '{fc.name}'")
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