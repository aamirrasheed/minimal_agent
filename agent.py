import sys
import json
import os
import subprocess
import tempfile
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()
client = Anthropic()

exec_code_tool_definition = {
    "name": "exec_code",
    "description": "This tool enables execution of Python 3.11 code. You will receive stdout, stderr, and return_code in the tool result. The code will be executed on a Macbook with minimal access to a filesystem. You may never write code that deletes files",
    "input_schema": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Code to execute"
            },
        },
        "required": ["code"],
    }
}

def exec_code(code):
    # Write the code to a temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as temp_file:
        temp_file.write(code)
        temp_file_path = temp_file.name

    try:
        # Run the subprocess to execute the python code
        proc = subprocess.Popen(
            [sys.executable, temp_file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = proc.communicate()
        return_code = proc.returncode
    finally:
        try:
            os.remove(temp_file_path)
        except Exception:
            pass

    return {
        "stdout": stdout if stdout else "",
        "stderr": stderr if stderr else "",
        "return_code": return_code if return_code else "",
    }


class Agent:
    def __init__(self, model="claude-sonnet-4-5", system_prompt=None):
        self.client = Anthropic()
        self.model = model
        self.system_prompt = system_prompt or "Ensure all output uses only terminal-safe characters. Avoid problematic Unicode that may not render, and avoid markdown since that adds character complexity."
        self.messages = []

    def process_message(self, prompt):
        self.messages.append({"role": "user", "content": prompt})
        
        while True:  # tool use loop
            stream = self.client.beta.messages.create(
                model=self.model,
                max_tokens=2048,
                system=self.system_prompt,
                messages=self.messages,
                stream=True,
                tools=[exec_code_tool_definition]
            )

            assistant_message_content = []
            current_content_block = {}
            stop_reason = None
            
            for event in stream:
                if event.type == 'message_start':
                    yield {"type": "message_start"}

                elif event.type == 'content_block_start':
                    current_content_block['type'] = event.content_block.type
                    if event.content_block.type == 'tool_use':
                        current_content_block['id'] = event.content_block.id
                        current_content_block['name'] = event.content_block.name
                        yield {"type": "tool_start", "name": event.content_block.name}
                    
                elif event.type == 'content_block_delta':
                    if current_content_block['type'] == 'text':
                        text = event.delta.text
                        current_content_block['text'] = current_content_block.get('text', '') + text
                        yield {"type": "text_delta", "text": text}
                    
                    elif current_content_block['type'] == 'tool_use':
                        current_content_block['input'] = current_content_block.get('input', '') + event.delta.partial_json

                elif event.type == 'content_block_stop':
                    if current_content_block['type'] == 'tool_use':
                        parsed_json = json.loads(current_content_block['input'])
                        current_content_block['input'] = parsed_json
                    
                    assistant_message_content.append(current_content_block)
                    current_content_block = {}

                elif event.type == 'message_delta':
                    if event.delta.stop_reason == "tool_use":
                        stop_reason = 'tool_use'

                elif event.type == 'message_stop':
                    yield {"type": "message_stop"}

            self.messages.append({
                "role": "assistant", 
                "content": assistant_message_content
            })

            if stop_reason == 'tool_use':
                # execute tool
                code = assistant_message_content[-1]['input']['code']
                yield {"type": "tool_executing", "code": code}
                result = exec_code(code)
                yield {"type": "tool_result", "result": result}

                tool_use_id = assistant_message_content[-1]['id']
                user_message_content = {
                    "type": "tool_result", 
                    "tool_use_id": tool_use_id,
                    "content": f"stdout: {result['stdout']} stderr: {result['stderr']} return_code: {result['return_code']}"
                }
                self.messages.append({
                    "role": "user", 
                    "content": [user_message_content]
                })
            else:
                break

def main():
    agent = Agent()
    try:
        while True:
            prompt = input("===You:===\n")
            print("===Claude:===")
            
            for chunk in agent.process_message(prompt):
                if chunk["type"] == "text_delta":
                    print(chunk["text"], end='', flush=True)
                elif chunk["type"] == "tool_start":
                    print(f"...Executing {chunk['name']} tool...")
                elif chunk["type"] == "message_stop":
                    print()
    except (EOFError, KeyboardInterrupt):
        print("\nGoodbye!")
    except Exception as e:
        print(f"\nAn error occurred: {e}")

if __name__ == "__main__":
    main()
