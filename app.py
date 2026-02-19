import asyncio

import gradio as gr
from agents import gen_trace_id, trace
from dotenv import load_dotenv

from scholarship_agents.schorlarship_agent import chat

load_dotenv(override=True)


def create_gradio_interface():
    with gr.Blocks(theme=gr.themes.Soft()) as interface:

        gr.Markdown("# 🎓 FindMyScholarship AI")

        chatbot = gr.Chatbot(label="📋 Funding Search Results", height=500)
        query = gr.Textbox(
            label="🔍 What funding are you looking for?",
            placeholder="e.g., PhD funding in machine learning at University of Oregon or UK universities"
        )
        search_btn = gr.Button("🚀 Search Funding")

        # Prevent concurrent runs (double submit / double click) from triggering repeated crawling/analyzing.
        run_lock = asyncio.Lock()

        async def run_query(message, history):
            async with run_lock:
                trace_id = gen_trace_id()
                with trace("Scholarship Search", trace_id=trace_id):
                    result = await chat(message, history)
                history.append((message, result))
                return history, ""

        search_btn.click(run_query, [query, chatbot], [chatbot, query])
        query.submit(run_query, [query, chatbot], [chatbot, query])

    return interface

demo = create_gradio_interface()

if __name__ == "__main__":
    demo.launch()
