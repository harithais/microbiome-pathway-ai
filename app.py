import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from collections import defaultdict
from pyvis.network import Network
import spacy

@st.cache_resource
@st.cache_resource
def load_model():
    try:
        return spacy.load("en_core_sci_sm")
    except OSError:
        from spacy.cli import download
        download("en_core_sci_sm")
        return spacy.load("en_core_sci_sm")

nlp = load_model()

st.set_page_config(layout="wide")
st.title("🧬 Microbiome Regulation Explorer")
st.markdown("Enter two keywords to explore how bacteria are regulated in recent PubMed literature.")

col1, col2 = st.columns(2)
with col1:
    keyword_1 = st.text_input("Keyword 1", value="stress")
with col2:
    keyword_2 = st.text_input("Keyword 2", value="women")

if st.button("Search"):
    query = f'({keyword_1}[Title/Abstract]) AND ({keyword_2}[Title/Abstract]) AND (microbiome[Title/Abstract] OR HPA[Title/Abstract])'
    today = datetime.today()
    start_date = (today - timedelta(days=3*365)).strftime("%Y/%m/%d")

    search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {
        "db": "pubmed",
        "term": f"{query} AND ({start_date}[PDAT] : {today.strftime('%Y/%m/%d')}[PDAT])",
        "retmode": "json",
        "retmax": 100
    }

    response = requests.get(search_url, params=params).json()
    paper_ids = response.get("esearchresult", {}).get("idlist", [])
    st.success(f"Found {len(paper_ids)} papers.")

    up_patterns = ["upregulated", "increased", "elevated", "raised"]
    down_patterns = ["downregulated", "decreased", "reduced", "lowered"]
    bacteria_regulation = defaultdict(lambda: {"up": [], "down": []})

    papers = []

    for pid in paper_ids:
        try:
            summary_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={pid}&retmode=json"
            summary = requests.get(summary_url).json()
            title = summary["result"][pid]["title"]

            fetch_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={pid}&retmode=xml"
            fetch_response = requests.get(fetch_url)
            soup = BeautifulSoup(fetch_response.content, "xml")
            abstract = soup.find("AbstractText")
            abstract_text = abstract.text if abstract else ""

            paper = {
                "title": title,
                "abstract": abstract_text,
                "link": f"https://pubmed.ncbi.nlm.nih.gov/{pid}/"
            }
            papers.append(paper)

            doc = nlp(paper["abstract"])
            bacteria_found = [ent.text.lower() for ent in doc.ents if ent.label_ in ["ORG", "GPE", "LOC", "PERSON", "NORP"] or "bact" in ent.text.lower()]
            text_lower = (title + " " + abstract_text).lower()

            for bacterium in set(bacteria_found):
                if any(p in text_lower for p in up_patterns):
                    bacteria_regulation[bacterium]["up"].append(paper)
                elif any(p in text_lower for p in down_patterns):
                    bacteria_regulation[bacterium]["down"].append(paper)

        except Exception:
            continue

    if not bacteria_regulation:
        st.warning("No regulated bacteria found.")
    else:
        net = Network(notebook=False, height='600px', width='100%', bgcolor='#ffffff', font_color='black')

        for bacterium, data in bacteria_regulation.items():
            label = bacterium.capitalize()
            color = "#00cc66" if data["up"] and not data["down"] else "#cc3300" if data["down"] and not data["up"] else "#9999ff"
            title_html = "<br><b>Upregulated:</b><ul>" + "".join([f"<li>{p['title']}</li>" for p in data["up"]]) + "</ul>"
            title_html += "<b>Downregulated:</b><ul>" + "".join([f"<li>{p['title']}</li>" for p in data["down"]]) + "</ul>"
            net.add_node(bacterium, label=label, title=title_html, color=color)

        output_file = "bacteria_network.html"
        net.write_html(output_file)

        with open(output_file, "r", encoding="utf-8") as f:
            html = f.read()
            st.components.v1.html(html, height=600, scrolling=True)
