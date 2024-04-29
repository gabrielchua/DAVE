"""
utils.py
"""
import os
import base64
import hmac
import re
from PIL import ImageFile
from typing import Tuple
from typing_extensions import override

import streamlit as st
from openai import (
    OpenAI,
    AssistantEventHandler
    )
from openai.types.beta.threads import Text, TextDelta
from openai.types.beta.threads.runs import ToolCall, ToolCallDelta

# Get secrets
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", st.secrets["OPENAI_API_KEY"])

# Config
LAST_UPDATE_DATE = "2024-04-08"

# Initialise the OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

def render_custom_css() -> None:
    """
    Applies custom CSS
    """
    st.html("""
            <style>
                #MainMenu {visibility: hidden}
                #header {visibility: hidden}
                #footer {visibility: hidden}
                .block-container {
                    padding-top: 3rem;
                    padding-bottom: 2rem;
                    padding-left: 3rem;
                    padding-right: 3rem;
                    }
            </style>
            """)

def initialise_session_state():
    """
    Initialise session state variables
    """
    if "file" not in st.session_state:
        st.session_state.file = None

    if "assistant_text" not in st.session_state:
        st.session_state.assistant_text = [""]

    for session_state_var in ["file_uploaded", "read_terms"]:
        if session_state_var not in st.session_state:
            st.session_state[session_state_var] = False

    for session_state_var in ["code_input", "code_output"]:
        if session_state_var not in st.session_state:
            st.session_state[session_state_var] = []

def moderation_endpoint(text) -> bool:
    """
    Checks if the text is triggers the moderation endpoint

    Args:
    - text (str): The text to check

    Returns:
    - bool: True if the text is flagged
    """
    response = client.moderations.create(input=text)
    return response.results[0].flagged

def is_nsfw(text) -> bool:
    """
    Checks if the text is nsfw.

    Args:
    - text (str): The text to check

    Returns:
    - bool: True if the text is nsfw
    """
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Is the given text NSFW? If yes, return `1``, else return `0`."},
            {"role": "user", "content": text},
        ],
        max_tokens=1,
        logit_bias={"15": 100,
                    "16": 100},
    )
    output = response.choices[0].message.content
    return bool(output)

def is_not_question(text) -> bool:
    """
    Checks if the text is not a question

    Args:
    - text (str): The text to check

    Returns:
    - bool: True if the text is not a question
    """
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Is the given text a question? If yes, return `1``, else return `0`."},
            {"role": "user", "content": text},
        ],
        max_tokens=1,
        logit_bias={"15": 100,
                    "16": 100},
    )
    output = response.choices[0].message.content
    return bool(output)

def delete_files(file_id_list: list[str]) -> None:
    """
    Delete the file(s) uploaded
    
    Args:
    - file_id_list (list[str]): List of file ids to delete
    """
    for file_id in file_id_list:
        client.files.delete(file_id)
        print(f"Deleted file: \t {file_id}")

def delete_thread(thread_id) -> None:
    """
    Delete the thread
    
    Args:
    - thread_id (str): The id of the thread to delete
    """
    client.beta.threads.delete(thread_id)
    print(f"Deleted thread: \t {thread_id}")

def remove_links(text: str) -> str:
    """
    Remove links from the text

    Args:
    - text (str): The text to remove markdown links from

    Returns:
    - str: The text with the links removed
    """
    # Pattern to match Markdown links: [Link text](URL)
    link_pattern = r'\[.*?\]\(.*?\)'
    # Pattern to match lines starting with list item indicators (unordered or ordered)
    list_item_pattern = r'^(\s*(\*|-|\d+\.)\s).*'
    # Combine both patterns to identify list items containing links
    combined_pattern = rf'({list_item_pattern}.*?{link_pattern}.*?$)|{link_pattern}'
    # Replace the matching content with an empty string
    # The MULTILINE flag is used to allow ^ to match the start of each line
    cleaned_text = re.sub(combined_pattern, '', text, flags=re.MULTILINE)
    return cleaned_text

def retrieve_messages_from_thread(thread_id: str) -> list[str]:
    """
    Retrieve messages from the thread

    Args:
    - thread_id (str): The id of the thread

    Returns:
    - list[str]: List of assistant messages
    """
    thread_messages = client.beta.threads.messages.list(thread_id)
    assistant_messages = []
    for message in thread_messages.data:
        if message.role == "assistant":
            assistant_messages.append(message.id)
    return assistant_messages

def retrieve_assistant_created_files(message_list: list[str]) -> list[str]:
    """
    Retrieve the assistant-created files

    Args:
    - message_list (list[str]): List of assistant messages

    Returns:
    - list[str]: List of assistant-created file ids
    """
    assistant_created_file_ids = []
    for message_id in message_list:
        message = client.beta.threads.messages.retrieve(
            message_id=message_id,
            thread_id=st.session_state.thread_id,
        )

        # Retrieve the attachments from the message, and the file ids from the attachments
        created_file_id = [file.file_id for file in message.attachments]
        for file_id in created_file_id:
            assistant_created_file_ids.append(file_id)        

        # message_files = client.beta.threads.messages.files.list(
        #     thread_id=st.session_state.thread_id,
        #     message_id=message_id)
        # for file in message_files.data:
        #     assistant_created_file_ids.append(file.id)

    return assistant_created_file_ids

