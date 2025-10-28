import gradio as gr
from dotenv import load_dotenv
#from scholarship_manager import SchorlashipManager
from schorlarship_agent import chat
load_dotenv(override=True)

# async def run(query: str):
#     async for chunk in SchorlashipManager().run(query):
#         yield chunk

# with gr.Blocks(theme=gr.themes.Default(primary_hue="sky")) as ui:
#     gr.Markdown("# Find My Schorlaship")
#     query_textbox = gr.Textbox(
#                      label="🔍 What funding are you looking for?",
#                      placeholder="e.g., 'PhD funding in computer science at MIT and Stanford' or 'Master's scholarships for international students in UK universities'",
#                      lines=3,
#                      max_lines=3
#                  )
#     run_button = gr.Button("Run", variant="primary")
#     report = gr.Markdown(label="Report")
    
#      # 🔥 Enable streaming updates
#     run_button.click(run, inputs=query_textbox, outputs=report, api_name="run")
#     query_textbox.submit(run, inputs=query_textbox, outputs=report)

# ui.launch(inbrowser=True)
gr.ChatInterface(chat, type="messages").launch()





















# # === Gradio UI Setup ===
# def create_gradio_interface():
#     with gr.Blocks(
#         title="FindMyScholarship AI",
#         theme=gr.themes.Soft(),
#         css="""
#         .gradio-container {
#             max-width: 1200px !important;
#         }
#         .results-box {
#             max-height: 600px;
#             overflow-y: auto;
#             padding: 20px;
#             border: 1px solid #e0e0e0;
#             border-radius: 10px;
#             background: #fafafa;
#         }
#         """
#     ) as interface:
#         gr.Markdown(
#             """
#             # 🎓 FindMyScholarship AI
            
#             **Discover funding opportunities for your academic journey!**
            
#             This AI-powered tool helps you find scholarships, PhD funding, master's studentships, and other financial support opportunities from university websites worldwide.
            
#             ### How to use:
#             1. Describe what you're looking for (field of study, degree level, preferred universities/countries)
#             2. The AI will identify relevant universities and search their official websites
#             3. Get direct links to funding opportunities with descriptions
            
#             ### Example queries:
#             - "PhD funding in machine learning at University of Toronto and University of British Columbia"
#             - "Master's scholarships for international students in environmental science"
#             - "Computer science doctoral programs with funding in Europe"
#             - "Find me AI research scholarships"
#             """
#         )
        
#         with gr.Row():
#             with gr.Column(scale=2):
#                 query_input = gr.Textbox(
#                     label="🔍 What funding are you looking for?",
#                     placeholder="e.g., 'PhD funding in computer science at MIT and Stanford' or 'Master's scholarships for international students in UK universities'",
#                     lines=3,
#                     max_lines=3
#                 )
                
#                 search_btn = gr.Button(
#                     "🚀 Search Funding Opportunities",
#                     variant="primary",
#                     size="lg"
#                 )
            
#             with gr.Column(scale=1):
#                 gr.Markdown(
#                     """
#                     ### 💡 Tips for better results:
#                     - Be specific about your field of study
#                     - Mention degree level (PhD, Master's, etc.)
#                     - Include preferred universities or countries
#                     - Use relevant keywords like 'scholarship', 'funding', 'studentship'
#                     """
#                 )
        
#         with gr.Row():
#             output = gr.Markdown(
#                 label="📋 Funding Opportunities Found",
#                 elem_classes="results-box"
#             )
        
#         # Examples section
#         gr.Markdown("### 💬 Example Queries to Try:")
#         examples = gr.Examples(
#             examples=[
#                 ["PhD funding in artificial intelligence and machine learning at University of Cambridge and Imperial College London"],
#                 ["Master's scholarships for international students in data science in Canadian universities"],
#                 ["Find me computer science doctoral programs with full funding in the United States"],
#                 ["Biotechnology research scholarships and studentships in Australian universities"],
#                 ["Environmental science PhD funding opportunities in Europe with scholarships"]
#             ],
#             inputs=query_input,
#             label="Click any example to try it!"
#         )
        
#         # Connect the button
#         search_btn.click(
#             fn=search_funding_opportunities,
#             inputs=query_input,
#             outputs=output
#         )
        
#         # Also allow Enter key to submit
#         query_input.submit(
#             fn=search_funding_opportunities,
#             inputs=query_input,
#             outputs=output
#         )
    
#     return interface

#gr.ChatInterface(chat, type="messages").launch()
