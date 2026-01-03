import streamlit as st
from agent import Agent

st.set_page_config(page_title="Claude Code Agent", page_icon="🤖")

st.title("🤖 Claude Code Agent")
st.markdown("An agent that can execute Python code to help solve your tasks.")

# Initialize session state for the agent and history
if "agent" not in st.session_state:
    st.session_state.agent = Agent()
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("What would you like me to do?"):
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Generate assistant response
    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        full_response = ""
        
        # We'll use a container for tool status updates
        status_container = st.container()
        
        for chunk in st.session_state.agent.process_message(prompt):
            if chunk["type"] == "text_delta":
                full_response += chunk["text"]
                response_placeholder.markdown(full_response + "▌")
            
            elif chunk["type"] == "tool_start":
                with status_container:
                    with st.status(f"Running tool: {chunk['name']}...", expanded=True) as status:
                        st.session_state.current_status = status
            
            elif chunk["type"] == "tool_executing":
                if "current_status" in st.session_state:
                    st.session_state.current_status.write("Executing code:")
                    st.session_state.current_status.code(chunk["code"], language="python")
            
            elif chunk["type"] == "tool_result":
                if "current_status" in st.session_state:
                    result = chunk["result"]
                    if result["stdout"]:
                        st.session_state.current_status.write("Output:")
                        st.session_state.current_status.code(result["stdout"])
                    if result["stderr"]:
                        st.session_state.current_status.error(f"Error: {result['stderr']}")
                    st.session_state.current_status.update(label="Tool execution complete", state="complete", expanded=False)

        response_placeholder.markdown(full_response)
        st.session_state.messages.append({"role": "assistant", "content": full_response})