@st.experimental_fragment
def render_download_files(file_id_list: list[str]) -> Tuple[list[bytes], list[str]]:
    """
    Download the files, renders a download button for each file, and returns the downloaded files

    Args:
    - file_id_list (list[str]): List of file ids to download

    Returns:
    - downloaded_files (list[object]): List of downloaded files
    - file_names (list[str]): List of file names
    """
    downloaded_files = []
    file_names = []
    if len(file_id_list) > 0:
        st.markdown("### 📂  **Downloadable Files**")
        for file_id_num, file_id in enumerate(file_id_list):
            try: 
                file_data = client.files.content(file_id)
                file = file_data.read()
                file_name = client.files.retrieve(file_id).filename
                file_name = os.path.basename(file_name)

                # # if file_name is `.csv`
                # if file_name.endswith(".csv"):
                #     try:
                #         with open(f"static/{file_name}", "wb") as f:
                #             f.write(file)
                #     except:
                #         # Convert bytes to string
                #         csv_str = file.decode('utf-8')
                #         csv_file = io.StringIO(csv_str)            
                #         df = pd.read_csv(csv_file)
                #         df.to_csv(f"static/{file_name}", index=False)
                # elif file_name.endswith(".png"):
                #     with open(f"static/{file_name}", "wb") as f:
                #         f.write(file)
                # st.write(f"- [{file_name}](static/{file_name})")

                # Store the downloaded file and its name
                downloaded_files.append(file)
                file_names.append(file_name)

                # Display the download button
                st.download_button(label=f"{file_name}",
                                    data=file,
                                    file_name=file_name,
                                    mime="text/csv")
                                    
            except: 
                # Display the download button
                file = st.session_state.download_files[file_id_num]
                file_name = st.session_state.download_file_names[file_id_num]
                st.download_button(label=f"{file_name}",
                                    data=file,
                                    file_name=file_name,
                                    mime="text/csv")
    
    return downloaded_files, file_names
    

class EventHandler(AssistantEventHandler):
    """
    Event handler for the assistant stream
    """
    @override
    def on_text_created(self, text: Text) -> None:
        """
        Handler for when a text is created
        """
        # This try-except block will update the earlier expander for code to complete.
        # Note the indexing. We are updating the x-1 textbox where x is the current textbox.
        # Note how `on_tool_call_done` creates a new textbook (which is the x_th textbox, so we want to access the x-1_th)
        # This is to address an edge case where code is executed, but there is no output textbox (e.g. a graph is created)
        try:
            st.session_state[f"code_expander_{len(st.session_state.text_boxes) - 1}"].update(state="complete", expanded=False)
        except KeyError:
            pass

        # Create a new text box
        st.session_state.text_boxes.append(st.empty())
        # Insert the text into the last element in assistant text list
        st.session_state.assistant_text[-1] += "**> 🕵️ DAVE:** \n\n "
        # Remove links from the text
        st.session_state.assistant_text[-1] = remove_links(st.session_state.assistant_text[-1])
        # Display the text in the newly created text box
        st.session_state.text_boxes[-1].info("".join(st.session_state["assistant_text"][-1]))
      
    @override
    def on_text_delta(self, delta: TextDelta, snapshot: Text):
        """
        Handler for when a text delta is created
        """
        # Clear the latest text box
        st.session_state.text_boxes[-1].empty()
        # If there is text written, add it to latest element in the assistant text list
        if delta.value:
            st.session_state.assistant_text[-1] += delta.value
        # Remove links from the text
        st.session_state.assistant_text[-1] = remove_links(st.session_state.assistant_text[-1])
        # Re-display the full text in the latest text box
        st.session_state.text_boxes[-1].info("".join(st.session_state["assistant_text"][-1]))

    def on_text_done(self, text: Text):
        """
        Handler for when text is done
        """
        # Create new text box and element in the assistant text list
        st.session_state.text_boxes.append(st.empty())
        st.session_state.assistant_text.append("")

    def on_tool_call_created(self, tool_call: ToolCall):
        """
        Handler for when a tool call is created
        """
        # Create new text box, which will contain code
        st.session_state.text_boxes.append(st.empty())
        # Create a new element in the code input list
        st.session_state.code_input.append("")
          
    def on_tool_call_delta(self, delta: ToolCallDelta, snapshot: ToolCallDelta):
        """
        Handler for when a tool call delta is created
        """
        if delta.type == "code_interpreter" and delta.code_interpreter:

            # Code writen by the assistant to be executed
            if delta.code_interpreter.input:
                # Go to the last text box
                with st.session_state.text_boxes[-1]:
                    # Check if a code box for this accompanying text box index exists
                    if f"code_box_{len(st.session_state.text_boxes)}" not in st.session_state:
                        # Nest the code in an expander
                        st.session_state[f"code_expander_{len(st.session_state.text_boxes)}"] = st.status("**💻 Code**", expanded=True)
                        # Create an empty container which is the placeholder for the code box
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
                        # This try-except block will update the earlier expander for code to complete.
                        # Note the indexing, as we have not yet created a new text box for the code output.
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

    def on_tool_call_done(self, tool_call: ToolCall):
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
        
        # # Display image in textbox
        image_html = f'<p align="center"><img src="data:image/png;base64,{data_url}" width=600></p>'
        st.session_state.text_boxes[-1].html(image_html)

        # st.session_state.text_boxes[-1].image(f"images/{img_name}.png", width=600)

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

    # def on_exception(self, exception: Exception):
    #     """
    #     Handler for when an exception occurs
    #     """
    #     st.error(f"An error occurred: {exception}")
    #     st.stop()
