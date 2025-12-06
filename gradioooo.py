# def chat(message, history):
#     messages = [{"role": "system", "content": system_prompt}] + history + [{"role": "user", "content": message}]
#     response = Runner.run(schorlaship_agent, messages)
#     return response.final_output

# import gradio as gr
# from dotenv import load_dotenv
# from schorlarship_finder import chat
# load_dotenv(override=True)

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

# gr.ChatInterface(chat, type="messages").launch()








# async def run_scholarship_search(user_query: str) -> List[Dict[str, Any]]:
#     logger.info(f"Starting scholarship search for query: {user_query}")

#     try:
#         uni_domains: MultipleSchoolsAndDomains = await discover_university_domains(user_query)
#         logger.info(
#             f"Domain discovery complete. Found {len(uni_domains.schools)} universities."
#         )
#     except Exception as e:
#         logger.error(f"Domain discovery failed: {e}", exc_info=True)
#         return [{"error": "Domain discovery failed. Try refining your query."}]

#     all_results: List[Dict[str, Any]] = []

#     for school in uni_domains.schools:
#         logger.info(f"Processing school: {school.school}")

#         for domain in school.domains:
#             logger.info(f"  Crawling domain: {domain}")

#             try:
#                 pages = await crawl_university_funding(
#                     domain_url=domain,
#                     user_query=user_query
#                 )
#                 logger.info(f"  Found {len(pages)} relevant pages at {domain}")
#             except Exception as e:
#                 logger.error(
#                     f"  Crawling failed for domain {domain}: {e}", exc_info=True
#                 )
#                 continue  # skip this domain, continue pipeline

#             for page in pages:
#                 url = page.get("url")
#                 logger.info(f"    Analyzing page: {url}")

#                 try:
#                     analysis = await analyze_funding_page(
#                         url=url,
#                         title=page.get("title", ""),
#                         preview=page.get("text", ""),
#                         user_query=user_query,
#                     )
#                 except Exception as e:
#                     logger.error(
#                         f"    Analysis failed for page {url}: {e}",
#                         exc_info=True
#                     )
#                     continue  # skip this page

#                 all_results.append(
#                     {
#                         "school": school.school,
#                         "domain": domain,
#                         "page_url": page["url"],
#                         "page_title": page.get("title", ""),
#                         "page_preview": page.get("text", ""),
#                         "page_relevance_score": page.get("relevance_score", 0),
#                         "analysis": analysis,
#                     }
#                 )

#     if not all_results:
#         logger.warning("Pipeline completed but no results were found.")

#     logger.info("Pipeline complete.")
#     all_results.sort(key=lambda r: r.get("page_relevance_score", 0), reverse=True)
#     return all_results
