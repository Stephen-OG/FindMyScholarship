# def chat(message, history):
#     messages = [{"role": "system", "content": system_prompt}] + history + [{"role": "user", "content": message}]
#     response = Runner.run(schorlaship_agent, messages)
#     return response.final_output

# import gradio as gr
# from dotenv import load_dotenv
# from schorlarship_finder import chat
# load_dotenv(override=True)



# def create_gradio_interface():

#     with gr.Blocks(theme=gr.themes.Soft()) as interface:

#         gr.Markdown("# 🎓 FindMyScholarship AI\nFind scholarships and funding worldwide.")

#         query_input = gr.Textbox(
#             label="🔍 What funding are you looking for?",
#             placeholder="e.g. PhD funding in machine learning at University of Oregon or UK universities",
#             lines=3,
#         )

#         search_btn = gr.Button("🚀 Search Funding Opportunities", variant="primary")
#         output = gr.Markdown(elem_classes="results-box")

#         async def process_query(message):
#             result = await chat(message, [])
#             return result

#         search_btn.click(process_query, query_input, output)
#         query_input.submit(process_query, query_input, output)

#     return interface








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
