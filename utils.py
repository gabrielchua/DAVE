"""
utils.py
"""
import base64
from PIL import ImageFile
from typing_extensions import override

import streamlit as st
from openai import (
    OpenAI,
    AssistantEventHandler
    )

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

def render_custom_css() -> None:
    """
    Applies custom CSS
    """
    st.markdown("""
            <style>
            #MainMenu {visibility: hidden}
            #header {visibility: hidden}
            #footer {visibility: hidden}
            .block-container {
                padding-top: 2rem;
                padding-bottom: 2rem;
                padding-left: 3rem;
                padding-right: 3rem;
                }
                
            </style>
            """, unsafe_allow_html=True)

def moderation_endpoint(text) -> bool:
    """
    Returns true if the text is NSFW
    """
    response = client.moderations.create(input=text)
    return response.results[0].flagged

def is_nsfw(text) -> bool:
    """
    Returns true if the text is not a question
    """
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Is the given text NSFW? If yes, return `1``, else return `0`."},
            {"role": "user", "content": text},
        ],
        max_tokens=1,
        logit_bias={"15": 100, "16": 100},
    )
    output = response.choices[0].message.content
    return int(output)

def is_not_question(text) -> bool:
    """
    Returns true if the text is not a question
    """
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Is the given text a question? If yes, return `1``, else return `0`."},
            {"role": "user", "content": text},
        ],
        max_tokens=1,
        logit_bias={"15": 100, "16": 100},
    )
    output = response.choices[0].message.content
    return int(output)

class EventHandler(AssistantEventHandler):
    """
    Event handler for the assistant stream
    """
    @override
    def on_text_created(self, text) -> None:
        """
        Handler for when a text is created
        """
        # Create a new text box
        st.session_state.text_boxes.append(st.empty())
        # Retrieve the newly created text box and empty it
        st.session_state.text_boxes[-1].empty()
        # Insert the text into the last element in assistant text list
        st.session_state.assistant_text[-1] += "**> 🕵️ Dave:** \n\n "
        # Display the text in the newly created text box
        st.session_state.text_boxes[-1].info("".join(st.session_state["assistant_text"][-1]))
      
    @override
    def on_text_delta(self, delta, snapshot):
        """
        Handler for when a text delta is created
        """
        # Clear the latest text box
        st.session_state.text_boxes[-1].empty()
        # If there is text written, add it to latest element in the assistant text list
        if delta.value:
            st.session_state.assistant_text[-1] += delta.value
        # Re-display the full text in the latest text box
        st.session_state.text_boxes[-1].info("".join(st.session_state["assistant_text"][-1]))

    def on_text_done(self, text):
        """
        Handler for when text is done
        """
        # Create new text box and element in the assistant text list
        st.session_state.text_boxes.append(st.empty())
        st.session_state.assistant_text.append("")

    def on_tool_call_created(self, tool_call):
        """
        Handler for when a tool call is created
        """
        # Create new text box, which will contain code
        st.session_state.text_boxes.append(st.empty())
        # Create a new element in the code input list
        st.session_state.code_input.append("")
          
    def on_tool_call_delta(self, delta, snapshot):
        """
        Handler for when a tool call delta is created
        """
        if delta.type == 'code_interpreter':

            # Code writen by the assistant to be executed
            if delta.code_interpreter.input:
                # Go to the last text box
                with st.session_state.text_boxes[-1]:
                    # Check if a code box for this accompanying text box index exists
                    if f"code_box_{len(st.session_state.text_boxes)}" not in st.session_state:
                        # Nest the code in an expander
                        st.session_state[f"code_expander_{len(st.session_state.text_boxes)}"] = st.status("**💻 Code**", expanded=True)
                        # Create a code box
                        st.session_state[f"code_box_{len(st.session_state.text_boxes)}"] = st.session_state[f"code_expander_{len(st.session_state.text_boxes)}"].empty()

                # Clear the code box
                st.session_state[f"code_box_{len(st.session_state.text_boxes)}"].empty()
                # If there is code written, add it to the code input
                if delta.code_interpreter.input:
                    st.session_state.code_input[-1] += delta.code_interpreter.input
                # Re-display the full code in the code box
                st.session_state[f"code_box_{len(st.session_state.text_boxes)}"].code(st.session_state.code_input[-1])

            # Output from the code executed by code interpreter
            if delta.code_interpreter.outputs:
                for output in delta.code_interpreter.outputs:
                    if output.type == "logs":
                        try:
                            st.session_state[f"code_expander_{len(st.session_state.text_boxes)}"].update(state="complete", expanded=False)
                        except KeyError:
                            pass
                        # Create a new element in the code input list, which is for the next code input
                        st.session_state.code_input.append("")
                        # Create a new text box, which is for the code output
                        st.session_state.text_boxes.append(st.empty())
                        # Nest the code output in an expander
                        st.session_state.text_boxes[-1] = st.expander(label="**🔎 Output**")
                        # Create a new element in the code output list
                        st.session_state.code_output.append("")
                        # Clear the latest text box which is for the code output
                        st.session_state.text_boxes[-1].empty()
                        # Add the logs to the code output
                        st.session_state.code_output[-1] += f"\n\n{output.logs}"
                        # Display the code output
                        st.session_state.text_boxes[-1].code(st.session_state.code_output[-1])

    def on_tool_call_done(self, tool_call):
        """
        Handler for when a tool call is done
        """
        # Create a new element in the code input list
        st.session_state.code_input.append("")
        # Create a new element in the code output list
        st.session_state.code_output.append("")
        # Create a new element in the assistant text list
        st.session_state.assistant_text.append("")
        # Create a new text box for the next operation
        st.session_state.text_boxes.append(st.empty())

    def on_image_file_done(self, image_file: ImageFile):
        """
        Handler for when an image file is done
        """
        # Download file from OpenAI
        image_data = client.files.content(image_file.file_id)
        img_name = image_file.file_id

        # Save file
        image_data_bytes = image_data.read()
        with open(f"images/{img_name}.png", "wb") as file:
            file.write(image_data_bytes)

        # Open file and encode as data
        file_ = open(f"images/{img_name}.png", "rb")
        contents = file_.read()
        data_url = base64.b64encode(contents).decode("utf-8")
        file_.close()

        # Create new text box
        st.session_state.text_boxes.append(st.empty())
        st.session_state.assistant_text.append("")
        
        # Display image in textbox
        image_html = f'<p align="center"><img src="data:image/png;base64,{data_url}" width=600></p>'
        st.session_state.text_boxes[-1].markdown(image_html, unsafe_allow_html=True)

        # Create new text box
        st.session_state.assistant_text.append("")
        st.session_state.text_boxes.append(st.empty())
        
        # Delete file from OpenAI
        client.files.delete(image_file.file_id)
      
    def on_timeout(self):
        """
        Handler for when the api call times out
        """
        st.error("The api call timed out.")
        st.stop()

    def on_exception(self, exception: Exception):
        """
        Handler for when an exception occurs
        """
        st.error(f"An error occurred: {exception}")
        st.stop()
