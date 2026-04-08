---
title: FindMyScholarship AI
emoji: 🎓
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# 🎓 FindMyScholarship AI

FindMyScholarship AI is an agentic web application that helps students and researchers discover scholarships, funding opportunities, and grants for Master's and PhD programs by automatically searching and analysing official university websites.

Instead of relying on static databases, the system dynamically:
1. Identifies relevant universities from a user's query
2. Crawls their official domains
3. Analyses pages to extract funding-related information
4. Presents results conversationally through an intuitive chat interface

## ✨ Features

* 🔍 **Natural language search** — Ask questions like:
   * "PhD funding in machine learning in UK universities"
   * "Master's scholarships for international students in Canada"
* 🌐 **Automated university domain discovery** — Uses search APIs to locate official school websites
* 🕸 **Web crawling** — Crawls relevant pages such as:
   * Scholarships
   * Funding
   * Studentships
   * Graduate admissions
* 🧠 **AI-powered content analysis** — Extracts and summarises relevant funding information
* 💬 **Conversational interface (Gradio)** — Results appear as a persistent chat history (previous answers are not lost)
* 🧹 **Clean UX**
   * Input field clears after each query
   * Results accumulate instead of overwriting
   * No loading "…" ambiguity — real responses only

## 🧠 Architecture Overview

```
User Query
   ↓
Scholarship Agent
   ↓
Domain Finder (search engine / SerpAPI)
   ↓
Web Crawler (official university pages)
   ↓
Analyzer (LLM-based relevance extraction)
   ↓
Gradio Chat UI
```

## 🗂 Project Structure

```
.
├── app.py                         # Gradio UI entry point
├── requirements.txt               # Python dependencies
├── scholarship_agents/
│   ├── schorlarship_agent.py      # Main agent orchestration
│   ├── find_domain.py             # University domain discovery
│   ├── crawler.py                 # Web crawler
│   ├── analyzer.py                # Content analysis & summarisation
│   └── __init__.py
```

## 🚀 Getting Started

### 1️⃣ Clone the repository

```bash
git clone https://github.com/<your-username>/FindMyScholarship.git
cd FindMyScholarship
```

### 2️⃣ Create a virtual environment (recommended)

```bash
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
# OR
.venv\Scripts\activate      # Windows
```

### 3️⃣ Install dependencies

```bash
pip install -r requirements.txt
```

### 4️⃣ Environment variables

Create a `.env` file for local development:

```env
OPENAI_API_KEY=your_openai_key
SERPAPI_API_KEY=your_serpapi_key
```

⚠️ **Important:** When deploying to Hugging Face Spaces, do not use `.env`. Instead, set these values in **Space → Settings → Repository Secrets**.

### 5️⃣ Run the app

```bash
python app.py
```

Then open the local URL shown in the terminal.

## ☁️ Deployment (Hugging Face Spaces)

This project is fully compatible with Hugging Face Spaces (Gradio SDK).

### Steps:

1. Create a new Space (`repo-type=space`, `sdk=gradio`)
2. Upload:
   * `app.py`
   * `scholarship_agents/`
   * `requirements.txt`
3. Add secrets:
   * `OPENAI_API_KEY`
   * `SERPAPI_API_KEY`
   * `SERPAPI_API_KEY`
4. Restart the Space

The app will be live within seconds.

## 🛠 Tech Stack

* **Python 3.10+**
* **Gradio** — UI & interaction
* **OpenAI API** — reasoning & summarisation
* **SerpAPI / Search API** — domain discovery
* **Requests / BeautifulSoup / aiohttp** — crawling
* **dotenv** — local environment management

## 🔒 Notes & Limitations

* Results depend on the availability and structure of university websites
* Some funding pages may block scraping or require authentication
* API usage may incur costs (OpenAI / SerpAPI)
* This tool is intended for research assistance, not guaranteed funding accuracy

## 🧭 Future Improvements

* 🔄 Async multi-domain crawling (faster results)
* 📊 Structured extraction (amount, deadline, eligibility)
* ⭐ Ranking by relevance score
* 🧠 Result caching for repeated queries
* 📱 Mobile-friendly UI improvements

## 📄 License

MIT License — You are free to use, modify, and distribute this project with attribution.

---

**Made with ❤️ for students seeking funding opportunities**
