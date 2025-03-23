import os
import re
import shutil
import tempfile
import json

import gradio as gr
from dotenv import load_dotenv
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader, PyMuPDFLoader
from openai import OpenAI

from prompts import system_prompt

load_dotenv()

# Constants
MODEL = "gpt-4o-mini"
SESSION_FILE = "session_data.json"

# Initialize OpenAI Model
openai_model = OpenAI()


class SessionManager:
    """Handles loading and saving session data."""

    @staticmethod
    def save(data):
        """Saves white paper session data to a file."""
        try:
            with open(SESSION_FILE, 'w', encoding='utf-8') as file:
                json.dump({"messages": data}, file, ensure_ascii=False, indent=4)
            return "Session saved successfully!"
        except Exception as e:
            return f"Error saving session: {e}"

    @staticmethod
    def load():
        """Loads white paper session data from a file."""
        try:
            with open(SESSION_FILE, 'r', encoding='utf-8') as file:
                session_data = json.load(file)
                return session_data.get('messages', {})
        except FileNotFoundError:
            return "No saved session found."
        except json.JSONDecodeError:
            return "Error: Corrupted session file."


class DocumentProcessor:
    """Handles document uploading, cleaning, and processing."""

    @staticmethod
    def clean_text(text):
        """Cleans extracted text by removing unwanted spaces and special characters."""
        text = re.sub(r'\s+', ' ', text)  # Normalize spaces
        text = re.sub(r'[^a-zA-Z0-9.,!?;:\'"()\s]', '', text)  # Remove unwanted characters
        return text.strip()

    @staticmethod
    def load_document(file):
        """Loads and processes text from PDF or TXT documents."""
        if file is None:
            return "No file uploaded."

        temp_file_path = os.path.join(tempfile.gettempdir(), os.path.basename(file.name))
        shutil.copy(file.name, temp_file_path)

        loader = TextLoader(temp_file_path) if temp_file_path.endswith(".txt") else PyMuPDFLoader(temp_file_path)
        docs = loader.load()

        # Split text into smaller sections
        text_splitter = RecursiveCharacterTextSplitter(separators=["\n\n", "\n"])
        chunks = text_splitter.split_documents(docs)

        cleaned_text = "\n\n".join(DocumentProcessor.clean_text(chunk.page_content) for chunk in chunks)
        os.remove(temp_file_path)

        return cleaned_text


class WhitePaperAssistant:
    """Handles processing, chat interaction, and system message generation."""

    def __init__(self):
        self.white_paper = SessionManager.load()  # Load existing session data

    def process_paper(self, title, description, paper):
        """Processes and formats research paper data."""
        self.white_paper = {
            'title': title,
            'description': description,
            'content': DocumentProcessor.load_document(paper)
        }
        SessionManager.save(self.white_paper)
        return f"""# {title}\n\n## Description\n{description}\n\n## Content\n{self.white_paper['content']}"""

    def get_system_message(self):
        """Generates the system message for chat context."""
        return system_prompt.format(
            title=self.white_paper.get('title', 'No Title'),
            description=self.white_paper.get('description', 'No Description'),
            content=self.white_paper.get('content', 'No Content')
        )

    def chat(self, message, history):
        """Handles chat interaction with OpenAI model."""
        system_message = self.get_system_message()
        messages = [{"role": "system", "content": system_message}] + history + [{"role": "user", "content": message}]
        stream = openai_model.chat.completions.create(model=MODEL, messages=messages, stream=True)

        response = ""
        for chunk in stream:
            response += chunk.choices[0].delta.content or ''
            yield response


# UI Setup
assistant = WhitePaperAssistant()

def build_setup_ui():
    """Creates UI for uploading and processing research papers."""
    with gr.Blocks(title="Research Paper Setup") as setup_ui:
        gr.Markdown("# Upload & Process Your Research Paper 📂")

        with gr.Row():
            title = gr.Textbox(label="Paper Title", placeholder="Enter research paper title")
            description = gr.Textbox(label="Short Description", placeholder="Enter a brief description")

        paper = gr.File(label="Upload Paper (PDF/TXT)", file_types=['.pdf', '.txt'])
        output = gr.Markdown("Processed content will appear here...")

        with gr.Row():
            submit_btn = gr.Button("Submit", variant="primary")
            clear_btn = gr.Button("Clear", variant="secondary")

        submit_btn.click(fn=assistant.process_paper, inputs=[title, description, paper], outputs=[output])
        clear_btn.click(fn=lambda: "Data cleared!", outputs=[output])

    return setup_ui


def build_chat_ui():
    """Creates the AI Chat interface."""
    with gr.Blocks(title="AI Chatbot") as chat_ui:
        gr.Markdown("# 🤖 Chat with Your Research Paper")
        gr.ChatInterface(fn=assistant.chat, type="messages")

    return chat_ui


# Launch the App
setup_tab = build_setup_ui()
chat_tab = build_chat_ui()

gr.TabbedInterface([chat_tab, setup_tab], ["AI Chat", "Setup"]).launch()
