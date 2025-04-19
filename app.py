import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from collections import defaultdict
import spacy

st.set_page_config(layout="wide")

# Load spaCy model
@st.cache_resource
def load_model():
    import en_core_web_sm
    return en_core_web_sm.load()

nlp = load_model()

st.title("🧬 Full-Text Bacteria Explorer")
st.markdown("Search PubMed for full-text papers mentioning bacteria under stress-related keywords. Click each paper to see matched sentences.")

col1, col2 = st.columns(2)
with col1:
    keyword_1 = st.text_input("Keyword 1", value="stress")
with col2:
    keyword_2 = st.text_input("Keyword 2", value="women")

if st.button("Search"):
    query = f'({keyword_1}[Title/Abstract]) AND ({keyword_2}[Title/Abstract]) AND (microbiome[Title/Abstract] OR gut[Title/Abstract] OR "gut microbiota"[Title/Abstract] OR flora[Title/Abstract] OR bacteria[Title/Abstract] OR "gut-brain axis"[Title/Abstract] OR HPA[Title/Abstract] OR "hypothalamic pituitary adrenal"[Title/Abstract])'
    
    # Date filter: last 3 years
    today = datetime.today()
    start_date = (today - timedelta(days=3*365)).strftime("%Y/%m/%d")

    # PubMed search
    search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {
        "db": "pubmed",
        "term": f"{query} AND ({start_date}[PDAT] : {today.strftime('%Y/%m/%d')}[PDAT])",
        "retmode": "json",
        "retmax": 30
    }

    response = requests.get(search_url, params=params).json()
    paper_ids = response.get("esearchresult", {}).get("idlist", [])
    st.success(f"Found {len(paper_ids)} papers.")

    def get_pmc_id(pmid):
        # Try converting PubMed ID to PMC ID
        url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi?dbfrom=pubmed&id={pmid}&retmode=json&linkname=pubmed_pmc"
        r = requests.get(url)
        links = r.json().get('linksets', [])
        if links and 'linksetdbs' in links[0]:
            for db in links[0]['linksetdbs']:
                for link in db.get('links', []):
                    if link.startswith('PMC'):
                        return link.replace("PMC", "")
        return None

    def extract_text_from_pmc(pmcid):
        # Fetch full-text XML
        url = f"https://www.ncbi.nlm.nih.gov/pmc/oai/oai.cgi?verb=GetRecord&identifier=oai:pubmedcentral.nih.gov:{pmcid}&metadataPrefix=pmc"
        xml = requests.get(url).content
        soup = BeautifulSoup(xml, "xml")
        body = soup.find("body")
        if body:
            return body.get_text(separator=" ")
        return None

    def extract_bacteria_sentences(text):
        doc = nlp(text)
        sentences = list(doc.sents)
        results = defaultdict(list)
        for sent in sentences:
            for ent in sent.ents:
                if ent.label_ in ["ORG", "GPE", "LOC", "PERSON", "NORP"] or "bact" in ent.text.lower():
                    results[ent.text.lower()].append(sent.text.strip())
        return results

    for pid in paper_ids:
        try:
            # Get summary (title)
            summary_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={pid}&retmode=json"
            summary = requests.get(summary_url).json()
            title = summary["result"][pid]["title"]
            link = f"https://pubmed.ncbi.nlm.nih.gov/{pid}/"

            # Try full text
            pmcid = get_pmc_id(pid)
            if pmcid:
                text = extract_text_from_pmc(pmcid)
            else:
                # Fallback: abstract only
                fetch_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={pid}&retmode=xml"
                fetch_response = requests.get(fetch_url)
                soup = BeautifulSoup(fetch_response.content, "xml")
                abstract = soup.find("AbstractText")
                text = abstract.text if abstract else ""

            if text:
                bac_matches = extract_bacteria_sentences(text)
                if bac_matches:
                    with st.expander(f"📄 {title}"):
                        st.markdown(f"[🔗 View on PubMed]({link})")
                        for bac, sents in bac_matches.items():
                            st.markdown(f"**🦠 {bac.capitalize()}**")
                            for s in sents:
                                st.markdown(f"• _{s}_")
                            st.markdown("---")
        except Exception as e:
            st.warning(f"Failed on paper {pid}: {e}")
